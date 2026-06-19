import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import Problem, Round

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def seed_round_problems(db: Session, round_id: str) -> int:
    seed_path = DATA_DIR / "seed_problems.json"
    with open(seed_path, encoding="utf-8") as f:
        problems_data = json.load(f)

    added = 0
    for item in problems_data:
        exists = db.query(Problem).filter(Problem.id == item["id"], Problem.round_id == round_id).first()
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
