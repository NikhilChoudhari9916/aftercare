"""Plain "what is this medicine for?" questions: the papers first, then the FDA label (ADR-0048).

Everything here is plain code. The model never writes any of this reply, so a purpose can only
come from the patient's own papers or, word for word, from the official label's "indications
and usage" part, which is shown as general information and never as the patient's own reason.
"""

import re

from app.enrichment.openfda import LabelText
from app.memory.session import Recall
from app.qa.references import resolve_reference
from app.safety.messages import NO_CARE_TEAM_LINE
from app.safety.rules import Tier
from app.summary.profile import ConfirmedProfile
from app.tools.paper_medicines import MedicineEntry

# Only direct questions about one medicine. Anything else keeps the regular workflow.
_PURPOSE_QUESTIONS = (
    r"what (?:does|do) .+ do",
    r"what(?: is|'s|’s| are) .+ (?:used |prescribed |taken )?for",
    r"why (?:am i|do i) (?:taking|take|on) .+",
)

LABEL_EXCERPT_CHARS = 450  # about two sentences: enough to read, short enough to stay clear
_SHORTEST_SENTENCE_CUT = 120  # do not stop after a stub such as "Edema."

_HEADING = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\s+)?indications\s*(?:and|&)\s*usage\s*:?\s*", re.IGNORECASE
)
_SECTION_NUMBER = re.compile(r"^\d+(?:\.\d+)*\s+")
_CROSS_REFERENCE = re.compile(r"\(\s*\d+(?:\.\d+)*(?:\s*,\s*\d+(?:\.\d+)*)*\s*\)")
_MARKUP = re.compile(r"[\[\]*]")  # square brackets could fake a [D1] tag; asterisks make bold


def purpose_medicine(profile: ConfirmedProfile, question: str, recall: Recall) -> str | None:
    """The one confirmed medicine a plain purpose question is about, or None.

    "What is Lasix for?" and "What is it for?" (after a question that named the medicine) work.
    A question that names no medicine, or two, keeps the regular workflow.
    """
    rewritten, focus = resolve_reference(profile, question, recall)
    if focus is None:
        return None
    text = " ".join(rewritten.casefold().strip(' \t\r\n?!.‘’“”"').split())
    if any(re.fullmatch(pattern, text) for pattern in _PURPOSE_QUESTIONS):
        return focus
    return None


def entry_for(entries: list[MedicineEntry], profile: ConfirmedProfile, medicine: str):
    """The original medicine-list row for a confirmed medicine, matched by any of its names."""
    names = {medicine.casefold()}
    for confirmed in profile.medicines:
        if confirmed.name_as_written == medicine:
            names.update(n.casefold() for n in [confirmed.name_as_written, *confirmed.other_names])
    return next((entry for entry in entries if entry.name.casefold() in names), None)


def label_excerpt(purpose: str) -> str:
    """The start of the label's "indications and usage", in its own words.

    Only layout is removed: the section heading, its numbering, "( 1.1 )" cross-references and
    characters the page would treat as markup. A long section is cut at a sentence end.
    """
    text = _HEADING.sub("", purpose)
    text = _SECTION_NUMBER.sub("", text)
    text = _CROSS_REFERENCE.sub("", text)
    text = " ".join(_MARKUP.sub("", text).split())
    if len(text) <= LABEL_EXCERPT_CHARS:
        return text
    head = text[:LABEL_EXCERPT_CHARS]
    cut = max(head.rfind(". "), head.rfind("? "), head.rfind("! "))
    head = head[: cut + 1] if cut >= _SHORTEST_SENTENCE_CUT else head.rsplit(" ", 1)[0]
    return f"{head} …"


def answer_purpose(
    medicine: str,
    entry: MedicineEntry | None,
    label: LabelText | None,
    label_id: str | None,
    tier: Tier,
) -> tuple[str, list[str]]:
    """The reply and the source IDs it cites. The papers win over the label."""
    lines = [NO_CARE_TEAM_LINE] if tier == Tier.CARE_TEAM else []
    if entry is not None and entry.purpose_quote:
        lines.append(f"Original words from your papers about {medicine}:")
        lines.append(f"“{entry.purpose_quote}” [{entry.id}]")
        return "\n\n".join(lines), [entry.id]

    lines.append(f"Your papers don't say why you take {medicine}.")
    if label is not None and label.found and label.purpose and label_id:
        lines.append(
            "General information from the FDA drug label, in its own words:\n\n"
            f"“{label_excerpt(label.purpose)}” [{label_id}]"
        )
        lines.append(
            "The label may list several uses. It does not say which one is yours, "
            "so please ask your care team or your pharmacist."
        )
        return "\n\n".join(lines), [label_id]
    lines.append(
        "I also couldn't get a description from the FDA drug label. "
        "Please ask your care team or your pharmacist."
    )
    return "\n\n".join(lines), []
