"""
AI Talent Summit — consolidated evaluation services.

Single-file handoff containing prompt judging, code generation, code judging,
scoring, build pipeline, assignment, and seed helpers.

Requires: openai, pydantic, pydantic-settings, tiktoken, sqlalchemy (for DB helpers)
Env: OPENAI_API_KEY, OPENAI_MODEL (default gpt-4o), PROMPT_SCORE_WEIGHT, OUTPUT_SCORE_WEIGHT
Rubrics: rubrics/v1.json, rubrics/code_v1.json (relative to project root)
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import tiktoken
from openai import OpenAI
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
RUBRIC_PATH = BASE_DIR / "rubrics" / "v1.json"
CODE_RUBRIC_PATH = BASE_DIR / "rubrics" / "code_v1.json"
DATA_DIR = BASE_DIR / "data"
_encoding = tiktoken.get_encoding("cl100k_base")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
    )

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    database_url: str = "sqlite:///./evaluations.db"
    problem_statement_max_tokens: int = 1500
    user_prompt_max_tokens: int = 8000
    problem_statement_min_tokens: int = 0
    user_prompt_min_tokens: int = 0
    prompt_score_weight: float = 0.4
    output_score_weight: float = 0.6


settings = Settings()


# ---------------------------------------------------------------------------
# Schemas (models used by services)
# ---------------------------------------------------------------------------


class CriterionScore(BaseModel):
    id: str
    score: float = Field(ge=0, le=10)
    rationale: str
    evidence: list[str] = []


class JudgeResult(BaseModel):
    rubric_version: str
    criteria: list[CriterionScore]
    flags: list[str] = []
    summary: str
    confidence: float = Field(ge=0, le=1)


class CriterionBreakdown(BaseModel):
    id: str
    name: str
    weight: float
    score: float
    weighted_contribution: float
    rationale: str
    evidence: list[str] = []


class CodeFile(BaseModel):
    path: str
    content: str


class CodegenResult(BaseModel):
    files: list[CodeFile]
    language: str
    summary: str


class GeneratedCode(BaseModel):
    files: list[CodeFile]
    language: str
    summary: str


class EvaluationDetail(BaseModel):
    total_score: float
    criteria: list[CriterionBreakdown]
    flags: list[str]
    summary: str


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def count_tokens(text: str) -> int:
    return len(_encoding.encode(text))


def load_rubric() -> dict:
    with open(RUBRIC_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_code_rubric() -> dict:
    with open(CODE_RUBRIC_PATH, encoding="utf-8") as f:
        return json.load(f)


def validate_problem_statement(text: str) -> None:
    tokens = count_tokens(text)
    if tokens < settings.problem_statement_min_tokens:
        raise ValueError(
            f"problem_statement too short: {tokens} tokens (min {settings.problem_statement_min_tokens})"
        )
    if tokens > settings.problem_statement_max_tokens:
        raise ValueError(
            f"problem_statement exceeds limit: {tokens} tokens (max {settings.problem_statement_max_tokens})"
        )


def validate_user_prompt(text: str) -> None:
    tokens = count_tokens(text)
    if tokens < settings.user_prompt_min_tokens:
        raise ValueError(
            f"user_prompt too short: {tokens} tokens (min {settings.user_prompt_min_tokens})"
        )
    if tokens > settings.user_prompt_max_tokens:
        raise ValueError(
            f"user_prompt exceeds limit: {tokens} tokens (max {settings.user_prompt_max_tokens})"
        )


def normalize_judge_response(raw: dict) -> dict:
    """Normalize judge JSON before validation (GPT sometimes returns confidence on 0-10 scale)."""
    if "confidence" in raw and isinstance(raw["confidence"], (int, float)):
        confidence = float(raw["confidence"])
        if confidence > 1:
            confidence = confidence / 10
        raw["confidence"] = max(0.0, min(1.0, confidence))
    return raw


def _require_api_key() -> None:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set. Add it to your .env file.")


def _usage_from_response(response) -> dict:
    usage = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
    }
    if response.usage.prompt_tokens_details:
        usage["cached_tokens"] = getattr(response.usage.prompt_tokens_details, "cached_tokens", 0)
    return usage


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def compute_total_score(
    criteria: list[CriterionScore], rubric: dict | None = None
) -> tuple[float, list[CriterionBreakdown]]:
    rubric = rubric or load_rubric()
    rubric_map = {c["id"]: c for c in rubric["criteria"]}

    breakdown: list[CriterionBreakdown] = []
    total = 0.0

    for item in criteria:
        meta = rubric_map.get(item.id)
        if not meta:
            continue
        weight = meta["weight"]
        contribution = (item.score / 10) * weight * 100
        breakdown.append(
            CriterionBreakdown(
                id=item.id,
                name=meta["name"],
                weight=weight,
                score=item.score,
                weighted_contribution=round(contribution, 2),
                rationale=item.rationale,
                evidence=item.evidence,
            )
        )
        total += contribution

    alignment = next((c.score for c in criteria if c.id == "problem_alignment"), 10)
    if alignment < 3:
        total = min(total, 40.0)

    return round(total, 2), breakdown


def compute_combined_score(prompt_score: float, output_score: float) -> float:
    combined = (
        settings.prompt_score_weight * prompt_score
        + settings.output_score_weight * output_score
    )
    return round(combined, 2)


# ---------------------------------------------------------------------------
# Prompt judge
# ---------------------------------------------------------------------------

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "rubric_version": {"type": "string"},
        "criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "score": {"type": "number"},
                    "rationale": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "score", "rationale", "evidence"],
                "additionalProperties": False,
            },
        },
        "flags": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["rubric_version", "criteria", "flags", "summary", "confidence"],
    "additionalProperties": False,
}


def build_judge_messages(problem_statement: str, user_prompt: str, rubric: dict) -> list[dict]:
    criteria_text = json.dumps(rubric["criteria"], indent=2)
    system = """You are an expert prompt evaluator for a technical competition.

