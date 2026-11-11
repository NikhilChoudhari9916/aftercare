import json
import logging
from collections.abc import Callable

from sqlmodel import Session, func, select

from app.agents.upload_graph import iter_upload
from app.config import Settings
from app.extraction.schema import SOURCED_SECTIONS
from app.llm import LLM
from app.models import (
    DocumentPage,
    Job,
    JobStatus,
    ProfileItem,
    ProfileVersion,
    utc_now,
)
from app.storage import get_pdf

logger = logging.getLogger(__name__)

# A quote that moved to another page was fixed in the graph, so it counts as verified.
VERIFIED = {"verified", "page_corrected"}


def run_extraction_job(
    job_id: str,
    *,
    session_factory: Callable[[], Session],
    llm: LLM,
    settings: Settings,
) -> None:
    """Run the upload graph for one document and store what it found as a DRAFT profile."""
    with session_factory() as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        job.status = JobStatus.RUNNING
        job.started_at = utc_now()
        db.add(job)
        db.commit()
        try:
            _run(db, job, llm, settings)
        except Exception as error:  # a worker thread must never die silently
            db.rollback()
            # The type only: exception messages can echo document text (ADR-0031).
            logger.error("extraction job %s crashed: %s", job_id, type(error).__name__)
            _fail(db, job_id, "internal_error")


def _fail(db: Session, job_id: str, code: str) -> None:
    job = db.get(Job, job_id)
    job.status = JobStatus.FAILED
    job.error_code = code
    job.finished_at = utc_now()
    db.add(job)
    db.commit()


def _run(db: Session, job: Job, llm: LLM, settings: Settings) -> None:
    pdf_bytes = get_pdf(settings.storage_dir, job.patient_id, job.document_id)

    final: dict = {}
    for node, update in iter_upload(llm, settings, pdf_bytes):
        final.update(update)
        job.step = node
        db.add(job)
        db.commit()

    if final.get("error"):
        _fail(db, job.id, final["error"])
        return

    _store(db, job, final)
    job.status = JobStatus.SUCCEEDED
    job.step = "done"
    job.finished_at = utc_now()
    db.add(job)
    db.commit()


def _store(db: Session, job: Job, final: dict) -> None:
    patient_id, document_id = job.patient_id, job.document_id
    for page in final["pages"]:
        db.add(
            DocumentPage(
                document_id=document_id, patient_id=patient_id, number=page.number, text=page.text
            )
        )

    latest = db.exec(
        select(func.max(ProfileVersion.version)).where(ProfileVersion.patient_id == patient_id)
    ).one()
    profile = final["profile"]
    version = ProfileVersion(
        patient_id=patient_id,
        document_id=document_id,
        version=(latest or 0) + 1,
        discharge_date=profile.discharge_date,
        injection_flags=json.dumps(
            [
                {"page": flag.page, "kind": flag.kind, "excerpt": flag.excerpt}
                for flag in final.get("injection_flags", [])
            ]
        ),
    )
    db.add(version)
    db.flush()

    statuses = {(f.section, f.index): f.status for f in final.get("findings", [])}
    for section in SOURCED_SECTIONS:
        for position, item in enumerate(getattr(profile, section)):
            status = "verified" if statuses.get((section, position)) in VERIFIED else "not_found"
            db.add(
                ProfileItem(
                    profile_version_id=version.id,
                    patient_id=patient_id,
                    section=section,
                    position=position,
                    data=item.model_dump_json(),
                    quote_status=status,
                )
            )
    db.commit()
