import json
from datetime import date, datetime

from pydantic import BaseModel
from sqlmodel import Session, select

from app.extraction.schema import (
    ExtractedContact,
    ExtractedDietLimit,
    ExtractedFollowUp,
    ExtractedMedication,
    ExtractedWarningSign,
)
from app.models import ProfileItem, ProfileStatus, ProfileVersion


class ConfirmedProfile(BaseModel):
    """What the patient confirmed, and nothing else. Summary, schedule and calendar read this."""

    version_id: str
    version: int
    confirmed_at: datetime | None
    discharge_date: date | None
    medicines: list[ExtractedMedication]
    warning_signs: list[ExtractedWarningSign]
    follow_ups: list[ExtractedFollowUp]
    care_team: list[ExtractedContact]
    diet_limits: list[ExtractedDietLimit]


def _discharge_date(text: str | None) -> date | None:
    try:
        return date.fromisoformat(text) if text else None
    except ValueError:
        return None  # the model wrote something that is not a date; show nothing rather than guess


def load_confirmed_profile(db: Session, patient_id: str) -> ConfirmedProfile | None:
    """The newest confirmed version for this patient, or None if nothing is confirmed yet."""
    version = db.exec(
        select(ProfileVersion)
        .where(
            ProfileVersion.patient_id == patient_id,
            ProfileVersion.status == ProfileStatus.CONFIRMED,
        )
        .order_by(ProfileVersion.version.desc())
    ).first()
    if version is None:
        return None

    items = db.exec(
        select(ProfileItem)
        .where(
            ProfileItem.profile_version_id == version.id,
            ProfileItem.patient_id == patient_id,
            ProfileItem.confirmed == True,  # noqa: E712  (SQL comparison, not a Python truth test)
        )
        .order_by(ProfileItem.section, ProfileItem.position)
    ).all()

    def section(name: str) -> list[dict]:
        return [json.loads(item.data) for item in items if item.section == name]

    return ConfirmedProfile(
        version_id=version.id,
        version=version.version,
        confirmed_at=version.confirmed_at,
        discharge_date=_discharge_date(version.discharge_date),
        medicines=section("medicines"),
        warning_signs=section("warning_signs"),
        follow_ups=section("follow_ups"),
        care_team=section("care_team"),
        diet_limits=section("diet_limits"),
    )