Your job is to score the USER PROMPT (the participant's submission) against the PROBLEM STATEMENT.
You must NOT execute the task or solve the problem yourself.
Score only how well the user prompt would instruct an LLM to handle the problem.

Scoring scale per criterion (0-10):
- 0-2: Missing or completely inadequate
- 3-4: Weak, major gaps
- 5-6: Adequate but incomplete
- 7-8: Good, minor gaps
- 9-10: Excellent, comprehensive

Rules:
- Cite specific evidence from the user prompt in each rationale (quote or paraphrase).
- If the prompt is generic and could apply to any task, problem_alignment must be <= 3.
- If the prompt ignores the problem, problem_alignment must be <= 3.
- flags may include: off_topic, generic_boilerplate, unsafe, contradictory — or empty list.
- confidence must be a decimal between 0.0 and 1.0 (e.g. 0.85), NOT a 0-10 score.
- Return valid JSON matching the schema exactly."""

    user = f"""PROBLEM STATEMENT:
<<<PROBLEM>>>
{problem_statement}
<<<END PROBLEM>>>

USER PROMPT TO EVALUATE (this is the participant's prompting answer):
<<<PROMPT>>>
{user_prompt}
<<<END PROMPT>>>

RUBRIC CRITERIA (score each from 0-10):
{criteria_text}

Evaluate the USER PROMPT against the PROBLEM STATEMENT using every rubric criterion."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def run_judge(problem_statement: str, user_prompt: str) -> tuple[JudgeResult, dict]:
    _require_api_key()
    rubric = load_rubric()
    client = OpenAI(api_key=settings.openai_api_key)

    response = client.chat.completions.create(
        model=settings.openai_model,
        temperature=0,
        messages=build_judge_messages(problem_statement, user_prompt, rubric),
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "prompt_evaluation",
                "strict": True,
                "schema": JUDGE_SCHEMA,
            },
        },
    )

    raw = normalize_judge_response(json.loads(response.choices[0].message.content))
    return JudgeResult(**raw), _usage_from_response(response)


# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------

