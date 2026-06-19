from app.config import settings


def compute_combined_score(prompt_score: float, output_score: float) -> float:
    combined = (
        settings.prompt_score_weight * prompt_score
        + settings.output_score_weight * output_score
    )
    return round(combined, 2)
