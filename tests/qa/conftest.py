from sqlmodel import Session

from app.extraction.schema import MedStatus
from app.models import Patient, ProfileStatus, User
from app.qa.index import index_patient
from tests.documents.test_upload_api import (
    ready,  # noqa: F401  (fixture: Patient 1 read, not confirmed)
)
from tests.samples import medicine
from tests.summary.conftest import confirmed_patient  # noqa: F401  (fixture: Patient 1, confirmed)
from tests.summary.test_profile import add_version


def other_patient(db: Session) -> str:
    """A second, confirmed and indexed patient whose only medicine is warfarin."""
    user = User(google_sub="someone-else", email="b@example.com", display_name="Bea")
    db.add(user)
    db.commit()
    patient = Patient(owner_user_id=user.id)
    db.add(patient)
    db.commit()
    warfarin = medicine("warfarin", ["COUMADIN"], "5 mg", "daily", MedStatus.NEW, "Take warfarin.")
    add_version(db, patient.id, 1, ProfileStatus.CONFIRMED, [(warfarin, True)])
    index_patient(db, patient.id)
    return patient.id
