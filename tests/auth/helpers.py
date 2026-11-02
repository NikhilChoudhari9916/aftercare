from typing import Any

from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, func, select

from app.auth.google import LoginFailed
from app.config import Settings

UI_URL = "http://localhost:8080"
BACKEND_URL = "http://localhost:8000"


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "test",
        "google_client_id": "client-id",
        "google_client_secret": "client-secret",
        "login_state_secret": "state-secret",
        "ui_url": UI_URL,
        "backend_url": BACKEND_URL,
    }
    values.update(overrides)
    return Settings(**values)


class FakeProvider:
    """Stands in for Google: no network, and the test decides who just signed in."""

    def __init__(self) -> None:
        self.claims: dict[str, Any] | None = None
        self.fail = False

    async def start_login(self, request: Request, redirect_uri: str) -> Response:
        return RedirectResponse("https://accounts.example/authorize", status_code=303)

    async def finish_login(self, request: Request) -> dict[str, Any]:
        if self.fail or self.claims is None:
            raise LoginFailed("fake failure")
        return dict(self.claims)


def sign_in(
    client: TestClient,
    provider: FakeProvider,
    *,
    sub: str = "google-sub-1",
    email: str = "ada@example.com",
    name: str = "Ada Lovelace",
    verified: Any = True,
):
    provider.claims = {"sub": sub, "email": email, "name": name, "email_verified": verified}
    return client.get("/auth/callback")


def count(db: Session, model: type[SQLModel]) -> int:
    return db.exec(select(func.count()).select_from(model)).one()


def session_cookie(response) -> str | None:
    for header in response.headers.get_list("set-cookie"):
        if header.startswith("aftercare_session="):
            return header
    return None
