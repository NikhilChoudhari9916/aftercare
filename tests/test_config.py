import pytest
from pydantic import ValidationError

from app.config import Settings

PRODUCTION_SECRETS = {
    "app_env": "production",
    "google_client_id": "id",
    "google_client_secret": "secret",
    "login_state_secret": "state",
}


def test_defaults_match_the_adrs():
    settings = Settings()
    assert settings.app_env == "development"
    assert settings.model_main == "claude-sonnet-5-5"
    assert settings.model_fast == "claude-haiku-5-5"
    assert settings.session_idle_hours == 12
    assert settings.session_max_days == 7
    assert settings.log_patient_text is False


def test_from_env_reads_uppercase_variables_and_converts_types(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SESSION_IDLE_HOURS", "3")
    monkeypatch.setenv("LOG_PATIENT_TEXT", "true")
    settings = Settings.from_env()
    assert settings.app_env == "test"
    assert settings.session_idle_hours == 3
    assert settings.log_patient_text is True


def test_logging_patient_text_is_allowed_in_development_and_test():
    assert Settings(app_env="development", log_patient_text=True).log_patient_text
    assert Settings(app_env="test", log_patient_text=True).log_patient_text


def test_logging_patient_text_is_refused_in_production():
    with pytest.raises(ValidationError, match="LOG_PATIENT_TEXT"):
        Settings(**PRODUCTION_SECRETS, log_patient_text=True)


@pytest.mark.parametrize(
    "missing", ["google_client_id", "google_client_secret", "login_state_secret"]
)
def test_production_requires_sign_in_secrets(missing):
    values = {**PRODUCTION_SECRETS, missing: ""}
    with pytest.raises(ValidationError, match=missing.upper()):
        Settings(**values)


def test_production_starts_when_everything_is_set():
    assert Settings(**PRODUCTION_SECRETS).app_env == "production"


def test_unknown_environment_name_is_rejected():
    with pytest.raises(ValidationError):
        Settings(app_env="staging")


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ({"app_env": "development"}, False),
        ({"app_env": "test"}, False),
        ({"app_env": "development", "backend_url": "https://api.example.com"}, True),
        (PRODUCTION_SECRETS, True),
    ],
)
def test_cookies_are_secure_in_production_and_whenever_the_backend_uses_https(values, expected):
    assert Settings(**values).cookies_secure is expected
