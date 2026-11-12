from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class Role(StrEnum):
    OWNER = "OWNER"
    AIDE = "AIDE"


class AccessStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class AccessEventKind(StrEnum):
    PATIENT_CREATED = "PATIENT_CREATED"
    DENIED = "DENIED"


class User(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    google_sub: str = Field(unique=True, index=True)
    email: str
    display_name: str
    created_at: datetime = Field(default_factory=utc_now)


class Patient(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    owner_user_id: str = Field(foreign_key="user.id", index=True)
    discharge_date: date | None = None
    created_at: datetime = Field(default_factory=utc_now)


class PatientAccess(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("patient_id", "user_id"),)

    id: str = Field(default_factory=new_id, primary_key=True)
    patient_id: str = Field(foreign_key="patient.id", index=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    role: Role
    status: AccessStatus = AccessStatus.ACTIVE
    invited_by_user_id: str | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None


class AccessEvent(SQLModel, table=True):
    """Audit trail of access changes. IDs only, never patient text."""

    id: str = Field(default_factory=new_id, primary_key=True)
    kind: AccessEventKind
    # No foreign keys: a denied attempt may name a patient that does not exist.
    patient_id: str | None = None
    user_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class LoginSession(SQLModel, table=True):
    __tablename__ = "session"

    id: str = Field(default_factory=new_id, primary_key=True)
    token_hash: str = Field(unique=True, index=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=utc_now)
    last_seen_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime


class JobType(StrEnum):
    EXTRACT = "EXTRACT"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ProfileStatus(StrEnum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"


class Document(SQLModel, table=True):
    """An uploaded PDF. The file lives in storage; only IDs and counts are kept here."""

    id: str = Field(default_factory=new_id, primary_key=True)
    patient_id: str = Field(foreign_key="patient.id", index=True)
    uploaded_at: datetime = Field(default_factory=utc_now)
    page_count: int


class DocumentPage(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    document_id: str = Field(foreign_key="document.id", index=True)
    patient_id: str = Field(index=True)
    number: int
    text: str


class Job(SQLModel, table=True):
    """Slow work that runs in the background (ADR-0034). Never holds patient text."""

    id: str = Field(default_factory=new_id, primary_key=True)
    patient_id: str = Field(foreign_key="patient.id", index=True)
    document_id: str | None = Field(default=None, foreign_key="document.id")
    type: JobType
    status: JobStatus = JobStatus.QUEUED
    step: str | None = None
    error_code: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ProfileVersion(SQLModel, table=True):
    """One extraction of one document. DRAFT until the patient has decided on every item."""

    id: str = Field(default_factory=new_id, primary_key=True)
    patient_id: str = Field(foreign_key="patient.id", index=True)
    document_id: str = Field(foreign_key="document.id")
    version: int
    status: ProfileStatus = ProfileStatus.DRAFT
    discharge_date: str | None = None
    injection_flags: str = "[]"  # JSON: page, kind, short excerpt
    created_at: datetime = Field(default_factory=utc_now)
    confirmed_at: datetime | None = None


class VisitStatus(StrEnum):
    BOOKED = "BOOKED"
    NOT_BOOKED = "NOT_BOOKED"


class MedicinePlan(SQLModel, table=True):
    """The patient's own reminder times for one confirmed medicine (ADR-0042).

    Their choice, not the papers: the papers' words stay in ProfileItem, untouched.
    """

    id: str = Field(default_factory=new_id, primary_key=True)
    patient_id: str = Field(foreign_key="patient.id", index=True)
    profile_item_id: str = Field(foreign_key="profileitem.id", unique=True, index=True)
    times: str  # JSON list of "HH:MM", sorted; may be empty ("no reminders")
    updated_at: datetime = Field(default_factory=utc_now)


class VisitPlan(SQLModel, table=True):
    """The patient's plan for one confirmed visit: booked, or not booked yet (ADR-0042)."""

    id: str = Field(default_factory=new_id, primary_key=True)
    patient_id: str = Field(foreign_key="patient.id", index=True)
    profile_item_id: str = Field(foreign_key="profileitem.id", unique=True, index=True)
    status: VisitStatus
    planned_date: date | None = None
    planned_time: str | None = None  # "HH:MM"
    call_on: date | None = None  # when to be reminded to call and book
    updated_at: datetime = Field(default_factory=utc_now)


class ProfileItem(SQLModel, table=True):
    """One extracted fact. `data` is the JSON of the typed item (see app/extraction/schema.py)."""

    id: str = Field(default_factory=new_id, primary_key=True)
    profile_version_id: str = Field(foreign_key="profileversion.id", index=True)
    patient_id: str = Field(index=True)
    section: str
    position: int
    data: str
    quote_status: str  # "verified" or "not_found"
    confirmed: bool = False
