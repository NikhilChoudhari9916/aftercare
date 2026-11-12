from datetime import date
from html import escape

from ui.api_client import Me

GENERIC_SIGN_IN_ERROR = "Something went wrong signing you in. Please try again."

SIGN_IN_ERRORS = {
    "sign_in_failed": "We couldn't sign you in with Google. Please try again.",
    "email_not_verified": (
        "Google says your email address isn't verified. "
        "Please verify it with Google, then try again."
    ),
}


def error_message(code: str | None) -> str | None:
    """Turn the backend's error code into a friendly sentence. Never repeats the code itself."""
    if not code:
        return None
    return SIGN_IN_ERRORS.get(code, GENERIC_SIGN_IN_ERROR)


def describe_role(me: Me) -> str:
    roles = {patient.role for patient in me.patients}
    if "OWNER" in roles:
        return "You are signed in as the patient."
    if "AIDE" in roles:
        return "You are signed in as an aide."
    return "You are signed in."


def sign_in_url(backend_url: str) -> str:
    return f"{backend_url}/auth/login?next=/"


def dev_sign_in_form(backend_url: str, persona: str, label: str) -> str:
    """The development-only test login button (ADR-0037). The backend refuses it anywhere but
    a developer's own machine, so showing it is never what protects anything."""
    action = escape(f"{backend_url}/auth/dev-login", quote=True)
    return (
        f'<form method="post" action="{action}" style="width:100%">'
        f'<input type="hidden" name="persona" value="{escape(persona, quote=True)}">'
        '<button type="submit" class="ac-nbtn dashed">'
        f"{escape(label)}</button></form>"
    )


def sign_out_form(backend_url: str) -> str:
    """A plain form, so the browser itself posts to the backend and receives the cookie-clearing
    response (ADR-0033). Built only from our own configuration, never from user data."""
    action = escape(f"{backend_url}/auth/logout", quote=True)
    return (
        f'<form method="post" action="{action}" style="width:100%">'
        '<button type="submit" class="ac-nbtn">'
        "Sign out</button></form>"
    )


SECTION_ORDER = ("medicines", "warning_signs", "follow_ups", "care_team", "diet_limits")
SECTION_TITLES = {
    "medicines": "Your medicines",
    "warning_signs": "Warning signs",
    "follow_ups": "Follow-up visits",
    "care_team": "Who to call",
    "diet_limits": "Food and drink limits",
}
STATUS_WORDS = {
    "NEW": "New",
    "CHANGED": "Changed",
    "STOPPED": "Stopped",
    "CONTINUED": "Keep taking as before",
    "AS_NEEDED": "Only when needed",
}
TIER_WORDS = {"CALL_911": "Call 911", "CALL_CARE_TEAM": "Call your care team"}

# What the patient may correct on each kind of item. The words copied from the papers
# (source_quote) are never editable: they are the evidence the patient checks against.
EDIT_FIELDS: dict[str, list[tuple[str, str]]] = {
    "medicines": [
        ("dose", "Dose"),
        ("frequency", "How often"),
        ("timing", "When (time of day, with food)"),
        ("change_note", "What changed"),
        ("end_date", "Last day (YYYY-MM-DD)"),
    ],
    "warning_signs": [("text", "Warning sign")],
    "follow_ups": [("what", "What"), ("when", "When"), ("with_whom", "With")],
    "care_team": [("name", "Name"), ("phone", "Phone"), ("hours", "Hours")],
    "diet_limits": [("text", "Limit")],
}
OPTIONAL_FIELDS = {"dose", "frequency", "timing", "change_note", "end_date", "with_whom", "hours"}
SELECT_FIELDS: dict[str, tuple[str, dict[str, str]]] = {
    "medicines": ("status", STATUS_WORDS),
    "warning_signs": ("tier", TIER_WORDS),
}

# The reading steps in the order the backend runs them (the names are the job's step names).
PROGRESS_STEPS = (
    ("ingest", "Reading your pages"),
    ("extract", "Finding your medicines and details"),
    ("check_quotes", "Checking each item against your papers"),
    ("normalize", "Tidying up"),
)
NOT_FOUND_WARNING = (
    "We could not find these exact words in your papers. Please check this one carefully."
)


