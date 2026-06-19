import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import Problem, Round, get_db
from app.schemas import (
    BuildEvaluateResponse,
    EvaluateBuildDirectRequest,
    EvaluateBuildRoundRequest,
)
from app.services.assignment import assign_problem
from app.services.build_pipeline import (
    build_response,
    persist_build_evaluation,
    run_build_evaluation,
)
from app.utils import load_code_rubric, validate_problem_statement, validate_user_prompt

router = APIRouter(prefix="/v1", tags=["build-evaluation"])

BUILD_TYPES = {"static_web", "react_spa", "backend_api"}


def _parse_acceptance_criteria(problem: Problem) -> list[str]:
    if not problem.acceptance_criteria:
        return []
    return json.loads(problem.acceptance_criteria)


@router.post("/evaluate/build/direct", response_model=BuildEvaluateResponse)
def evaluate_build_direct(body: EvaluateBuildDirectRequest, db: Session = Depends(get_db)):
    """
    Dual evaluation: score prompt quality + generate code from prompt + score output.

    Pass `problem_statement`, `user_prompt`, and `problem_type`.
    """
    if body.problem_type not in BUILD_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"problem_type must be one of: {', '.join(sorted(BUILD_TYPES))}",
        )

    try:
        validate_problem_statement(body.problem_statement)
        validate_user_prompt(body.user_prompt)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        result, _ = run_build_evaluation(
            problem_statement=body.problem_statement,
            user_prompt=body.user_prompt,
            problem_type=body.problem_type,
            acceptance_criteria=body.acceptance_criteria,
        )
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Build evaluation failed: {e}") from e

    evaluation = persist_build_evaluation(
        db,
        problem_statement=body.problem_statement,
        user_prompt=body.user_prompt,
        result=result,
    )
    return build_response(evaluation, result)


@router.post("/evaluate/build", response_model=BuildEvaluateResponse)
def evaluate_build_round(body: EvaluateBuildRoundRequest, db: Session = Depends(get_db)):
    """
    Competition flow for build problems: assign problem from bank, run dual evaluation.
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

    problem_type = problem.problem_type or "prompt_only"
    if problem_type not in BUILD_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Assigned problem '{problem.id}' is type '{problem_type}'. "
                "Use POST /v1/evaluate for prompt_only problems."
            ),
        )

    acceptance_criteria = _parse_acceptance_criteria(problem)

    try:
        result, _ = run_build_evaluation(
            problem_statement=problem.problem_statement,
            user_prompt=body.user_prompt,
            problem_type=problem_type,
            acceptance_criteria=acceptance_criteria,
        )
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Build evaluation failed: {e}") from e

    evaluation = persist_build_evaluation(
        db,
        problem_statement=problem.problem_statement,
        user_prompt=body.user_prompt,
        result=result,
        round_id=body.round_id,
        participant_id=body.participant_id,
        problem_id=problem.id,
        assignment_id=assignment.id,
    )
    return build_response(evaluation, result)


@router.get("/rubrics/code")
def get_code_rubric():
    return load_code_rubric()
