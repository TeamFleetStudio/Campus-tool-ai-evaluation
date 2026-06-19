import json

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import settings

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


class CodeFile(BaseModel):
    path: str
    content: str


class CodegenResult(BaseModel):
    files: list[CodeFile]
    language: str
    summary: str


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
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set. Add it to your .env file.")

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
    result = CodegenResult(**raw)

    usage = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
    }
    return result, usage
