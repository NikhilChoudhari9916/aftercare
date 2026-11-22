"""Read complete medicine-list entries from original text; never infer a medical purpose."""

import re
from collections import Counter

from pydantic import BaseModel
from sqlmodel import select

from app.models import DocumentPage, ProfileVersion
from app.summary.profile import load_confirmed_profile
from app.tools.profile_tools import Passage
from app.tools.registry import NoInput, Tool, ToolContext, ToolError

HEADING = re.compile(r"(?im)^\s*(?:your medicine list|discharge medications|medication list)\s*$")
STATUS = re.compile(r"(?im)(?<!\w)(NEW|STOPPED|CONTINUE(?:D)?(?::[^\n]*)?|CHANGED:[^\n]*)[ \t]*$")


class MedicineEntry(Passage):
    name: str
    status: str | None
    purpose_quote: str | None


class MedicineEntries(BaseModel):
    passages: list[MedicineEntry]


def medicine_entries(context: ToolContext, _arguments: NoInput) -> MedicineEntries:
    if context.db is None:
        raise ToolError("Original medicine-list entries are unavailable.")
    profile = load_confirmed_profile(context.db, context.patient_id)
    if profile is None or profile.review_notices:
        raise ToolError("Please review your original papers before using the medicine list.")
    version = context.db.get(ProfileVersion, profile.version_id)
    pages = context.db.exec(
        select(DocumentPage)
        .where(
            DocumentPage.patient_id == context.patient_id,
            DocumentPage.document_id == version.document_id,
        )
        .order_by(DocumentPage.number)
    ).all()
    first_words = Counter(m.name_as_written.split()[0].casefold() for m in profile.medicines)
    entries = []
    status_count = 0
    for page in pages:
        heading = HEADING.search(page.text)
        if heading is None:
            continue
        body = page.text[heading.end() :]
        status_count += len(list(STATUS.finditer(body)))
        anchors = []
        for medicine in profile.medicines:
            if medicine.source_page != page.number:
                continue
            candidates = [medicine.name_as_written, *medicine.other_names]
            first = medicine.name_as_written.split()[0]
            if first_words[first.casefold()] == 1:
                candidates.append(first)
            matches = []
            for name in candidates:
                # Anchoring to the beginning of a physical row prevents matching mentions in
                # another medicine's instructions. The entire entry is retained as evidence.
                pattern = r"(?im)^\s*\(?" + r"\s+".join(map(re.escape, name.split()))
                match = re.search(pattern + r"(?![\w-])", body)
                if match:
                    matches.append(match)
            if matches:
                match = min(matches, key=lambda m: (m.start(), -len(m.group())))
                anchors.append((match.start(), " ".join(match.group().strip().lstrip("(").split())))
        anchors.sort()
        for i, (start, name) in enumerate(anchors):
            end = anchors[i + 1][0] if i + 1 < len(anchors) else len(body)
            row = body[start:end].strip()
            if i + 1 == len(anchors):
                # End the last table row before a following section, not after a marker in
                # the right-hand column: NEW may share a line with a name/instruction.
                boundary = re.search(
                    r"\n[ \t]*\n|(?im:^[ \t]*(?:Pain relief|Follow-up|Food|Activity|"
                    r"When to call)[: ])",
                    row,
                )
                if boundary:
                    row = row[: boundary.start()].strip()
            status = STATUS.search(row)
            if status is None:
                continue  # unknown layout: use the regular question path; do not guess a row
            flat = " ".join(row.split())
            purpose = None
            for sentence in re.split(r"(?<=[.!?])\s+", flat):
                if re.search(r"\b(?:as needed|is used|is prescribed) for\b", sentence, re.I):
                    if not re.search(r"\b(?:not|never|avoid|don't|don’t)\b", sentence, re.I):
                        # Keep the whole row, including dose limits and warnings, rather than
                        # cutting away a negation or qualification around a purpose phrase.
                        purpose = flat
                    break
            entries.append(
                MedicineEntry(
                    id=f"D{2000 + len(entries) + 1}",
                    name=name,
                    page=page.number,
                    section="Original medicine-list entry",
                    text=flat,
                    original_document=True,
                    status=status.group(1).split(":")[0].upper(),
                    purpose_quote=purpose,
                )
            )
    # Partial coverage is not enough to answer "each" or enumerate all new medicines.
    if len(entries) != len(profile.medicines) or len(entries) != status_count or not entries:
        raise ToolError("The complete original medicine list could not be verified.")
    return MedicineEntries(passages=entries)


READ_ORIGINAL_MEDICINE_ENTRIES = Tool(
    name="read_original_medicine_entries",
    description=(
        "Read complete medicine-list rows from this patient's unchanged original "
        "uploaded document, including explicit status markers and literal purpose phrases. "
        "No external sources, edits or inferred purposes are used."
    ),
    input_model=NoInput,
    handler=medicine_entries,
)
