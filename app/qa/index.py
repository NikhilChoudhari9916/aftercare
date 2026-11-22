from sqlmodel import Session, delete, select

from app.models import Chunk, ChunkSource, DocumentPage, ProfileItem, ProfileVersion, RetrievalState
from app.qa.chunker import chunk_pages
from app.summary.profile import load_confirmed_profile


def index_patient(db: Session, patient_id: str) -> int:
    """Cut the patient's confirmed papers into searchable chunks. Returns how many were made.

    Run right after the patient confirms. The old chunks are replaced, so a medicine the patient
    removed, or papers they replaced, can never be found again. Does nothing (and returns 0)
    when nothing is confirmed.
    """
    profile = load_confirmed_profile(db, patient_id)
    if profile is None:
        return 0
    version = db.get(ProfileVersion, profile.version_id)
    pages = db.exec(
        select(DocumentPage)
        .where(
            DocumentPage.patient_id == patient_id, DocumentPage.document_id == version.document_id
        )
        .order_by(DocumentPage.number)
    ).all()

    state = db.get(RetrievalState, version.id)
    if state is None:
        # Pre-fix indexes have no reliable edit approval. Withhold original search text.
        state = RetrievalState(patient_id=patient_id, profile_version_id=version.id)
    if state.patient_id != patient_id:
        raise ValueError("The retrieval state belongs to another patient")
    unconfirmed = db.exec(
        select(ProfileItem.id).where(
            ProfileItem.patient_id == patient_id,
            ProfileItem.profile_version_id == version.id,
            ProfileItem.confirmed == False,  # noqa: E712
        )
    ).first()
    if unconfirmed is not None:
        state.include_document_text = False
    chunks = (
        chunk_pages(pages) if state.include_document_text and not profile.review_notices else []
    )
    db.exec(delete(Chunk).where(Chunk.patient_id == patient_id))
    for number, raw in enumerate(chunks, start=1):
        db.add(
            Chunk(
                patient_id=patient_id,
                profile_version_id=version.id,
                source=ChunkSource.DOCUMENT,
                ref=f"D{number}",
                position=number,
                page=raw.page,
                section=raw.section,
                text=raw.text,
            )
        )
    state.ready = True
    db.add(state)
    db.commit()
    return len(chunks)
