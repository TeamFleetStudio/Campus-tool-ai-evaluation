import hashlib
import json
import random

from sqlalchemy.orm import Session

from app.database import Assignment, Problem, Round


def assign_problem(
    db: Session,
    round_obj: Round,
    participant_id: str,
) -> Assignment:
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
