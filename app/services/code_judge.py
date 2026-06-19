import json

from openai import OpenAI

from app.config import settings
from app.schemas import JudgeResult
from app.utils import load_code_rubric, normalize_judge_response

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
    criteria_list = "\n".join(f"- {c}" for c in acceptance_criteria) if acceptance_criteria else "None specified"
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
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set. Add it to your .env file.")

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

    raw = json.loads(response.choices[0].message.content)
    raw = normalize_judge_response(raw)
    result = JudgeResult(**raw)

    usage = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
    }
    return result, usage
