import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_app_refuses_to_start_with_unsafe_production_settings(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LOG_PATIENT_TEXT", "1")
    with pytest.raises(ValueError, match="LOG_PATIENT_TEXT"), TestClient(app):
        pass
