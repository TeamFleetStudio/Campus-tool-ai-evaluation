import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Evaluation, Problem, Round, get_db
from app.schemas import (
    AssignmentResponse,
    CreateRoundRequest,
    EvaluateDirectRequest,
    EvaluateResponse,
    EvaluateRoundRequest,
    ProblemResponse,
    RoundResponse,
    SampleAnswerResponse,
)
from app.services.assignment import assign_problem
from app.services.judge import run_judge
from app.services.scoring import compute_total_score
from app.services.seed import load_sample_answers, seed_round_problems
from app.utils import load_rubric, validate_problem_statement, validate_user_prompt

router = APIRouter(prefix="/v1", tags=["evaluation"])


def _build_evaluate_response(
    evaluation: Evaluation,
    breakdown,
    usage: dict,
) -> EvaluateResponse:
    return EvaluateResponse(
        evaluation_id=evaluation.id,
        round_id=evaluation.round_id,
        participant_id=evaluation.participant_id,
        problem_id=evaluation.problem_id,
        problem_statement=evaluation.problem_statement,
        rubric_version=evaluation.rubric_version,
        total_score=evaluation.total_score,
        criteria=breakdown,
        flags=json.loads(evaluation.flags_json),
        summary=evaluation.summary or "",
        model=evaluation.model or "",
        usage=usage,
        created_at=evaluation.created_at,
    )


