"""The medicine schedule. Plain code, never the model (CLAUDE.md section 2, ADR-0006).

The rule that keeps this safe: a time is only ever worked out from words the papers use for
how often and when. Anything else is shown as written and the patient is asked to set the timing.
"""

import re
from datetime import date, time
from enum import StrEnum

from pydantic import BaseModel

from app.extraction.schema import ExtractedFollowUp, ExtractedMedication, MedStatus
from app.models import VisitStatus
from app.summary.choices import Day, Plan, VisitChoice
from app.summary.profile import ConfirmedProfile


class Slot(StrEnum):
    MORNING = "MORNING"
    MIDDAY = "MIDDAY"
    EVENING = "EVENING"
    BEDTIME = "BEDTIME"


# Everyday defaults. A reminder is a nudge, so these are easy to move in the calendar app.
SLOT_TIMES: dict[Slot, time] = {
    Slot.MORNING: time(8, 0),
    Slot.MIDDAY: time(13, 0),
    Slot.EVENING: time(18, 0),
    Slot.BEDTIME: time(21, 0),
}
SLOT_NAMES: dict[Slot, str] = {
    Slot.MORNING: "Morning",
    Slot.MIDDAY: "Midday",
    Slot.EVENING: "Evening",
    Slot.BEDTIME: "Bedtime",
}
SLOT_ORDER = tuple(SLOT_NAMES)
# The hour from which a time reads as midday, evening or bedtime (before MORNING_FROM: bedtime).
MIDDAY_FROM, EVENING_FROM, BEDTIME_FROM, MORNING_FROM = 12, 16, 20, 5


def part_of_day(hhmm: str) -> Slot:
    """Name for a clock time, so "07:30" and "08:00" both read as Morning."""
    hour = int(hhmm.split(":")[0])
    if hour >= BEDTIME_FROM or hour < MORNING_FROM:
        return Slot.BEDTIME
    if hour >= EVENING_FROM:
        return Slot.EVENING
    return Slot.MIDDAY if hour >= MIDDAY_FROM else Slot.MORNING


# Words in a frequency that mean "not every day": never turned into a daily reminder.
_NOT_DAILY = re.compile(
    r"every other|alternate|weekly|\bweek\b|monthly|every \d+ days|every (two|three) days"
)
_AS_NEEDED = re.compile(r"as needed|\bprn\b|if needed|when needed")

# How many times a day, by the words the papers use (abbreviations are already expanded).
_FOUR = re.compile(r"four times|4 times|\bqid\b")
_THREE = re.compile(r"three times|3 times|\btid\b|every 8 hours")
_TWICE = re.compile(r"twice|two times|2 times|\bbid\b|every 12 hours")
_ONCE = re.compile(
    r"once|one time|1 time|daily|every day|each day|every morning|every evening|each morning|"
    r"each evening|at bedtime|nightly|every night"
)

# Words that name part of the day.
_MENTIONS: dict[Slot, re.Pattern[str]] = {
    Slot.MORNING: re.compile(r"morning|breakfast|\ba\.?m\.?\b|on waking|wake up"),
    Slot.MIDDAY: re.compile(r"midday|noon|lunch|afternoon"),
    Slot.EVENING: re.compile(r"evening|dinner|supper|\bp\.?m\.?\b"),
    Slot.BEDTIME: re.compile(r"bedtime|bed time|at night|nightly|every night|before bed"),
}
_DEFAULT_SLOTS: dict[int, list[Slot]] = {
    2: [Slot.MORNING, Slot.EVENING],
    3: [Slot.MORNING, Slot.MIDDAY, Slot.EVENING],
    4: list(SLOT_ORDER),
}


def parse_slots(frequency: str | None, timing: str | None) -> list[Slot] | None:
    """The times of day a medicine is taken, or None when the words are not clear enough."""
    text = f"{frequency or ''} {timing or ''}".lower()
    if not text.strip() or _NOT_DAILY.search(text):
        return None

    mentioned = [slot for slot in SLOT_ORDER if _MENTIONS[slot].search(text)]
    for count, pattern in ((4, _FOUR), (3, _THREE), (2, _TWICE)):
        if pattern.search(text):
            # If the papers name exactly that many times of day, use those; else the defaults.
            return mentioned if len(mentioned) == count else _DEFAULT_SLOTS[count]
    if _ONCE.search(text) and len(mentioned) == 1:
        return mentioned
    return None


