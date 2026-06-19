import json

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Evaluation
from app.schemas import BuildEvaluateResponse, CodeFile, EvaluationDetail, GeneratedCode
from app.services.code_judge import run_code_judge
from app.services.codegen import run_codegen
from app.services.combined import compute_combined_score
from app.services.judge import run_judge
from app.services.scoring import compute_total_score
from app.utils import load_code_rubric, load_rubric


def _merge_usage(
    prompt_usage: dict,
    codegen_usage: dict,
    code_judge_usage: dict,
) -> dict:
    return {
        "prompt_judge_tokens": prompt_usage.get("total_tokens", 0),
        "codegen_tokens": codegen_usage.get("total_tokens", 0),
        "code_judge_tokens": code_judge_usage.get("total_tokens", 0),
        "total_tokens": (
            prompt_usage.get("total_tokens", 0)
            + codegen_usage.get("total_tokens", 0)
            + code_judge_usage.get("total_tokens", 0)
        ),
        "prompt_judge": prompt_usage,
        "codegen": codegen_usage,
        "code_judge": code_judge_usage,
    }


def run_build_evaluation(
    *,
    problem_statement: str,
    user_prompt: str,
    problem_type: str,
    acceptance_criteria: list[str] | None = None,
) -> tuple[dict, dict]:
    criteria = acceptance_criteria or []

    prompt_judge_result, prompt_usage = run_judge(problem_statement, user_prompt)
    prompt_score, prompt_breakdown = compute_total_score(
        prompt_judge_result.criteria, load_rubric()
    )

    codegen_result, codegen_usage = run_codegen(
        problem_statement, user_prompt, problem_type
    )
    files = [f.model_dump() for f in codegen_result.files]

    code_judge_result, code_judge_usage = run_code_judge(
        problem_statement, criteria, files, problem_type
    )
    output_score, output_breakdown = compute_total_score(
        code_judge_result.criteria, load_code_rubric()
    )

    combined_score = compute_combined_score(prompt_score, output_score)
    usage = _merge_usage(prompt_usage, codegen_usage, code_judge_usage)

    result = {
        "prompt_score": prompt_score,
        "output_score": output_score,
        "combined_score": combined_score,
        "prompt_evaluation": EvaluationDetail(
            total_score=prompt_score,
            criteria=prompt_breakdown,
            flags=prompt_judge_result.flags,
            summary=prompt_judge_result.summary,
        ),
        "output_evaluation": EvaluationDetail(
            total_score=output_score,
            criteria=output_breakdown,
            flags=code_judge_result.flags,
            summary=code_judge_result.summary,
        ),
        "generated_code": GeneratedCode(
            files=[CodeFile(**f) for f in files],
            language=codegen_result.language,
            summary=codegen_result.summary,
        ),
        "prompt_judge_result": prompt_judge_result,
        "code_judge_result": code_judge_result,
        "prompt_breakdown": prompt_breakdown,
        "output_breakdown": output_breakdown,
        "usage": usage,
        "problem_type": problem_type,
    }
    return result, usage


def persist_build_evaluation(
    db: Session,
    *,
    problem_statement: str,
    user_prompt: str,
    result: dict,
    round_id: str | None = None,
    participant_id: str | None = None,
    problem_id: str | None = None,
    assignment_id: str | None = None,
) -> Evaluation:
    evaluation = Evaluation(
        assignment_id=assignment_id,
        round_id=round_id,
        participant_id=participant_id,
        problem_id=problem_id,
        problem_statement=problem_statement,
        user_prompt=user_prompt,
        rubric_version=result["prompt_judge_result"].rubric_version,
        total_score=result["combined_score"],
        criteria_json=json.dumps([c.model_dump() for c in result["prompt_breakdown"]]),
        flags_json=json.dumps(result["prompt_judge_result"].flags),
        summary=result["prompt_evaluation"].summary,
        model=settings.openai_model,
        prompt_tokens=result["usage"]["prompt_judge"].get("prompt_tokens"),
        completion_tokens=result["usage"]["code_judge"].get("completion_tokens"),
        problem_type=result["problem_type"],
        prompt_score=result["prompt_score"],
        output_score=result["output_score"],
        combined_score=result["combined_score"],
        generated_code_json=json.dumps(result["generated_code"].model_dump()),
        output_criteria_json=json.dumps(
            [c.model_dump() for c in result["output_breakdown"]]
        ),
        evaluation_mode="build",
        usage_json=json.dumps(result["usage"]),
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation


def build_response(evaluation: Evaluation, result: dict) -> BuildEvaluateResponse:
    return BuildEvaluateResponse(
        evaluation_id=evaluation.id,
        round_id=evaluation.round_id,
        participant_id=evaluation.participant_id,
        problem_id=evaluation.problem_id,
        problem_statement=evaluation.problem_statement,
        problem_type=evaluation.problem_type or result["problem_type"],
        prompt_score=result["prompt_score"],
        output_score=result["output_score"],
        combined_score=result["combined_score"],
        prompt_evaluation=result["prompt_evaluation"],
        output_evaluation=result["output_evaluation"],
        generated_code=result["generated_code"],
        model=settings.openai_model,
        usage=result["usage"],
        created_at=evaluation.created_at,
    )