def step_states(status: str, step: str | None) -> list[str]:
    """done / active / pending for each reading step. `step` is the last step the job finished."""
    names = [name for name, _ in PROGRESS_STEPS]
    if status == "SUCCEEDED" or step == "done":
        return ["done"] * len(names)
    finished = names.index(step) + 1 if step in names else 0
    return [
        "done" if index < finished else "active" if index == finished else "pending"
        for index in range(len(names))
    ]


def item_headline(section: str, data: dict) -> str:
    if section == "medicines":
        return " ".join(part for part in (data.get("name_as_written"), data.get("dose")) if part)
    if section == "follow_ups":
        return data.get("what", "")
    if section == "care_team":
        return data.get("name", "")
    return data.get("text", "")


def item_lines(section: str, data: dict) -> list[str]:
    """The details under an item's headline, in plain words."""
    lines: list[str] = []
    if section == "medicines":
        lines += [data.get("frequency"), data.get("timing"), data.get("change_note")]
        if data.get("end_date"):
            lines.append(f"Last day: {data['end_date']}")
    elif section == "follow_ups":
        lines += [data.get("when"), data.get("with_whom")]
    elif section == "care_team":
        lines += [data.get("phone"), data.get("hours")]
    return [line for line in lines if line]


def item_chip(section: str, data: dict) -> tuple[str, str] | None:
    """(words, kind) for the colored chip on an item: a medicine's status or a warning's urgency."""
    key, words = {"medicines": ("status", STATUS_WORDS), "warning_signs": ("tier", TIER_WORDS)}.get(
        section, (None, {})
    )
    value = data.get(key) if key else None
    return (words[value], value) if value in words else None


def quote_note(quote_status: str) -> str | None:
    return NOT_FOUND_WARNING if quote_status == "not_found" else None


def injection_warning(pages: list[int]) -> str | None:
    """Text in the papers that talks to a computer program instead of to the patient."""
    if not pages:
        return None
    where = ", ".join(str(page) for page in sorted(set(pages)))
    return (
        f"Page {where} of your papers has text that looks like instructions to a computer "
        "program, not to you. AfterCare ignores it. Please check that page carefully."
    )


def apply_edits(data: dict, edits: dict[str, str]) -> dict | None:
    """The item's data with the patient's changes, or None if nothing changed.

    A blank answer clears an optional field and leaves a required one as it was."""
    changed = dict(data)
    for key, raw in edits.items():
        value = (raw or "").strip()
        if value:
            changed[key] = value
        elif key in OPTIONAL_FIELDS:
            changed[key] = None
    return changed if changed != data else None


# (icon, title, text, coming soon?) for the three cards under the sign-in box.
HOW_IT_WORKS = (
    ("upload_file", "Upload your papers", "Choose the PDF you were given at the hospital.", False),
    (
        "fact_check",
        "Check what we found",
        "Confirm each medicine and detail, side by side with your papers.",
        False,
    ),
    (
        "auto_stories",
        "Understand and plan",
        "A plain-language summary, a medicine schedule, and reminders.",
        False,
    ),
)


def calendar_url(backend_url: str, patient_id: str, titles: str = "private") -> str:
    """The calendar file is a plain link: the browser sends its own cookie and saves the file."""
    return f"{backend_url}/patients/{patient_id}/schedule.ics?titles={titles}"


def medicine_title(name: str, dose: str | None) -> str:
    return f"{name} {dose}" if dose else name


def also_called(other_names: list[str]) -> str | None:
    names = [name for name in other_names if name]
    return f"Also called {', '.join(names)}" if names else None


def end_date_note(end_date: str | None) -> str | None:
    """ "Until Nov 20" for a fixed course, or nothing."""
    if not end_date:
        return None
    try:
        day = date.fromisoformat(end_date)
    except ValueError:
        return None
    return f"Until {day.strftime('%b')} {day.day}, {day.year}"


def visit_when(when: str, with_whom: str | None) -> str:
    return f"{when}, with {with_whom}" if with_whom else when