class MedicineLine(BaseModel):
    name: str
    other_names: list[str]
    dose: str | None
    how_often: str  # as the papers wrote it
    status: MedStatus
    end_date: date | None
    source_page: int
    # For the planning form (ADR-0042): the times in effect are the patient's, else a default.
    item_id: str = ""
    times: list[str] = []
    suggested_times: list[str] = []
    times_needed: int | None = (
        None  # how many times the papers clearly ask for; None = patient decides
    )
    chosen: bool = False


class DoseTime(BaseModel):
    slot: Slot
    label: str
    time: str  # "08:00"
    medicines: list[MedicineLine]


class FollowUpLine(BaseModel):
    item_id: str = ""
    what: str
    when: str  # as the papers wrote it
    with_whom: str | None
    # What the papers gave: booked_time, date_only, window (two times), or no_date.
    kind: str
    papers_date: Day | None
    papers_time: str | None
    # What the patient chose (None until they save a plan), and what the calendar will use.
    status: VisitStatus | None
    date: Day | None
    time: str | None  # "10:30"
    call_on: Day | None
    chosen: bool
    in_calendar: bool
    source_page: int


class Schedule(BaseModel):
    version: int
    daily: list[DoseTime]
    needs_timing: list[MedicineLine]
    plan_medicines: list[MedicineLine]  # every medicine the patient can choose reminder times for
    as_needed: list[MedicineLine]
    stopped: list[MedicineLine]
    follow_ups: list[FollowUpLine]


def _end_date(text: str | None) -> date | None:
    try:
        return date.fromisoformat(text) if text else None
    except ValueError:
        return None


def medicine_line(medicine: ExtractedMedication, item_id: str = "") -> MedicineLine:
    written = " ".join(part for part in (medicine.frequency, medicine.timing) if part)
    return MedicineLine(
        name=medicine.name_as_written,
        other_names=medicine.other_names,
        dose=medicine.dose,
        how_often=written,
        status=medicine.status,
        end_date=_end_date(medicine.end_date),
        source_page=medicine.source_page,
        item_id=item_id,
    )


def is_as_needed(medicine: ExtractedMedication) -> bool:
    written = f"{medicine.frequency or ''} {medicine.timing or ''}".lower()
    return (
        medicine.as_needed
        or medicine.status == MedStatus.AS_NEEDED
        or bool(_AS_NEEDED.search(written))
    )


# --- follow-up dates ---------------------------------------------------------------------

_MONTHS = {
    name: number
    for number, names in enumerate(
        (
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may",),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sept", "sep"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        ),
        start=1,
    )
    for name in names
}
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_US_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_WORD_DATE = re.compile(r"\b([a-z]{3,9})\.? (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})\b", re.IGNORECASE)
_CLOCK = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\b\.?", re.IGNORECASE)


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_follow_up_date(text: str) -> date | None:
    """A date the papers wrote out in full, or None. Never a guess ("next week" stays text)."""
    if match := _ISO_DATE.search(text):
        return _safe_date(int(match[1]), int(match[2]), int(match[3]))
    if match := _US_DATE.search(text):
        return _safe_date(int(match[3]), int(match[1]), int(match[2]))
    for match in _WORD_DATE.finditer(text):
        month = _MONTHS.get(match[1].lower())
        if month:
            return _safe_date(int(match[3]), month, int(match[2]))
    return None


def parse_follow_up_time(text: str) -> time | None:
    """One clock time with a.m. or p.m. Otherwise the visit becomes an all-day calendar entry.

    Two times ("any time 7 a.m. to 4 p.m.") are a window, not an appointment, so no time is picked.
    """
    matches = list(_CLOCK.finditer(text))
    if len(matches) != 1:
        return None
    match = matches[0]
    hour, minute = int(match[1]), int(match[2] or 0)
    if not (1 <= hour <= 12 and minute < 60):
        return None
    if match[3].lower() == "p" and hour != 12:
        hour += 12
    if match[3].lower() == "a" and hour == 12:
        hour = 0
    return time(hour, minute)