CODEGEN_SCHEMA = {
    "type": "object",
    "properties": {
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
        "language": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["files", "language", "summary"],
    "additionalProperties": False,
}

TYPE_INSTRUCTIONS = {
    "static_web": (
        "Generate a complete static website. Prefer a single index.html with inline CSS and JS "
        "unless separation improves clarity. Must be self-contained and runnable in a browser."
    ),
    "react_spa": (
        "Generate a minimal React SPA. Include index.html, a main App component file, and any "
        "supporting files needed. Use CDN React if a build step is not required."
    ),
    "backend_api": (
        "Generate a complete backend API with all routes implemented. Include a single entry file "
        "and any supporting modules. Code must be runnable."
    ),
}


def _build_codegen_messages(
    problem_statement: str,
    user_prompt: str,
    problem_type: str,
) -> list[dict]:
    type_hint = TYPE_INSTRUCTIONS.get(problem_type, TYPE_INSTRUCTIONS["static_web"])
    system = f"""You are a code generator executing a participant's prompt.

Your job is to generate working code based on the USER PROMPT instructions and PROBLEM STATEMENT.
Follow the user prompt as the primary instruction set.

Output type: {problem_type}
{type_hint}

Rules:
- Return complete, runnable code in the files array
- Do not include explanations outside the JSON schema
- Do not use placeholder comments like "implement here" — write real code
- Keep code focused on the requirements — no unnecessary boilerplate"""

    user = f"""PROBLEM STATEMENT:
<<<PROBLEM>>>
{problem_statement}
<<<END PROBLEM>>>

USER PROMPT (execute this to generate code):
<<<PROMPT>>>
{user_prompt}
<<<END PROMPT>>>

Generate the code files now."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def run_codegen(
    problem_statement: str,
    user_prompt: str,
    problem_type: str,
) -> tuple[CodegenResult, dict]:
    _require_api_key()
    client = OpenAI(api_key=settings.openai_api_key)

    response = client.chat.completions.create(
        model=settings.openai_model,
        temperature=0.2,
        messages=_build_codegen_messages(problem_statement, user_prompt, problem_type),
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "code_generation",
                "strict": True,
                "schema": CODEGEN_SCHEMA,
            },
        },
    )

    raw = json.loads(response.choices[0].message.content)
    return CodegenResult(**raw), _usage_from_response(response)


# ---------------------------------------------------------------------------
# Code judge
# ---------------------------------------------------------------------------

CODE_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "rubric_version": {"type": "string"},
        "criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "score": {"type": "number"},
                    "rationale": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "score", "rationale", "evidence"],
                "additionalProperties": False,
            },
        },
        "flags": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["rubric_version", "criteria", "flags", "summary", "confidence"],
    "additionalProperties": False,
}


def _format_files(files: list[dict]) -> str:
    parts = []
    for f in files:
        parts.append(f"=== FILE: {f['path']} ===\n{f['content']}\n=== END FILE ===")
    return "\n\n".join(parts)


def _build_code_judge_messages(
    problem_statement: str,
    acceptance_criteria: list[str],
    files: list[dict],
    problem_type: str,
    rubric: dict,
) -> list[dict]:
    criteria_text = json.dumps(rubric["criteria"], indent=2)
    criteria_list = (
        "\n".join(f"- {c}" for c in acceptance_criteria) if acceptance_criteria else "None specified"
    )
    code_text = _format_files(files)

    system = """You are an expert code reviewer for a technical competition.

Your job is to score GENERATED CODE against the PROBLEM STATEMENT and acceptance criteria.
You are reviewing code statically — you cannot execute it, but assess whether it would likely work.

Scoring scale per criterion (0-10):
- 0-2: Missing or completely inadequate
- 3-4: Weak, major gaps
- 5-6: Adequate but incomplete
- 7-8: Good, minor gaps
- 9-10: Excellent, comprehensive

Rules:
- Cite specific evidence from the code in each rationale (file names, snippets, features present/missing)
- If code is empty or unrelated to the problem, requirements_met must be <= 2
- flags may include: incomplete, non_functional, security_issue, placeholder_code — or empty list
- confidence must be a decimal between 0.0 and 1.0 (e.g. 0.85), NOT a 0-10 score.
- For backend_api problems, ui_completeness should reflect API surface completeness instead of UI
- Return valid JSON matching the schema exactly"""

    user = f"""PROBLEM STATEMENT:
<<<PROBLEM>>>
{problem_statement}
<<<END PROBLEM>>>

PROBLEM TYPE: {problem_type}

ACCEPTANCE CRITERIA:
{criteria_list}

GENERATED CODE:
<<<CODE>>>
{code_text}
<<<END CODE>>>

RUBRIC CRITERIA (score each from 0-10):
{criteria_text}

Evaluate the generated code against the problem statement and acceptance criteria."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def run_code_judge(
    problem_statement: str,
    acceptance_criteria: list[str],
    files: list[dict],
    problem_type: str,
) -> tuple[JudgeResult, dict]:
    _require_api_key()
    rubric = load_code_rubric()
    client = OpenAI(api_key=settings.openai_api_key)

    response = client.chat.completions.create(
        model=settings.openai_model,
        temperature=0,
        messages=_build_code_judge_messages(
            problem_statement, acceptance_criteria, files, problem_type, rubric
        ),
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "code_evaluation",
                "strict": True,
                "schema": CODE_JUDGE_SCHEMA,
            },
        },
    )

    raw = normalize_judge_response(json.loads(response.choices[0].message.content))
    return JudgeResult(**raw), _usage_from_response(response)


