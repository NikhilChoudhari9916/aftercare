import json
from functools import partial
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel, ValidationError
from sqlmodel import Session, select

from app.auth.dependencies import AppSettings, CurrentUser, DbSession, check_access, require_access
from app.documents.deps import get_job_runner, get_llm_or_503
from app.extraction.schema import SECTION_MODELS
from app.ingestion.pdf_reader import PdfError, read_pdf
from app.jobs.extraction import run_extraction_job
from app.jobs.messages import friendly_error
from app.jobs.runner import JobRunner
from app.llm import LLM
from app.models import (
    Document,
    Job,
    JobType,
    PatientAccess,
    ProfileItem,
    ProfileStatus,
    ProfileVersion,
    Role,
    utc_now,
)
from app.storage import save_pdf

router = APIRouter()

Runner = Annotated[JobRunner, Depends(get_job_runner)]
Llm = Annotated[LLM, Depends(get_llm_or_503)]
OwnerAccess = Annotated[PatientAccess, Depends(require_access(Role.OWNER))]


class UploadResponse(BaseModel):
    job_id: str
    document_id: str


class JobOut(BaseModel):
    id: str
    type: str
    status: str
    step: str | None
    error_code: str | None
    message: str | None
    document_id: str | None


class ItemOut(BaseModel):
    id: str
    section: str
    position: int
    data: dict[str, Any]
    quote_status: str
    confirmed: bool


class FlagOut(BaseModel):
    page: int
    kind: str
    excerpt: str


class ExtractionOut(BaseModel):
    version_id: str
    version: int
    status: str
    discharge_date: str | None
    injection_flags: list[FlagOut]
    items: list[ItemOut]


class ItemDecision(BaseModel):
    id: str
    action: Literal["confirm", "remove"]
    data: dict[str, Any] | None = None


class ProfileDecision(BaseModel):
    version_id: str
    items: list[ItemDecision]


def _extraction_out(db: Session, version: ProfileVersion) -> ExtractionOut:
    items = db.exec(
        select(ProfileItem)
        .where(ProfileItem.profile_version_id == version.id)
        .order_by(ProfileItem.section, ProfileItem.position)
    ).all()
    return ExtractionOut(
        version_id=version.id,
        version=version.version,
        status=version.status,
        discharge_date=version.discharge_date,
        injection_flags=[FlagOut(**flag) for flag in json.loads(version.injection_flags)],
        items=[
            ItemOut(
                id=item.id,
                section=item.section,
                position=item.position,
                data=json.loads(item.data),
                quote_status=item.quote_status,
                confirmed=item.confirmed,
            )
            for item in items
        ],
    )


@router.post("/documents", status_code=202, response_model=UploadResponse)
async def upload_document(
    patient_id: Annotated[str, Form()],
    file: UploadFile,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
    runner: Runner,
    llm: Llm,
) -> UploadResponse:
    check_access(db, user, patient_id, (Role.OWNER,))

    max_bytes = settings.max_pdf_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    try:
        pages = read_pdf(data, max_pages=settings.max_pdf_pages, max_bytes=max_bytes)
    except PdfError as error:
        raise HTTPException(
            status_code=422, detail={"code": error.code, "message": error.friendly_message}
        ) from error

    document = Document(patient_id=patient_id, page_count=len(pages))
    db.add(document)
    db.commit()
    save_pdf(settings.storage_dir, patient_id, document.id, data)

    job = Job(patient_id=patient_id, document_id=document.id, type=JobType.EXTRACT)
    db.add(job)
    db.commit()

    engine = db.get_bind()
    runner.submit(
        partial(
            run_extraction_job,
            job.id,
            session_factory=lambda: Session(engine),
            llm=llm,
            settings=settings,
        )
    )
    return UploadResponse(job_id=job.id, document_id=document.id)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, user: CurrentUser, db: DbSession) -> JobOut:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Not found")
    check_access(db, user, job.patient_id, (Role.OWNER,))
    return JobOut(
        id=job.id,
        type=job.type,
        status=job.status,
        step=job.step,
        error_code=job.error_code,
        message=friendly_error(job.error_code),
        document_id=job.document_id,
    )


@router.get("/patients/{patient_id}/extraction", response_model=ExtractionOut)
def get_extraction(patient_id: str, _access: OwnerAccess, db: DbSession) -> ExtractionOut:
    version = db.exec(
        select(ProfileVersion)
        .where(ProfileVersion.patient_id == patient_id)
        .order_by(ProfileVersion.version.desc())
    ).first()
    if version is None:
        raise HTTPException(status_code=404, detail="No document has been read yet")
    return _extraction_out(db, version)


@router.put("/patients/{patient_id}/profile", response_model=ExtractionOut)
def confirm_profile(
    patient_id: str, decision: ProfileDecision, _access: OwnerAccess, db: DbSession
) -> ExtractionOut:
    """The patient decides on every item. Nothing unconfirmed is ever used (CLAUDE.md section 2)."""
    version = db.get(ProfileVersion, decision.version_id)
    if version is None or version.patient_id != patient_id:
        raise HTTPException(status_code=404, detail="Not found")
    if version.status == ProfileStatus.CONFIRMED:
        raise HTTPException(status_code=409, detail="This profile is already confirmed")

    items = {
        item.id: item
        for item in db.exec(
            select(ProfileItem).where(ProfileItem.profile_version_id == version.id)
        ).all()
    }
    decided = [entry.id for entry in decision.items]
    if len(set(decided)) != len(decided) or set(decided) != set(items):
        raise HTTPException(status_code=422, detail="Please decide on every item exactly once")

    for entry in decision.items:
        item = items[entry.id]
        if entry.action == "remove":
            db.delete(item)
            continue
        if entry.data is not None:
            try:
                item.data = (
                    SECTION_MODELS[item.section].model_validate(entry.data).model_dump_json()
                )
            except ValidationError as error:
                raise HTTPException(
                    status_code=422, detail=f"That change to a {item.section} item is not valid"
                ) from error
        item.confirmed = True
        db.add(item)

    version.status = ProfileStatus.CONFIRMED
    version.confirmed_at = utc_now()
    db.add(version)
    db.commit()
    return _extraction_out(db, version)