def count_clock_times(text: str) -> int:
    return len(list(_CLOCK.finditer(text)))


def visit_kind(day: date | None, clock_times: int) -> str:
    if day is None:
        return "no_date"
    if clock_times == 1:
        return "booked_time"
    return "date_only" if clock_times == 0 else "window"


def follow_up_line(
    follow_up: ExtractedFollowUp, item_id: str = "", choice: VisitChoice | None = None
) -> FollowUpLine:
    papers_day = parse_follow_up_date(follow_up.when)
    papers_clock = parse_follow_up_time(follow_up.when) if papers_day else None
    papers_time = papers_clock.strftime("%H:%M") if papers_clock else None

    if choice is None:
        status, day, clock, call_on = None, papers_day, papers_time, None
        in_calendar = day is not None
    elif choice.status == VisitStatus.BOOKED:
        status, day, clock, call_on = choice.status, choice.date, choice.time, None
        in_calendar = True
    else:
        status, day, clock, call_on = choice.status, None, None, choice.call_on
        in_calendar = call_on is not None
    return FollowUpLine(
        item_id=item_id,
        what=follow_up.what,
        when=follow_up.when,
        with_whom=follow_up.with_whom,
        kind=visit_kind(papers_day, count_clock_times(follow_up.when) if papers_day else 0),
        papers_date=papers_day,
        papers_time=papers_time,
        status=status,
        date=day,
        time=clock,
        call_on=call_on,
        chosen=choice is not None,
        in_calendar=in_calendar,
        source_page=follow_up.source_page,
    )


# --- the schedule ------------------------------------------------------------------------


def _item_id(ids: list[str], index: int) -> str:
    return ids[index] if index < len(ids) else ""


def build_schedule(profile: ConfirmedProfile, plan: Plan | None = None) -> Schedule:
    """Doses grouped by their exact time. The patient's chosen times win over the defaults."""
    plan = plan or Plan()
    by_time: dict[str, list[MedicineLine]] = {}
    needs_timing: list[MedicineLine] = []
    plan_medicines: list[MedicineLine] = []
    as_needed: list[MedicineLine] = []
    stopped: list[MedicineLine] = []

    for index, medicine in enumerate(profile.medicines):
        item_id = _item_id(profile.medicine_ids, index)
        line = medicine_line(medicine, item_id)
        if medicine.status == MedStatus.STOPPED:
            stopped.append(line)
        elif is_as_needed(medicine):
            as_needed.append(line)
        else:
            slots = parse_slots(medicine.frequency, medicine.timing)
            suggested = [SLOT_TIMES[slot].strftime("%H:%M") for slot in slots or []]
            chosen = plan.medicines.get(item_id)
            times = suggested if chosen is None else chosen
            line = line.model_copy(
                update={
                    "times": times,
                    "suggested_times": suggested,
                    "times_needed": len(slots) if slots else None,
                    "chosen": chosen is not None,
                }
            )
            plan_medicines.append(line)
            if not times:
                needs_timing.append(line)
            for value in times:
                by_time.setdefault(value, []).append(line)

    daily = [
        DoseTime(
            slot=part_of_day(value),
            label=SLOT_NAMES[part_of_day(value)],
            time=value,
            medicines=by_time[value],
        )
        for value in sorted(by_time)
    ]
    follow_ups = [
        follow_up_line(
            follow_up,
            _item_id(profile.follow_up_ids, index),
            plan.visits.get(_item_id(profile.follow_up_ids, index)),
        )
        for index, follow_up in enumerate(profile.follow_ups)
    ]
    return Schedule(
        version=profile.version,
        daily=daily,
        needs_timing=needs_timing,
        plan_medicines=plan_medicines,
        as_needed=as_needed,
        stopped=stopped,
        follow_ups=follow_ups,
    )