# ---------------------------------------------------------------------------
# Build pipeline (full 3-step evaluation)
# ---------------------------------------------------------------------------


def _merge_usage(prompt_usage: dict, codegen_usage: dict, code_judge_usage: dict) -> dict:
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
    """Run prompt judge → codegen → code judge. Returns (result dict, usage dict)."""
    criteria = acceptance_criteria or []

    prompt_judge_result, prompt_usage = run_judge(problem_statement, user_prompt)
    prompt_score, prompt_breakdown = compute_total_score(
        prompt_judge_result.criteria, load_rubric()
    )

    codegen_result, codegen_usage = run_codegen(problem_statement, user_prompt, problem_type)
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


def run_prompt_evaluation(
    problem_statement: str,
    user_prompt: str,
) -> tuple[float, list[CriterionBreakdown], JudgeResult, dict]:
    """Prompt-only evaluation. Returns (total_score, breakdown, judge_result, usage)."""
    judge_result, usage = run_judge(problem_statement, user_prompt)
    total_score, breakdown = compute_total_score(judge_result.criteria, load_rubric())
    return total_score, breakdown, judge_result, usage


# ---------------------------------------------------------------------------
# Assignment & seed (require app.database when used with FastAPI)
# ---------------------------------------------------------------------------


def assign_problem(db: Session, round_obj, participant_id: str):
    """Assign a problem from the round bank. Requires Round/Assignment/Problem ORM models."""
    from app.database import Assignment, Problem

    existing = (
        db.query(Assignment)
        .filter(Assignment.round_id == round_obj.id, Assignment.participant_id == participant_id)
        .first()
    )
    if existing:
        return existing

    problems = db.query(Problem).filter(Problem.round_id == round_obj.id).all()
    if not problems:
        raise ValueError(f"No problems in bank for round {round_obj.id}")

    strategy = round_obj.assignment_strategy
    if strategy == "round_robin":
        count = db.query(Assignment).filter(Assignment.round_id == round_obj.id).count()
        problem = problems[count % len(problems)]
    elif strategy == "hash":
        digest = int(hashlib.sha256(participant_id.encode()).hexdigest(), 16)
        problem = problems[digest % len(problems)]
    else:
        problem = random.choice(problems)

    assignment = Assignment(
        round_id=round_obj.id,
        participant_id=participant_id,
        problem_id=problem.id,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def seed_round_problems(db: Session, round_id: str) -> int:
    """Load problems from data/seed_problems.json into the database."""
    from app.database import Problem

    seed_path = DATA_DIR / "seed_problems.json"
    with open(seed_path, encoding="utf-8") as f:
        problems_data = json.load(f)

    added = 0
    for item in problems_data:
        exists = (
            db.query(Problem).filter(Problem.id == item["id"], Problem.round_id == round_id).first()
        )
        if exists:
            continue
        db.add(
            Problem(
                id=item["id"],
                round_id=round_id,
                title=item["title"],
                difficulty=item["difficulty"],
                problem_statement=item["problem_statement"],
                approx_tokens=item.get("approx_tokens"),
                problem_type=item.get("problem_type", "prompt_only"),
                acceptance_criteria=json.dumps(item.get("acceptance_criteria", [])),
            )
        )
        added += 1
    db.commit()
    return added


def load_sample_answers() -> list[dict]:
    with open(DATA_DIR / "sample_answers.json", encoding="utf-8") as f:
        return json.load(f)


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
):
    """Save build evaluation to database. Requires Evaluation ORM model."""
    from app.database import Evaluation

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
        output_criteria_json=json.dumps([c.model_dump() for c in result["output_breakdown"]]),
        evaluation_mode="build",
        usage_json=json.dumps(result["usage"]),
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation
