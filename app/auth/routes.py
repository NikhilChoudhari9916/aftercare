from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.dependencies import AppSettings, CurrentUser, DbSession
from app.auth.google import IdentityProvider, LoginFailed, get_identity_provider
from app.auth.session import (
    COOKIE_NAME,
    clear_session_cookie,
    create_session,
    end_session,
    set_session_cookie,
)
from app.config import LOCAL_HOSTS, Settings
from app.models import (
    AccessEvent,
    AccessEventKind,
    AccessStatus,
    Patient,
    PatientAccess,
    Role,
    User,
    utc_now,
)

router = APIRouter()

MAX_DISPLAY_NAME_LENGTH = 200

# Fixed synthetic people for the test login. "dev:" can never be a real Google subject ID
# (those are numbers) and ".test" can never be a real email domain.
DEV_PEOPLE = {
    "alex": ("dev:alex", "alex@aftercare.test", "Alex (test patient)"),
    "sam": ("dev:sam", "sam@aftercare.test", "Sam (second test patient)"),
}

Provider = Annotated[IdentityProvider, Depends(get_identity_provider)]


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str


class PatientRef(BaseModel):
    id: str
    role: Role


class MeResponse(BaseModel):
    user: UserOut
    patients: list[PatientRef]


def safe_next(value: str | None) -> str:
    """Only a plain path on our own site is allowed, so sign-in can't redirect elsewhere."""
    if not value or not value.startswith("/") or value.startswith("//"):
        return "/"
    if "\\" in value or any(ord(char) < 32 for char in value):
        return "/"
    return value


def find_or_create_user(db: Session, *, sub: str, email: str, display_name: str) -> User:
    """Look the user up by Google's subject ID, never by email. First sign-in creates a patient."""
    user = db.exec(select(User).where(User.google_sub == sub)).first()
    if user is not None:
        if (user.email, user.display_name) != (email, display_name):
            user.email, user.display_name = email, display_name
            db.add(user)
            db.commit()
        return user

    user = User(google_sub=sub, email=email, display_name=display_name)
    patient = Patient(owner_user_id=user.id)
    # Flush in order: with no declared relationships, SQLAlchemy would not
    # promise the user row exists before the patient row that points to it.
    db.add(user)
    db.flush()
    db.add(patient)
    db.flush()
    db.add(PatientAccess(patient_id=patient.id, user_id=user.id, role=Role.OWNER))
    db.add(
        AccessEvent(kind=AccessEventKind.PATIENT_CREATED, patient_id=patient.id, user_id=user.id)
    )
    db.commit()
    return user


@router.get("/auth/login")
async def login(
    request: Request,
    settings: AppSettings,
    provider: Provider,
    next_path: Annotated[str, Query(alias="next")] = "/",
) -> Response:
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")
    request.session["next"] = safe_next(next_path)
    redirect_uri = f"{settings.backend_url.rstrip('/')}/auth/callback"
    return await provider.start_login(request, redirect_uri)


@router.get("/auth/callback")
async def callback(
    request: Request, db: DbSession, settings: AppSettings, provider: Provider
) -> Response:
    ui = settings.ui_url.rstrip("/")
    try:
        claims = await provider.finish_login(request)
    except LoginFailed:
        return RedirectResponse(f"{ui}/?error=sign_in_failed", status_code=303)

    sub, email = claims.get("sub"), claims.get("email")
    if not sub or not email or claims.get("email_verified") is not True:
        return RedirectResponse(f"{ui}/?error=email_not_verified", status_code=303)

    display_name = (claims.get("name") or email)[:MAX_DISPLAY_NAME_LENGTH]
    user = find_or_create_user(db, sub=sub, email=email, display_name=display_name)
    return start_session(request, db, settings, user, safe_next(request.session.pop("next", "/")))


def start_session(
    request: Request, db: Session, settings: Settings, user: User, next_path: str
) -> Response:
    """Shared by every way of signing in, so all of them get the same cookie and session rules."""
    old_token = request.cookies.get(COOKIE_NAME)
    if old_token:  # always issue a fresh token on sign-in
        end_session(db, old_token)
    token = create_session(db, user, settings)
    response = RedirectResponse(settings.ui_url.rstrip("/") + next_path, status_code=303)
    set_session_cookie(response, token, settings)
    return response


@router.post("/auth/dev-login")
def dev_login(
    request: Request,
    db: DbSession,
    settings: AppSettings,
    persona: Annotated[str, Form()] = "alex",
) -> Response:
    """Sign in a fixed synthetic person on a developer's own machine only (ADR-0037)."""
    # 404, not 403: when this is off, the route should look like it does not exist.
    if not settings.dev_login or request.url.hostname not in LOCAL_HOSTS:
        raise HTTPException(status_code=404, detail="Not found")
    if persona not in DEV_PEOPLE:
        raise HTTPException(status_code=422, detail="Unknown test person")
    sub, email, name = DEV_PEOPLE[persona]
    user = find_or_create_user(db, sub=sub, email=email, display_name=name)
    return start_session(request, db, settings, user, "/")


@router.post("/auth/logout")
def logout(request: Request, db: DbSession, settings: AppSettings) -> Response:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        end_session(db, token)
    response = RedirectResponse(settings.ui_url, status_code=303)
    clear_session_cookie(response, settings)
    return response


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser, db: DbSession, response: Response) -> MeResponse:
    response.headers["Cache-Control"] = "no-store"
    now = utc_now()
    accesses = db.exec(
        select(PatientAccess).where(
            PatientAccess.user_id == user.id, PatientAccess.status == AccessStatus.ACTIVE
        )
    ).all()
    patients = [
        PatientRef(id=access.patient_id, role=access.role)
        for access in accesses
        if access.expires_at is None or access.expires_at > now
    ]
    return MeResponse(
        user=UserOut(id=user.id, email=user.email, display_name=user.display_name),
        patients=patients,
    )
