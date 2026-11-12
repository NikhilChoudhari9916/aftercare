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
        '<button type="submit" '
        'style="width:100%;min-height:48px;font-size:1rem;border:1px dashed #888;'
        'border-radius:4px;background:transparent;color:inherit;cursor:pointer">'
        f"{escape(label)}</button></form>"
    )


def sign_out_form(backend_url: str) -> str:
    """A plain form, so the browser itself posts to the backend and receives the cookie-clearing
    response (ADR-0033). Built only from our own configuration, never from user data."""
    action = escape(f"{backend_url}/auth/logout", quote=True)
    return (
        f'<form method="post" action="{action}" style="width:100%">'
        '<button type="submit" '
        'style="width:100%;min-height:48px;font-size:1rem;border:1px solid #888;'
        'border-radius:4px;background:transparent;color:inherit;cursor:pointer">'
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

JOB_STEP_WORDS = {
    "ingest": "Reading the pages",
    "extract": "Finding your medicines and details",
    "check_quotes": "Checking each item against your papers",
    "normalize": "Tidying up abbreviations",
    "done": "Done",
}
NOT_FOUND_WARNING = (
    "We could not find these exact words in your papers. Please check this one carefully."
)


def job_step_text(status: str, step: str | None) -> str:
    if status == "QUEUED":
        return "Waiting to start"
    return JOB_STEP_WORDS.get(step or "", "Working on it")


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
        lines.append(STATUS_WORDS.get(data.get("status", ""), ""))
        lines += [data.get("frequency"), data.get("timing"), data.get("change_note")]
        if data.get("end_date"):
            lines.append(f"Last day: {data['end_date']}")
    elif section == "warning_signs":
        lines.append(TIER_WORDS.get(data.get("tier", ""), ""))
    elif section == "follow_ups":
        lines += [data.get("when"), data.get("with_whom")]
    elif section == "care_team":
        lines += [data.get("phone"), data.get("hours")]
    return [line for line in lines if line]


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