SCHEDULE_TIP = (
    "Times start as suggestions from your papers. "
    "Choose your own in “Set up your reminders”, and the calendar file will use them."
)
NEEDS_TIMING_NOTE = (
    "Your papers don't say a clear time of day for these, so they are not in the calendar yet. "
    "The patient chooses their times in “Set up your reminders”."
)
CALENDAR_REDOWNLOAD = "If you change your papers, download the calendar file again."


def clock_label(hhmm: str) -> str:
    """ "08:00" becomes "8:00 AM"."""
    hour, minute = (int(part) for part in hhmm.split(":"))
    suffix = "AM" if hour < 12 else "PM"
    return f"{hour % 12 or 12}:{minute:02d} {suffix}"


# --- planning (ADR-0042) -----------------------------------------------------------------

PLAN_INTRO = (
    "Choose when you take each medicine and what you will do about each visit. "
    "These are your choices, not your papers. Your papers stay as they are."
)
VISIT_KIND_NOTES = {
    "booked_time": "Your papers give a date and a time. Check that they are right.",
    "date_only": "Your papers give a date but no time. Add the time if you know it.",
    "window": "Your papers give a window of time, not one time. Pick when you plan to go.",
    "no_date": "Your papers don't give a date. You still need to call to book this visit.",
}
TIMES_NOTE_FIXED = "Your papers say {phrase} a day, so pick {count}."
TIMES_NOTE_FREE = "Your papers don't say a clear time. Add the times you will take it, or none."
PLAN_SAVED = "Saved. Your schedule and calendar file now use your choices."
BOOKED, NOT_BOOKED = "BOOKED", "NOT_BOOKED"


def format_day(iso_day: str | None) -> str:
    """ "2026-10-20" becomes "Tue, Oct 20, 2026"."""
    if not iso_day:
        return ""
    try:
        day = date.fromisoformat(iso_day)
    except ValueError:
        return iso_day
    return f"{day.strftime('%a, %b')} {day.day}, {day.year}"


def times_note(times_needed: int | None) -> str:
    if not times_needed:
        return TIMES_NOTE_FREE
    phrase = "1 time" if times_needed == 1 else f"{times_needed} times"
    return TIMES_NOTE_FIXED.format(phrase=phrase, count=times_needed)


def visit_start_state(line) -> dict[str, str]:
    """What the form starts with for one visit: their saved choice, else what the papers gave."""
    if line.chosen:
        return {
            "status": line.status or BOOKED,
            "date": line.date or "",
            "time": line.time or "",
            "call_on": line.call_on or "",
        }
    if line.kind == "no_date":
        return {"status": NOT_BOOKED, "date": "", "time": "", "call_on": ""}
    return {
        "status": BOOKED,
        "date": line.papers_date or "",
        "time": line.papers_time or "",
        "call_on": "",
    }


def build_plan_payload(
    medicine_times: dict[str, list[str]], visits: dict[str, dict[str, str]]
) -> dict:
    """The body for PUT /plan. Blank boxes are left out; the server checks everything else."""
    return {
        "medicines": [
            {"item_id": item_id, "times": [value for value in times if value]}
            for item_id, times in medicine_times.items()
        ],
        "visits": [
            (
                {
                    "item_id": item_id,
                    "status": BOOKED,
                    "date": state["date"] or None,
                    "time": state["time"] or None,
                }
                if state["status"] == BOOKED
                else {
                    "item_id": item_id,
                    "status": NOT_BOOKED,
                    "call_on": state["call_on"] or None,
                }
            )
            for item_id, state in visits.items()
        ],
    }


def visit_when_text(line) -> str:
    """What to show for a visit: the patient's choice if they made one, else the papers' words."""
    if line.status == NOT_BOOKED:
        base = "Not booked yet"
        return (
            f"{base}. Reminder to call on {format_day(line.call_on)}."
            if line.call_on
            else (f"{base}.")
        )
    if line.chosen and line.date:
        text = format_day(line.date)
        return f"{text} at {clock_label(line.time)}" if line.time else f"{text} (all day)"
    return visit_when(line.when, line.with_whom)
