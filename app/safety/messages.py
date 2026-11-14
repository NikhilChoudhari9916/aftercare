"""Fixed words the safety gate is allowed to say. None of these is written by a model."""

# Word for word from CLAUDE.md section 5. A test pins it; changing it is a safety change.
TIER1_MESSAGE = (
    "This could be an emergency. Please call 911 now. "
    "Do not drive yourself. If someone is with you, ask them to stay with you."
)

NO_CARE_TEAM_LINE = "Please call your care team or your pharmacist."


def care_team_line(name: str | None, phone: str | None, hours: str | None = None) -> str:
    """The line every Tier 2 answer starts with: who to call, from the patient's own papers."""
    if not name or not phone:
        return NO_CARE_TEAM_LINE
    when = f" ({hours})" if hours else ""
    return f"Please call {name} at {phone}{when}."


def safe_fallback(pharmacist_phone: str | None = None) -> str:
    """What the patient sees when an answer failed its checks twice (CLAUDE.md section 6)."""
    if not pharmacist_phone:
        return "I can't answer that safely. Please call your pharmacist."
    return f"I can't answer that safely. Please call your pharmacist at {pharmacist_phone}."
