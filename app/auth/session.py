import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import Response
from sqlmodel import Session, select

from app.config import Settings
from app.models import LoginSession, User, utc_now

COOKIE_NAME = "aftercare_session"
LAST_SEEN_UPDATE_SECONDS = 60


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User, settings: Settings, now: datetime | None = None) -> str:
    """Start a session and return the raw token. Only its hash is stored."""
    now = now or utc_now()
    token = secrets.token_urlsafe(32)
    db.add(
        LoginSession(
            token_hash=hash_token(token),
            user_id=user.id,
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(days=settings.session_max_days),
        )
    )
    db.commit()
    return token


def get_session_user(
    db: Session, token: str, settings: Settings, now: datetime | None = None
) -> User | None:
    """Return the signed-in user, or None if the session is unknown or has expired."""
    now = now or utc_now()
    row = db.exec(select(LoginSession).where(LoginSession.token_hash == hash_token(token))).first()
    if row is None:
        return None

    idle_limit = row.last_seen_at + timedelta(hours=settings.session_idle_hours)
    if now >= row.expires_at or now >= idle_limit:
        db.delete(row)
        db.commit()
        return None

    if (now - row.last_seen_at).total_seconds() >= LAST_SEEN_UPDATE_SECONDS:
        row.last_seen_at = now
        db.add(row)
        db.commit()
    return db.get(User, row.user_id)


def end_session(db: Session, token: str) -> None:
    row = db.exec(select(LoginSession).where(LoginSession.token_hash == hash_token(token))).first()
    if row is not None:
        db.delete(row)
        db.commit()


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_max_days * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.cookies_secure,
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        COOKIE_NAME,
        httponly=True,
        samesite="lax",
        secure=settings.cookies_secure,
        path="/",
    )
