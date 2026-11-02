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
