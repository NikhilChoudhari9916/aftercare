"""The calendar (.ics) file. Plain code, built from the schedule (ADR-0040).

- Times are "floating": no time zone is written, so every calendar app shows them in the
  phone's own local time. That is what a patient who travels or changes phones expects.
- Titles are private by default ("Evening medicines"); the patient can ask for detailed ones.
- Medicines that are STOPPED or AS NEEDED never get an event, and neither does one whose
  timing the papers do not make clear (the schedule page asks the patient to set it).
- Each daily reminder runs for the next REMINDER_DAYS days, or until the medicine's end date.
- Times are the patient's own choices when they have saved a plan (ADR-0042), else the defaults.
- A visit the patient has not booked yet becomes an all-day "call to book" reminder on the day
  they chose. The app only reminds; it never books or contacts anyone.
"""

import hashlib
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Literal

from icalendar import Alarm, Calendar, Event, vRecur

from app.models import VisitStatus
from app.summary.schedule import SLOT_NAMES, FollowUpLine, MedicineLine, Schedule

TitleStyle = Literal["private", "detailed"]
REMINDER_DAYS = 30
VISIT_MINUTES = 60
PRODUCT_ID = "-//AfterCare//Reminders//EN"


def _uid(patient_id: str, key: str) -> str:
    """Stable, so importing a newer file updates the same events. Hashed: no patient ID leaks."""
    digest = hashlib.sha256(f"{patient_id}:{key}".encode()).hexdigest()[:24]
    return f"{digest}@aftercare.local"


def _medicine_text(line: MedicineLine) -> str:
    return " ".join(part for part in (line.name, line.dose) if part)


def _days_left(start: date, end_date: date | None) -> int:
    window_end = start + timedelta(days=REMINDER_DAYS - 1)
    last_day = min(window_end, end_date) if end_date else window_end
    return (last_day - start).days + 1


def _clock(hhmm: str) -> time:
    return datetime.strptime(hhmm, "%H:%M").time()


def _alarm() -> Alarm:
    alarm = Alarm()
    alarm.add("action", "DISPLAY")
    alarm.add("description", "Reminder")
    alarm.add("trigger", timedelta(0))
    return alarm


def _medicine_events(
    schedule: Schedule, patient_id: str, start: date, titles: TitleStyle, now: datetime
) -> list[Event]:
    events = []
    for dose_time in schedule.daily:
        # Medicines with different end dates need their own repeat length, so group by end date.
        groups: dict[date | None, list[MedicineLine]] = defaultdict(list)
        for line in dose_time.medicines:
            groups[line.end_date].append(line)

        for end_date, lines in groups.items():
            days = _days_left(start, end_date)
            if days < 1:
                continue  # the course is already over
            begin = datetime.combine(start, _clock(dose_time.time))
            event = Event()
            key = f"{dose_time.time}:{end_date}"
            event.add("uid", _uid(patient_id, key))
            event.add("dtstamp", now)
            event.add("dtstart", begin)
            event.add("dtend", begin + timedelta(minutes=15))
            event.add("rrule", vRecur({"FREQ": "DAILY", "COUNT": days}))
            event.add("sequence", schedule.version)
            if titles == "detailed":
                event.add(
                    "summary",
                    f"{SLOT_NAMES[dose_time.slot]}: "
                    + ", ".join(_medicine_text(line) for line in lines),
                )
                event.add("description", "Check your AfterCare schedule for details.")
            else:
                event.add("summary", f"{SLOT_NAMES[dose_time.slot]} medicines")
                event.add("description", "Open AfterCare to see which medicines.")
            event.add_component(_alarm())
            events.append(event)
    return events


def _follow_up_event(
    follow_up: FollowUpLine,
    index: int,
    patient_id: str,
    titles: TitleStyle,
    now: datetime,
    version: int,
) -> Event:
    event = Event()
    event.add("uid", _uid(patient_id, f"visit:{index}"))
    event.add("dtstamp", now)
    event.add("sequence", version)
    if follow_up.time:
        begin = datetime.combine(follow_up.date, _clock(follow_up.time))
        event.add("dtstart", begin)
        event.add("dtend", begin + timedelta(minutes=VISIT_MINUTES))
    else:
        event.add("dtstart", follow_up.date)  # all day: the papers gave no time
        event.add("dtend", follow_up.date + timedelta(days=1))
    if titles == "detailed":
        who = f" with {follow_up.with_whom}" if follow_up.with_whom else ""
        event.add("summary", f"{follow_up.what}{who}")
        said = (
            "You planned this in AfterCare."
            if follow_up.chosen
            else f"Your papers say: {follow_up.when}"
        )
        event.add("description", said)
    else:
        event.add("summary", "Medical appointment")
        event.add("description", "Open AfterCare for details.")
    event.add_component(_alarm())
    return event


def _call_reminder_event(
    follow_up: FollowUpLine,
    index: int,
    patient_id: str,
    titles: TitleStyle,
    now: datetime,
    version: int,
) -> Event:
    """An all-day to-do on the day the patient chose: call and book this visit."""
    event = Event()
    event.add("uid", _uid(patient_id, f"call:{index}"))
    event.add("dtstamp", now)
    event.add("sequence", version)
    event.add("dtstart", follow_up.call_on)
    event.add("dtend", follow_up.call_on + timedelta(days=1))
    if titles == "detailed":
        event.add("summary", f"Call to book: {follow_up.what}")
        event.add("description", f"Your papers say: {follow_up.when}")
    else:
        event.add("summary", "Call to book an appointment")
        event.add("description", "Open AfterCare for details.")
    event.add_component(_alarm())
    return event


def build_ics(
    schedule: Schedule,
    patient_id: str,
    *,
    today: date,
    now: datetime,
    discharge_date: date | None = None,
    titles: TitleStyle = "private",
) -> bytes:
    """Daily reminders start today, or on the discharge date if that is still ahead.

    Visit and call-to-book entries sit on the exact day the papers or the patient gave.
    """
    start = max(today, discharge_date) if discharge_date else today
    calendar = Calendar()
    calendar.add("prodid", PRODUCT_ID)
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")

    for event in _medicine_events(schedule, patient_id, start, titles, now):
        calendar.add_component(event)
    for index, follow_up in enumerate(schedule.follow_ups):
        if follow_up.status == VisitStatus.NOT_BOOKED:
            if follow_up.call_on is not None:
                calendar.add_component(
                    _call_reminder_event(
                        follow_up, index, patient_id, titles, now, schedule.version
                    )
                )
        elif follow_up.date is not None:
            calendar.add_component(
                _follow_up_event(follow_up, index, patient_id, titles, now, schedule.version)
            )
    return calendar.to_ical()
