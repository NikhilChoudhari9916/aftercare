import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, model_validator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
RED_FLAGS_FILE = PROJECT_ROOT / "data" / "red_flags.yaml"


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

    anthropic_api_key: str = ""
    llm_timeout_seconds: float = 60.0
    job_workers: int = 2
    max_extraction_attempts: int = 2
    max_tool_calls: int = 6
    agent_timeout_seconds: float = 30.0
    classifier_runs: int = 3  # ADR-0005: run the safety classifier 3 times, take the most severe
    classifier_timeout_seconds: float = 10.0

    # Public drug-name and drug-label services. Only medicine names are ever sent to them.
    rxnav_base_url: str = "https://rxnav.nlm.nih.gov/REST"
    openfda_base_url: str = "https://api.fda.gov"
    external_timeout_seconds: float = 5.0
    external_cache_days: int = 7  # CLAUDE.md section 15: refresh weekly
    label_section_chars: int = 1500  # keeps a tool result short enough to read and cite

    log_patient_text: bool = False
    dev_login: bool = False

    @model_validator(mode="after")
    def _check_dev_login_is_local(self) -> Self:
        """The test login may only exist on a developer's own machine (ADR-0037)."""
        if self.dev_login:
            if self.app_env == "production":
                raise ValueError("DEV_LOGIN must be off when APP_ENV=production")
            if urlsplit(self.backend_url).hostname not in LOCAL_HOSTS:
                raise ValueError("DEV_LOGIN is only allowed when BACKEND_URL is a local address")
        return self

    @model_validator(mode="after")
    def _check_production_safety(self) -> Self:
        if self.app_env == "production":
            if self.log_patient_text:
                raise ValueError("LOG_PATIENT_TEXT must be off when APP_ENV=production")
            missing = [
                name.upper()
                for name in (
                    "google_client_id",
                    "google_client_secret",
                    "login_state_secret",
                    "anthropic_api_key",
                )
                if not getattr(self, name)
            ]
            if missing:
                raise ValueError(f"Missing required settings in production: {', '.join(missing)}")
        return self

    @property
    def cookies_secure(self) -> bool:
        """Secure cookies everywhere except plain-http local development (ADR-0033)."""
        return self.app_env == "production" or self.backend_url.startswith("https://")

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
    # Tests must never pick up a developer's real keys from .env (they would call the real API).
    if os.environ.get("APP_ENV") != "test":
        load_dotenv(PROJECT_ROOT / ".env")
    return Settings.from_env()
