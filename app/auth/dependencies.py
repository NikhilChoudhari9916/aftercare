from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select

from app.auth.session import COOKIE_NAME, get_session_user
from app.config import Settings, get_settings
from app.db import get_session
from app.models import (
    AccessEvent,
    AccessEventKind,
    AccessStatus,
    PatientAccess,
    Role,
    User,
    utc_now,
)

STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

DbSession = Annotated[Session, Depends(get_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def check_origin(request: Request, settings: AppSettings) -> None:
    """Reject a browser request that changes data when it comes from an unexpected site."""
    if request.method not in STATE_CHANGING_METHODS:
        return
    origin = request.headers.get("origin")
    if origin is None:  # not a browser (for example the UI server calling us)
        return
    allowed = {settings.ui_url.rstrip("/"), settings.backend_url.rstrip("/")}
    if origin.rstrip("/") not in allowed:
        raise HTTPException(status_code=403, detail="Origin not allowed")


def current_user(request: Request, db: DbSession, settings: AppSettings) -> User:
    token = request.cookies.get(COOKIE_NAME)
    user = get_session_user(db, token, settings) if token else None
    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def _record_denied(db: Session, user: User, patient_id: str) -> None:
    db.add(AccessEvent(kind=AccessEventKind.DENIED, patient_id=patient_id, user_id=user.id))
    db.commit()


def require_access(*allowed_roles: Role) -> Callable[..., PatientAccess]:
    """Dependency for routes with a `patient_id` path parameter.

    No access at all is a 404 (so patient IDs can't be probed); the wrong role is a 403.
    Every denial is recorded as an access event, with IDs only.
    """

    def dependency(patient_id: str, user: CurrentUser, db: DbSession) -> PatientAccess:
        access = db.exec(
            select(PatientAccess).where(
                PatientAccess.patient_id == patient_id,
                PatientAccess.user_id == user.id,
                PatientAccess.status == AccessStatus.ACTIVE,
            )
        ).first()
        expired = access is not None and access.expires_at is not None
        expired = expired and access.expires_at <= utc_now()
        if access is None or expired:
            _record_denied(db, user, patient_id)
            raise HTTPException(status_code=404, detail="Not found")
        if access.role not in allowed_roles:
            _record_denied(db, user, patient_id)
            raise HTTPException(status_code=403, detail="Not allowed")
        return access

    return dependency
