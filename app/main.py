import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlmodel import Session
from starlette.middleware.sessions import SessionMiddleware

from app.auth.dependencies import check_origin
from app.auth.routes import router as auth_router
from app.config import get_settings
from app.db import get_engine, init_db
from app.documents.routes import router as documents_router
from app.jobs.runner import ThreadJobRunner, mark_interrupted_jobs

LOGIN_COOKIE_NAME = "aftercare_login"
LOGIN_COOKIE_SECONDS = 600


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = get_engine()
    init_db(engine)
    with Session(engine) as db:
        mark_interrupted_jobs(db)  # work from before a restart is gone, so say so (ADR-0034)
    runner = ThreadJobRunner(get_settings().job_workers)
    app.state.job_runner = runner
    yield
    runner.shutdown()


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
    app.include_router(documents_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
