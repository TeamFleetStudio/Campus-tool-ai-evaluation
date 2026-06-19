from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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


class EvaluateRoundRequest(BaseModel):
    """Submit a participant's prompting answer for a round."""

    round_id: str
    participant_id: str
    user_prompt: str = Field(
        ...,
        description="The participant's prompting answer — the prompt they would give an LLM.",
    )


class EvaluateDirectRequest(BaseModel):
    """Evaluate directly without round assignment (testing / admin)."""

    problem_statement: str
    user_prompt: str = Field(
        ...,
        description="The participant's prompting answer — the prompt they would give an LLM.",
    )
    rubric_version: str = "v1"


class EvaluateResponse(BaseModel):
    evaluation_id: str
    round_id: str | None = None
    participant_id: str | None = None
    problem_id: str | None = None
    problem_statement: str
    rubric_version: str
    total_score: float
    criteria: list[CriterionBreakdown]
    flags: list[str]
    summary: str
    model: str
    usage: dict
    created_at: datetime


class CreateRoundRequest(BaseModel):
    name: str
    rubric_version: str = "v1"
    assignment_strategy: Literal["random", "round_robin", "hash"] = "random"
    seed_problems: bool = True


class RoundResponse(BaseModel):
    id: str
    name: str
    rubric_version: str
    assignment_strategy: str
    problem_count: int
    created_at: datetime


class ProblemResponse(BaseModel):
    id: str
    round_id: str
    title: str
    difficulty: str
    problem_statement: str
    approx_tokens: float | None = None
    problem_type: str = "prompt_only"
    acceptance_criteria: list[str] = Field(default_factory=list)


class AssignmentResponse(BaseModel):
    round_id: str
    participant_id: str
    problem_id: str
    problem_statement: str
    title: str
    problem_type: str = "prompt_only"
    acceptance_criteria: list[str] = Field(default_factory=list)
    assigned_at: datetime


class SampleAnswerResponse(BaseModel):
    problem_id: str
    label: str
    user_prompt: str


ProblemType = Literal["prompt_only", "static_web", "react_spa", "backend_api"]


class CodeFile(BaseModel):
    path: str
    content: str


class GeneratedCode(BaseModel):
    files: list[CodeFile]
    language: str
    summary: str


class EvaluationDetail(BaseModel):
    total_score: float
    criteria: list[CriterionBreakdown]
    flags: list[str]
    summary: str


class EvaluateBuildDirectRequest(BaseModel):
    problem_statement: str
    user_prompt: str = Field(
        ...,
        description="The participant's prompting answer — instructions for the LLM to generate code.",
    )
    problem_type: ProblemType = "static_web"
    acceptance_criteria: list[str] = Field(default_factory=list)
    rubric_version: str = "v1"


class EvaluateBuildRoundRequest(BaseModel):
    round_id: str
    participant_id: str
    user_prompt: str = Field(
        ...,
        description="The participant's prompting answer — instructions for the LLM to generate code.",
    )


class BuildEvaluateResponse(BaseModel):
    evaluation_id: str
    round_id: str | None = None
    participant_id: str | None = None
    problem_id: str | None = None
    problem_statement: str
    problem_type: str
    prompt_score: float
    output_score: float
    combined_score: float
    prompt_evaluation: EvaluationDetail
    output_evaluation: EvaluationDetail
    generated_code: GeneratedCode
    model: str
    usage: dict
    created_at: datetime
