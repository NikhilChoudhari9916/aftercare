import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, model_validator

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseModel):
    """All configuration lives here. Each field reads the env variable named like it, uppercased."""

    model_config = ConfigDict(frozen=True)

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///aftercare.db"
    storage_dir: Path = Path("storage")

    backend_url: str = "http://localhost:8000"
    ui_url: str = "http://localhost:8080"

    google_client_id: str = ""
    google_client_secret: str = ""
    login_state_secret: str = ""

    session_idle_hours: int = 12
    session_max_days: int = 7

    model_main: str = "claude-sonnet-5-5"
    model_fast: str = "claude-haiku-5-5"
    model_strong: str = "claude-opus-5-5"

    max_pdf_mb: int = 10
    max_pdf_pages: int = 30

    log_patient_text: bool = False

    @model_validator(mode="after")
    def _check_production_safety(self) -> Self:
        if self.app_env == "production":
            if self.log_patient_text:
                raise ValueError("LOG_PATIENT_TEXT must be off when APP_ENV=production")
            missing = [
                name.upper()
                for name in ("google_client_id", "google_client_secret", "login_state_secret")
                if not getattr(self, name)
            ]
            if missing:
                raise ValueError(f"Missing required settings in production: {', '.join(missing)}")
        return self

    @classmethod
    def from_env(cls) -> Self:
        values = {
            name: os.environ[name.upper()]
            for name in cls.model_fields
            if name.upper() in os.environ
        }
        return cls(**values)


@lru_cache
def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings.from_env()
