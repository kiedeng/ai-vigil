from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    app_name: str = "AI Eye Monitor"
    api_prefix: str = "/api"
    database_url: str = Field(default=f"sqlite:///{PROJECT_ROOT / 'data' / 'ai_eye.db'}")

    admin_username: str = "admin"
    admin_password: str = "admin123"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    new_api_base_url: str = "http://localhost:3000"
    new_api_key: str = ""
    evaluator_model: str = "deepseek-chat"

    default_interval_seconds: int = 300
    default_timeout_seconds: int = 30
    default_failure_threshold: int = 3
    alert_cooldown_minutes: int = 30
    scheduler_poll_seconds: int = 30

    frontend_dist_dir: str = str(PROJECT_ROOT / "frontend" / "dist")
    sample_storage_dir: str = str(PROJECT_ROOT / "data" / "samples")

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
