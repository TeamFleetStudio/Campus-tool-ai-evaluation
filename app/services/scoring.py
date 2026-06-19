from app.schemas import CriterionBreakdown, CriterionScore, JudgeResult
from app.utils import load_rubric


def compute_total_score(criteria: list[CriterionScore], rubric: dict | None = None) -> tuple[float, list[CriterionBreakdown]]:
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
