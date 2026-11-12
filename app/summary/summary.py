"""The plain-language summary. Built from the confirmed profile by plain code, no model (ADR-0040).

Every sentence says what "your papers" say and carries the page it came from, so the screen can
show a "From your papers, page N" tag. Nothing here says whether the patient has a condition,
and nothing tells anyone to start, stop, skip or change a medicine: it repeats the papers.
"""

from pydantic import BaseModel

from app.extraction.schema import ExtractedMedication, MedStatus
from app.summary.profile import ConfirmedProfile
from app.summary.schedule import is_as_needed

INTRO = (
    "This is what your discharge papers say, in plain words. "
    "If anything looks wrong, call your care team or your pharmacist."
)


class SummaryLine(BaseModel):
    text: str
    source_page: int | None = None


class SummarySection(BaseModel):
    key: str
    title: str
    lines: list[SummaryLine]


class Summary(BaseModel):
    version: int
    intro: str
    sections: list[SummarySection]


def _plain(text: str) -> str:
    """Drop a trailing full stop so the sentence we build around it ends with just one."""
    return text.strip().rstrip(".")


def _name(medicine: ExtractedMedication) -> str:
    others = [name for name in medicine.other_names if name]
    return (
        f"{medicine.name_as_written} (also called {', '.join(others)})"
        if others
        else (medicine.name_as_written)
    )


def _how(medicine: ExtractedMedication) -> str:
    parts = [medicine.dose, medicine.frequency, medicine.timing]
    return ", ".join(part for part in parts if part)


def _medicine_sentence(medicine: ExtractedMedication) -> str:
    name, how = _name(medicine), _how(medicine)
    if medicine.status == MedStatus.STOPPED:
        return f"Your papers say to stop {name}. Ask your pharmacist if you are not sure."
    if is_as_needed(medicine):
        base = f"Your papers list {name} to take only when needed"
        return f"{base}: {how}." if how else f"{base}."
    if medicine.status == MedStatus.CHANGED:
        base = f"Your papers say {name} has changed"
        sentence = f"{base}. Now: {how}." if how else f"{base}."
        return f"{sentence} {medicine.change_note}" if medicine.change_note else sentence
    verb = {MedStatus.NEW: "list a new medicine", MedStatus.CONTINUED: "say to continue"}.get(
        medicine.status
    )
    if verb is None:
        return f"Your papers list {name}: {how}." if how else f"Your papers list {name}."
    text = f"Your papers {verb}: {name}"
    return f"{text}, {how}." if how else f"{text}."


def build_summary(profile: ConfirmedProfile) -> Summary:
    sections: list[SummarySection] = []

    def add(key: str, title: str, lines: list[SummaryLine]) -> None:
        if lines:
            sections.append(SummarySection(key=key, title=title, lines=lines))

    add(
        "medicines",
        "Your medicines",
        [
            SummaryLine(text=_medicine_sentence(m), source_page=m.source_page)
            for m in profile.medicines
        ],
    )
    add(
        "follow_ups",
        "Visits and tests",
        [
            SummaryLine(
                text=f"{f.what}: {f.when}" + (f", with {f.with_whom}." if f.with_whom else "."),
                source_page=f.source_page,
            )
            for f in profile.follow_ups
        ],
    )
    add(
        "call_911",
        "Call 911 right away",
        [
            SummaryLine(
                text=f"Your papers say to call 911 for: {_plain(w.text)}.",
                source_page=w.source_page,
            )
            for w in profile.warning_signs
            if w.tier == "CALL_911"
        ],
    )
    add(
        "call_care_team",
        "Call your care team",
        [
            SummaryLine(
                text=f"Your papers say to call your care team for: {_plain(w.text)}.",
                source_page=w.source_page,
            )
            for w in profile.warning_signs
            if w.tier == "CALL_CARE_TEAM"
        ],
    )
    add(
        "diet",
        "Food and drink",
        [
            SummaryLine(text=f"Your papers say: {_plain(d.text)}.", source_page=d.source_page)
            for d in profile.diet_limits
        ],
    )
    add(
        "care_team",
        "Who to call",
        [
            SummaryLine(
                text=f"{c.name}: {c.phone}" + (f" ({c.hours})." if c.hours else "."),
                source_page=c.source_page,
            )
            for c in profile.care_team
        ],
    )
    return Summary(version=profile.version, intro=INTRO, sections=sections)
