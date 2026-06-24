from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
    )

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    database_url: str = "sqlite:///./evaluations.db"
    problem_statement_max_tokens: int = 1500
    user_prompt_max_tokens: int = 8000
    problem_statement_min_tokens: int = 0
    user_prompt_min_tokens: int = 0
    prompt_score_weight: float = 0.4
    output_score_weight: float = 0.6


settings = Settings()
