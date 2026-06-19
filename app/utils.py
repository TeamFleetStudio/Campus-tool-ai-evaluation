import json
from pathlib import Path

import tiktoken

from app.config import settings

RUBRIC_PATH = Path(__file__).resolve().parent.parent / "rubrics" / "v1.json"
CODE_RUBRIC_PATH = Path(__file__).resolve().parent.parent / "rubrics" / "code_v1.json"
_encoding = tiktoken.get_encoding("cl100k_base")


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
