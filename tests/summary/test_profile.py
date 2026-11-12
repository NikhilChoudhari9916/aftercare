import json

from sqlmodel import Session

from app.models import (
    Document,
    Patient,
    ProfileItem,
    ProfileStatus,
    ProfileVersion,
    User,
)
from app.summary.profile import load_confirmed_profile
from tests.samples import patient1_profile


def make_patient(db: Session) -> str:
    user = User(google_sub="sub", email="a@example.com", display_name="Ada")
    db.add(user)
    db.commit()
    patient = Patient(owner_user_id=user.id)
    db.add(patient)
    db.commit()
    return patient.id


def add_version(db: Session, patient_id: str, number: int, status: ProfileStatus, medicines):
    document = Document(patient_id=patient_id, page_count=1)
    db.add(document)
    db.commit()
    version = ProfileVersion(
        patient_id=patient_id,
        document_id=document.id,
        version=number,
        status=status,
        discharge_date="2026-10-12",
    )
    db.add(version)
    db.commit()
    for position, (medicine, confirmed) in enumerate(medicines):
        db.add(
            ProfileItem(
                profile_version_id=version.id,
                patient_id=patient_id,
                section="medicines",
                position=position,
                data=medicine.model_dump_json(),
                quote_status="verified",
                confirmed=confirmed,
            )
        )
    db.commit()
    return version


def test_a_draft_with_nothing_confirmed_gives_no_profile(db: Session):
    patient_id = make_patient(db)
    medicines = patient1_profile().medicines
    add_version(db, patient_id, 1, ProfileStatus.DRAFT, [(m, False) for m in medicines])

    assert load_confirmed_profile(db, patient_id) is None


def test_an_unconfirmed_item_inside_a_confirmed_version_is_ignored(db: Session):
    patient_id = make_patient(db)
    first, second, *_ = patient1_profile().medicines
    add_version(db, patient_id, 1, ProfileStatus.CONFIRMED, [(first, True), (second, False)])

    profile = load_confirmed_profile(db, patient_id)

    assert [m.name_as_written for m in profile.medicines] == [first.name_as_written]


def test_a_newer_unconfirmed_upload_never_replaces_the_confirmed_profile(db: Session):
    patient_id = make_patient(db)
    first, second, *_ = patient1_profile().medicines
    add_version(db, patient_id, 1, ProfileStatus.CONFIRMED, [(first, True)])
    add_version(db, patient_id, 2, ProfileStatus.DRAFT, [(second, False)])

    profile = load_confirmed_profile(db, patient_id)

    assert profile.version == 1
    assert [m.name_as_written for m in profile.medicines] == [first.name_as_written]


def test_a_bad_discharge_date_is_dropped_not_guessed(db: Session):
    patient_id = make_patient(db)
    version = add_version(db, patient_id, 1, ProfileStatus.CONFIRMED, [])
    version.discharge_date = "last Tuesday"
    db.add(version)
    db.commit()

    assert load_confirmed_profile(db, patient_id).discharge_date is None


def test_another_patients_items_are_never_loaded(db: Session):
    patient_id = make_patient(db)
    other = Patient(owner_user_id=db.get(Patient, patient_id).owner_user_id)
    db.add(other)
    db.commit()
    first, second, *_ = patient1_profile().medicines
    add_version(db, patient_id, 1, ProfileStatus.CONFIRMED, [(first, True)])
    add_version(db, other.id, 1, ProfileStatus.CONFIRMED, [(second, True)])

    mine = load_confirmed_profile(db, patient_id)
    theirs = load_confirmed_profile(db, other.id)

    assert [m.name_as_written for m in mine.medicines] == [first.name_as_written]
    assert [m.name_as_written for m in theirs.medicines] == [second.name_as_written]
    assert json.loads(first.model_dump_json())["name_as_written"] not in str(theirs.medicines)
