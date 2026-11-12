"""What the patient chose, as plain data, shared by the schedule and the plan."""

from datetime import date

from pydantic import BaseModel

from app.models import VisitStatus

# A field below is named "date", which would hide the type inside its own class body.
Day = date


class VisitChoice(BaseModel):
    status: VisitStatus
    date: Day | None = None
    time: str | None = None  # "HH:MM"
    call_on: Day | None = None


class Plan(BaseModel):
    """What the patient chose, by the ID of the confirmed item it belongs to (ADR-0042)."""

    medicines: dict[str, list[str]] = {}
    visits: dict[str, VisitChoice] = {}
