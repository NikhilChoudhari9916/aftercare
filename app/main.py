import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.auth.dependencies import check_origin
from app.auth.routes import router as auth_router
from app.config import get_settings
from app.db import get_engine, init_db

LOGIN_COOKIE_NAME = "aftercare_login"
LOGIN_COOKIE_SECONDS = 600


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db(get_engine())
    yield


def create_app() -> FastAPI:
    settings = get_settings()  # a bad configuration stops the app before it serves anything
    app = FastAPI(title="AfterCare", lifespan=lifespan, dependencies=[Depends(check_origin)])

    # Holds only the short Google login handshake (state, nonce, PKCE), never the real session.
    # In development a missing secret becomes a random per-process one, so a restart during
    # a login attempt just means signing in again.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.login_state_secret or secrets.token_urlsafe(32),
        session_cookie=LOGIN_COOKIE_NAME,
        max_age=LOGIN_COOKIE_SECONDS,
        same_site="lax",
        https_only=settings.cookies_secure,
    )
    app.include_router(auth_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