def _persist_evaluation(
    db: Session,
    *,
    problem_statement: str,
    user_prompt: str,
    judge_result,
    total_score: float,
    breakdown,
    usage: dict,
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
        rubric_version=judge_result.rubric_version,
        total_score=total_score,
        criteria_json=json.dumps([c.model_dump() for c in breakdown]),
        flags_json=json.dumps(judge_result.flags),
        summary=judge_result.summary,
        model=settings.openai_model,
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation


@router.post("/evaluate", response_model=EvaluateResponse)
def evaluate_round_submission(body: EvaluateRoundRequest, db: Session = Depends(get_db)):
    """
    **Primary endpoint for participants.**

    Pass the prompting answer in `user_prompt`.
    The server assigns a problem from the bank (first submit) and evaluates
  the prompt against that problem using GPT-4o.
    """
    try:
        validate_user_prompt(body.user_prompt)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    round_obj = db.query(Round).filter(Round.id == body.round_id).first()
    if not round_obj:
        raise HTTPException(status_code=404, detail=f"Round not found: {body.round_id}")

    try:
        assignment = assign_problem(db, round_obj, body.participant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    problem = db.query(Problem).filter(Problem.id == assignment.problem_id).first()
    if not problem:
        raise HTTPException(status_code=500, detail="Assigned problem not found")

    try:
        judge_result, usage = run_judge(problem.problem_statement, body.user_prompt)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Judge call failed: {e}") from e

    total_score, breakdown = compute_total_score(judge_result.criteria)
    evaluation = _persist_evaluation(
        db,
        problem_statement=problem.problem_statement,
        user_prompt=body.user_prompt,
        judge_result=judge_result,
        total_score=total_score,
        breakdown=breakdown,
        usage=usage,
        round_id=body.round_id,
        participant_id=body.participant_id,
        problem_id=problem.id,
        assignment_id=assignment.id,
    )
    return _build_evaluate_response(evaluation, breakdown, usage)


@router.post("/evaluate/direct", response_model=EvaluateResponse)
def evaluate_direct(body: EvaluateDirectRequest, db: Session = Depends(get_db)):
    """
    Evaluate without a round — useful for testing.

    Pass `problem_statement` and the prompting answer in `user_prompt`.
    """
    try:
        validate_problem_statement(body.problem_statement)
        validate_user_prompt(body.user_prompt)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        judge_result, usage = run_judge(body.problem_statement, body.user_prompt)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Judge call failed: {e}") from e

    total_score, breakdown = compute_total_score(judge_result.criteria)
    evaluation = _persist_evaluation(
        db,
        problem_statement=body.problem_statement,
        user_prompt=body.user_prompt,
        judge_result=judge_result,
        total_score=total_score,
        breakdown=breakdown,
        usage=usage,
    )
    return _build_evaluate_response(evaluation, breakdown, usage)


@router.post("/rounds", response_model=RoundResponse)
def create_round(body: CreateRoundRequest, db: Session = Depends(get_db)):
    round_obj = Round(
        name=body.name,
        rubric_version=body.rubric_version,
        assignment_strategy=body.assignment_strategy,
    )
    db.add(round_obj)
    db.commit()
    db.refresh(round_obj)

    if body.seed_problems:
        seed_round_problems(db, round_obj.id)

    problem_count = db.query(Problem).filter(Problem.round_id == round_obj.id).count()
    return RoundResponse(
        id=round_obj.id,
        name=round_obj.name,
        rubric_version=round_obj.rubric_version,
        assignment_strategy=round_obj.assignment_strategy,
        problem_count=problem_count,
        created_at=round_obj.created_at,
    )


@router.get("/rounds/{round_id}", response_model=RoundResponse)
def get_round(round_id: str, db: Session = Depends(get_db)):
    round_obj = db.query(Round).filter(Round.id == round_id).first()
    if not round_obj:
        raise HTTPException(status_code=404, detail="Round not found")
    problem_count = db.query(Problem).filter(Problem.round_id == round_id).count()
    return RoundResponse(
        id=round_obj.id,
        name=round_obj.name,
        rubric_version=round_obj.rubric_version,
        assignment_strategy=round_obj.assignment_strategy,
        problem_count=problem_count,
        created_at=round_obj.created_at,
    )


def _problem_response(p: Problem) -> ProblemResponse:
    criteria = json.loads(p.acceptance_criteria) if p.acceptance_criteria else []
    return ProblemResponse(
        id=p.id,
        round_id=p.round_id,
        title=p.title,
        difficulty=p.difficulty,
        problem_statement=p.problem_statement,
        approx_tokens=p.approx_tokens,
        problem_type=p.problem_type or "prompt_only",
        acceptance_criteria=criteria,
    )


@router.get("/rounds/{round_id}/problems", response_model=list[ProblemResponse])
def list_problems(round_id: str, db: Session = Depends(get_db)):
    problems = db.query(Problem).filter(Problem.round_id == round_id).all()
    return [_problem_response(p) for p in problems]


@router.get("/rounds/{round_id}/assignment/{participant_id}", response_model=AssignmentResponse)
def get_assignment(round_id: str, participant_id: str, db: Session = Depends(get_db)):
    round_obj = db.query(Round).filter(Round.id == round_id).first()
    if not round_obj:
        raise HTTPException(status_code=404, detail="Round not found")

    assignment = assign_problem(db, round_obj, participant_id)
    problem = db.query(Problem).filter(Problem.id == assignment.problem_id).first()
    criteria = json.loads(problem.acceptance_criteria) if problem.acceptance_criteria else []
    return AssignmentResponse(
        round_id=round_id,
        participant_id=participant_id,
        problem_id=problem.id,
        problem_statement=problem.problem_statement,
        title=problem.title,
        problem_type=problem.problem_type or "prompt_only",
        acceptance_criteria=criteria,
        assigned_at=assignment.assigned_at,
    )


@router.get("/evaluations/{evaluation_id}", response_model=EvaluateResponse)
def get_evaluation(evaluation_id: str, db: Session = Depends(get_db)):
    evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    from app.schemas import CriterionBreakdown

    breakdown = [CriterionBreakdown(**c) for c in json.loads(evaluation.criteria_json)]
    return EvaluateResponse(
        evaluation_id=evaluation.id,
        round_id=evaluation.round_id,
        participant_id=evaluation.participant_id,
        problem_id=evaluation.problem_id,
        problem_statement=evaluation.problem_statement,
        rubric_version=evaluation.rubric_version,
        total_score=evaluation.total_score,
        criteria=breakdown,
        flags=json.loads(evaluation.flags_json),
        summary=evaluation.summary or "",
        model=evaluation.model or "",
        usage={
            "prompt_tokens": evaluation.prompt_tokens,
            "completion_tokens": evaluation.completion_tokens,
        },
        created_at=evaluation.created_at,
    )


@router.get("/rubrics")
def get_rubric():
    return load_rubric()


@router.get("/samples/problems", response_model=list[ProblemResponse])
def get_sample_problems():
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent.parent / "data" / "seed_problems.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [
        ProblemResponse(
            id=p["id"],
            round_id="sample",
            title=p["title"],
            difficulty=p["difficulty"],
            problem_statement=p["problem_statement"],
            approx_tokens=p.get("approx_tokens"),
            problem_type=p.get("problem_type", "prompt_only"),
            acceptance_criteria=p.get("acceptance_criteria", []),
        )
        for p in data
    ]


@router.get("/samples/answers", response_model=list[SampleAnswerResponse])
def get_sample_answers(problem_id: str | None = None):
    answers = load_sample_answers()
    if problem_id:
        answers = [a for a in answers if a["problem_id"] == problem_id]
    return [SampleAnswerResponse(**a) for a in answers]


@router.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
