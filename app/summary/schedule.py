"""The medicine schedule. Plain code, never the model (CLAUDE.md section 2, ADR-0006).

The rule that keeps this safe: a time is only ever worked out from words the papers use for
how often and when. Anything else is shown as written and the patient is asked to set the timing.
"""

import re
from datetime import date, time
from enum import StrEnum

from pydantic import BaseModel

from app.extraction.schema import ExtractedFollowUp, ExtractedMedication, MedStatus
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


class DoseTime(BaseModel):
    slot: Slot
    label: str
    time: str  # "08:00"
    medicines: list[MedicineLine]


class FollowUpLine(BaseModel):
    what: str
    when: str  # as the papers wrote it
    with_whom: str | None
    date: date | None
    time: str | None  # "10:30", only when the papers give a time
    in_calendar: bool
    source_page: int


class Schedule(BaseModel):
    version: int
    daily: list[DoseTime]
    needs_timing: list[MedicineLine]
    as_needed: list[MedicineLine]
    stopped: list[MedicineLine]
    follow_ups: list[FollowUpLine]


def _end_date(text: str | None) -> date | None:
    try:
        return date.fromisoformat(text) if text else None
    except ValueError:
        return None


def medicine_line(medicine: ExtractedMedication) -> MedicineLine:
    written = " ".join(part for part in (medicine.frequency, medicine.timing) if part)
    return MedicineLine(
        name=medicine.name_as_written,
        other_names=medicine.other_names,
        dose=medicine.dose,
        how_often=written,
        status=medicine.status,
        end_date=_end_date(medicine.end_date),
        source_page=medicine.source_page,
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


def follow_up_line(follow_up: ExtractedFollowUp) -> FollowUpLine:
    day = parse_follow_up_date(follow_up.when)
    clock = parse_follow_up_time(follow_up.when) if day else None
    return FollowUpLine(
        what=follow_up.what,
        when=follow_up.when,
        with_whom=follow_up.with_whom,
        date=day,
        time=clock.strftime("%H:%M") if clock else None,
        in_calendar=day is not None,
        source_page=follow_up.source_page,
    )


# --- the schedule ------------------------------------------------------------------------


def build_schedule(profile: ConfirmedProfile) -> Schedule:
    by_slot: dict[Slot, list[MedicineLine]] = {slot: [] for slot in SLOT_ORDER}
    needs_timing: list[MedicineLine] = []
    as_needed: list[MedicineLine] = []
    stopped: list[MedicineLine] = []

    for medicine in profile.medicines:
        line = medicine_line(medicine)
        if medicine.status == MedStatus.STOPPED:
            stopped.append(line)
        elif is_as_needed(medicine):
            as_needed.append(line)
        else:
            slots = parse_slots(medicine.frequency, medicine.timing)
            if slots is None:
                needs_timing.append(line)
            for slot in slots or []:
                by_slot[slot].append(line)

    daily = [
        DoseTime(
            slot=slot,
            label=SLOT_NAMES[slot],
            time=SLOT_TIMES[slot].strftime("%H:%M"),
            medicines=lines,
        )
        for slot, lines in by_slot.items()
        if lines
    ]
    return Schedule(
        version=profile.version,
        daily=daily,
        needs_timing=needs_timing,
        as_needed=as_needed,
        stopped=stopped,
        follow_ups=[follow_up_line(follow_up) for follow_up in profile.follow_ups],
    )
