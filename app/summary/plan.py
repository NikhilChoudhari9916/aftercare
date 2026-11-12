"""The patient's own plan: reminder times for each medicine, and what they will do about each visit.

The papers say what to take and which visits are needed. *When* the patient takes a medicine and
*how* they handle a visit are their choices (ADR-0042). They are stored apart from the papers
and checked here by plain code, never by the model.
"""

import json
import re
from datetime import date

from pydantic import BaseModel
from sqlmodel import Session, select

from app.extraction.schema import MedStatus
from app.models import MedicinePlan, VisitPlan, VisitStatus, utc_now
from app.summary.choices import Day, Plan, VisitChoice
from app.summary.profile import ConfirmedProfile
from app.summary.schedule import is_as_needed, parse_slots

MAX_TIMES_PER_MEDICINE = 6
EARLIEST_YEAR, LATEST_YEAR = 2000, 2100
_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class PlanError(Exception):
    """The plan cannot be saved. The message is plain language for the patient."""


class MedicineTimesIn(BaseModel):
    item_id: str
    times: list[str]


class VisitIn(BaseModel):
    item_id: str
    status: VisitStatus
    date: Day | None = None
    time: str | None = None
    call_on: Day | None = None


class PlanIn(BaseModel):
    medicines: list[MedicineTimesIn]
    visits: list[VisitIn]


def times_needed(medicine) -> int | None:
    """How many times a day the papers clearly ask for, or None when the patient decides."""
    slots = parse_slots(medicine.frequency, medicine.timing)
    return len(slots) if slots else None


def is_plannable(medicine) -> bool:
    """STOPPED and AS NEEDED medicines never get reminder times."""
    return medicine.status != MedStatus.STOPPED and not is_as_needed(medicine)


def _check_time(value: str, what: str) -> str:
    if not _HHMM.match(value):
        raise PlanError(f"{what}: please pick a time like 8:30 AM.")
    return value


def _check_day(value: date, what: str) -> date:
    if not EARLIEST_YEAR <= value.year <= LATEST_YEAR:
        raise PlanError(f"{what}: that date does not look right.")
    return value


def _check_ids(given: list[str], expected: list[str], what: str) -> None:
    if len(set(given)) != len(given) or set(given) != set(expected):
        raise PlanError(f"Please choose something for every {what}.")


def validate_plan(profile: ConfirmedProfile, plan: PlanIn, *, today: date) -> Plan:
    """Return the checked plan, or raise PlanError. Every rule here is plain code."""
    plannable = {
        item_id: medicine
        for item_id, medicine in zip(profile.medicine_ids, profile.medicines, strict=False)
        if is_plannable(medicine)
    }
    _check_ids([m.item_id for m in plan.medicines], list(plannable), "medicine")
    _check_ids([v.item_id for v in plan.visits], profile.follow_up_ids, "visit")

    medicines: dict[str, list[str]] = {}
    for entry in plan.medicines:
        medicine = plannable[entry.item_id]
        name = medicine.name_as_written
        if len(entry.times) > MAX_TIMES_PER_MEDICINE:  # before looping over a huge list
            raise PlanError(f"{name}: please pick at most {MAX_TIMES_PER_MEDICINE} times.")
        times = sorted({_check_time(value, name) for value in entry.times})
        if len(times) != len(entry.times):
            raise PlanError(f"{name}: each reminder needs a different time.")
        needed = times_needed(medicine)
        if needed is not None and len(times) != needed:
            raise PlanError(
                f"{name}: your papers say {needed} time(s) a day, so please pick {needed}."
            )
        if len(times) > MAX_TIMES_PER_MEDICINE:
            raise PlanError(f"{name}: please pick at most {MAX_TIMES_PER_MEDICINE} times.")
        medicines[entry.item_id] = times

    visits: dict[str, VisitChoice] = {}
    names = dict(zip(profile.follow_up_ids, profile.follow_ups, strict=False))
    for entry in plan.visits:
        what = names[entry.item_id].what
        if entry.status == VisitStatus.BOOKED:
            if entry.date is None:
                raise PlanError(f"{what}: please pick the date of the visit.")
            if entry.call_on is not None:
                raise PlanError(f"{what}: a booked visit does not need a reminder to call.")
            choice = VisitChoice(
                status=entry.status,
                date=_check_day(entry.date, what),
                time=_check_time(entry.time, what) if entry.time else None,
            )
        else:
            if entry.date is not None or entry.time:
                raise PlanError(f"{what}: choose booked if you have a date, or not booked yet.")
            if entry.call_on is not None and entry.call_on < today:
                raise PlanError(f"{what}: please pick today or a later day to be reminded.")
            choice = VisitChoice(
                status=entry.status,
                call_on=_check_day(entry.call_on, what) if entry.call_on else None,
            )
        visits[entry.item_id] = choice
    return Plan(medicines=medicines, visits=visits)


def load_plan(db: Session, patient_id: str, profile: ConfirmedProfile) -> Plan:
    """The saved plan for this patient's current confirmed papers (older plans are ignored)."""
    medicines = {
        row.profile_item_id: json.loads(row.times)
        for row in db.exec(
            select(MedicinePlan).where(
                MedicinePlan.patient_id == patient_id,
                MedicinePlan.profile_item_id.in_(profile.medicine_ids),
            )
        ).all()
    }
    visits = {
        row.profile_item_id: VisitChoice(
            status=row.status, date=row.planned_date, time=row.planned_time, call_on=row.call_on
        )
        for row in db.exec(
            select(VisitPlan).where(
                VisitPlan.patient_id == patient_id,
                VisitPlan.profile_item_id.in_(profile.follow_up_ids),
            )
        ).all()
    }
    return Plan(medicines=medicines, visits=visits)


def save_plan(db: Session, patient_id: str, profile: ConfirmedProfile, plan: Plan) -> None:
    """Replace this patient's plan for the current papers, all at once."""
    for model, ids in ((MedicinePlan, profile.medicine_ids), (VisitPlan, profile.follow_up_ids)):
        for row in db.exec(
            select(model).where(model.patient_id == patient_id, model.profile_item_id.in_(ids))
        ).all():
            db.delete(row)
    db.flush()
    now = utc_now()
    for item_id, times in plan.medicines.items():
        db.add(
            MedicinePlan(
                patient_id=patient_id,
                profile_item_id=item_id,
                times=json.dumps(times),
                updated_at=now,
            )
        )
    for item_id, choice in plan.visits.items():
        db.add(
            VisitPlan(
                patient_id=patient_id,
                profile_item_id=item_id,
                status=choice.status,
                planned_date=choice.date,
                planned_time=choice.time,
                call_on=choice.call_on,
                updated_at=now,
            )
        )
    db.commit()
