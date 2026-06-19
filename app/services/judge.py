import json

from openai import OpenAI

from app.config import settings
from app.schemas import JudgeResult
from app.utils import load_rubric, normalize_judge_response

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
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set. Add it to your .env file.")

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

    raw = json.loads(response.choices[0].message.content)
    raw = normalize_judge_response(raw)
    result = JudgeResult(**raw)

    usage = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
    }
    if response.usage.prompt_tokens_details:
        usage["cached_tokens"] = getattr(response.usage.prompt_tokens_details, "cached_tokens", 0)

    return result, usage
