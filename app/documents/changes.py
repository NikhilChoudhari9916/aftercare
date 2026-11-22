"""Patient-visible edit history. Extracted values are never called original document facts."""

import json

from sqlmodel import Session, select

from app.models import DocumentPage, ProfileChange, ProfileStatus, ProfileVersion, RetrievalState

CHECK_DOCUMENTS = "Please check your documents or call your healthcare provider."


def change_notices(db: Session, version: ProfileVersion) -> tuple[list[str], set[str]]:
    changes = db.exec(
        select(ProfileChange)
        .where(
            ProfileChange.patient_id == version.patient_id,
            ProfileChange.profile_version_id == version.id,
        )
        .order_by(ProfileChange.created_at, ProfileChange.id)
    ).all()
    state = db.get(RetrievalState, version.id)
    if not changes:
        if version.status == ProfileStatus.CONFIRMED and (
            state is None or not state.include_document_text
        ):
            return (
                [
                    "Earlier edits or removals may be present, but their original edit history "
                    "is unavailable. The saved profile cannot be treated as original-document "
                    f"evidence. {CHECK_DOCUMENTS}"
                ],
                set(),
            )
        return [], set()
    pages = {
        page.number: page.text
        for page in db.exec(
            select(DocumentPage).where(
                DocumentPage.patient_id == version.patient_id,
                DocumentPage.document_id == version.document_id,
            )
        ).all()
    }
    notices = []
    for change in changes:
        before = json.loads(change.before_data)
        after = json.loads(change.after_data) if change.after_data is not None else None
        number = before.get("source_page")
        original = pages.get(number, "")
        identity = (
            before.get("name_as_written")
            or before.get("what")
            or before.get("name")
            or before.get("text")
            or change.section
        )
        lines = [f"Edited item (as originally extracted): {identity}"]
        if after is None:
            lines += [
                "Originally extracted item (check against the document): "
                + json.dumps(before, ensure_ascii=False),
                "Your edit: item removed (user-entered change, not document evidence).",
            ]
        else:
            for key in sorted(set(before) | set(after)):
                if before.get(key) == after.get(key):
                    continue
                label = key.replace("_", " ")
                lines += [
                    f"Originally extracted {label} (check against the document): "
                    + json.dumps(before.get(key), ensure_ascii=False),
                    f"Your edited {label}: "
                    + json.dumps(after.get(key), ensure_ascii=False)
                    + " (user-entered, not document evidence).",
                ]
        lines.append(CHECK_DOCUMENTS)
        lines.append(
            f"Original document (page {number}): "
            + (original if original else "Original text unavailable; no original value verified.")
        )
        notices.append("\n\n".join(lines))
    return notices, {change.item_id for change in changes}
