from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.auth.dependencies import DbSession, require_access
from app.models import PatientAccess, Role
from app.summary.calendar_export import TitleStyle, build_ics
from app.summary.profile import ConfirmedProfile, load_confirmed_profile
from app.summary.schedule import Schedule, build_schedule
from app.summary.summary import Summary, build_summary

router = APIRouter()

# An aide may read all three (ADR-0032), so owner and aide are both allowed here.
Reader = Annotated[PatientAccess, Depends(require_access(Role.OWNER, Role.AIDE))]


def _confirmed(db: DbSession, patient_id: str) -> ConfirmedProfile:
    profile = load_confirmed_profile(db, patient_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="The papers have not been confirmed yet")
    return profile


@router.get("/patients/{patient_id}/summary", response_model=Summary)
def get_summary(patient_id: str, _access: Reader, db: DbSession) -> Summary:
    return build_summary(_confirmed(db, patient_id))


@router.get("/patients/{patient_id}/schedule", response_model=Schedule)
def get_schedule(patient_id: str, _access: Reader, db: DbSession) -> Schedule:
    return build_schedule(_confirmed(db, patient_id))


@router.get("/patients/{patient_id}/schedule.ics")
def get_calendar(
    patient_id: str,
    _access: Reader,
    db: DbSession,
    titles: Annotated[TitleStyle, Query()] = "private",
) -> Response:
    profile = _confirmed(db, patient_id)
    ics = build_ics(
        build_schedule(profile),
        patient_id,
        today=date.today(),
        now=datetime.now(UTC),
        discharge_date=profile.discharge_date,
        titles=titles,
    )
    return Response(
        content=ics,
        media_type="text/calendar",
        headers={
            "Content-Disposition": 'attachment; filename="aftercare-reminders.ics"',
            "Cache-Control": "no-store",
        },
    )
