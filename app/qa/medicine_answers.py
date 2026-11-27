"""Fixed answers for two common list questions, backed by complete original table entries."""

import re
from typing import Literal

from app.safety.messages import NO_CARE_TEAM_LINE
from app.safety.rules import Tier
from app.tools.paper_medicines import MedicineEntries

MedicineQuestion = Literal["new", "purposes", "list"]


def medicine_question(question: str) -> MedicineQuestion | None:
    text = " ".join(question.casefold().strip(' \t\r\n?‘’“”"').split())
    if re.fullmatch(
        r"(?:which|what) (?:of )?(?:my |the )?(?:medicine|medication)s? "
        r"(?:is|are|was|were) (?:the )?new",
        text,
    ) or re.fullmatch(r"which (?:is|are) (?:my |the )?new (?:medicine|medication)s?", text):
        return "new"
    if re.fullmatch(
        r"what (?:is|are) (?:each of |all of )?(?:my |the |these )?"
        r"(?:medicine|medication)s? (?:used )?for",
        text,
    ):
        return "purposes"
    if re.fullmatch(
        r"(?:what|which) (?:medicine|medication)s? (?:am i|do i) (?:taking|take|on)"
        r"|what (?:is|are) (?:all )?(?:of )?(?:my|the) (?:medicine|medication|med)s?"
        r"|(?:list|show|tell me) (?:me )?(?:all )?(?:of )?(?:my|the) (?:medicine|medication|med)s?",
        text,
    ):
        return "list"
    return None


def answer_medicine_list(entries: MedicineEntries, intent: MedicineQuestion, tier: Tier) -> str:
    lines = []
    if tier == Tier.CARE_TEAM:
        lines.append(NO_CARE_TEAM_LINE)
    if intent == "new":
        selected = [e for e in entries.passages if e.status == "NEW"]
        if not selected:
            return "\n\n".join(
                [
                    *lines,
                    "I couldn't verify any entries explicitly marked NEW in your medicine list.",
                ]
            )
        lines.append("Your uploaded medicine list explicitly marks these medicines NEW:")
        lines += [f"- **{e.name}** — marked **NEW**. [{e.id}]" for e in selected]
    elif intent == "list":
        lines.append("Your uploaded medicine list includes these medicines:")
        for entry in entries.passages:
            marked = f" — marked **{entry.status}**" if entry.status else ""
            lines.append(f"- **{entry.name}**{marked}. [{entry.id}]")
    else:
        lines.append("Here is what I can verify in the medicine-list entries:")
        for entry in entries.passages:
            status = " (marked STOPPED)" if entry.status == "STOPPED" else ""
            purpose = (
                f"Original words: “{entry.purpose_quote}”"
                if entry.purpose_quote
                else "I couldn't verify a purpose in this medicine-list entry."
            )
            lines.append(f"- **{entry.name}**{status}: {purpose} [{entry.id}]")
        lines.append("I won't infer a purpose from a medicine's name or timing.")
    return "\n\n".join(lines)
