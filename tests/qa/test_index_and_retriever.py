from sqlmodel import Session, select

from app.models import Chunk, Patient, ProfileStatus, User
from app.qa.index import index_patient
from app.qa.retriever import Retriever
from tests.documents.test_upload_api import decide_all
from tests.qa.conftest import other_patient
from tests.samples import patient1_profile
from tests.summary.test_profile import add_version


def chunks_of(db: Session, patient_id: str) -> list[Chunk]:
    return list(db.exec(select(Chunk).where(Chunk.patient_id == patient_id)).all())


# --- the index, built when the patient confirms ---


def test_confirming_makes_the_papers_searchable(client, db, confirmed_patient):
    chunks = chunks_of(db, confirmed_patient)

    assert len(chunks) > 6
    assert sorted(c.position for c in chunks) == list(range(1, len(chunks) + 1))
    assert {c.ref for c in chunks} == {f"D{i}" for i in range(1, len(chunks) + 1)}
    assert {c.source for c in chunks} == {"DOCUMENT"}
    assert sum(c.section == "Your medicine list" for c in chunks) >= 6


def test_a_medicine_the_patient_removed_is_not_in_the_medicine_chunks(client, db, ready):
    patient_id, extraction = ready
    amlodipine = next(
        item
        for item in extraction["items"]
        if item["section"] == "medicines" and item["data"]["name_as_written"] == "amlodipine"
    )

    response = client.put(
        f"/patients/{patient_id}/profile",
        json=decide_all(extraction, **{amlodipine["id"]: {"action": "remove"}}),
    )

    assert response.status_code == 200
    rows = [
        c.text
        for c in chunks_of(db, patient_id)
        if c.section == "Your medicine list" and c.text.startswith(("amlodipine", "furosemide"))
    ]
    assert any(text.startswith("furosemide") for text in rows)
    assert not any(text.startswith("amlodipine") for text in rows)


def test_indexing_again_replaces_the_old_chunks(db, confirmed_patient):
    before = {c.id for c in chunks_of(db, confirmed_patient)}

    index_patient(db, confirmed_patient)

    after = chunks_of(db, confirmed_patient)
    assert before.isdisjoint({c.id for c in after})
    assert len(after) == len(before)


def test_nothing_is_indexed_until_the_papers_are_confirmed(db, ready):
    patient_id, _extraction = ready

    assert index_patient(db, patient_id) == 0
    assert chunks_of(db, patient_id) == []


# --- the retriever ---


def search(db, patient_id, query, limit=4):
    return Retriever(db).search(patient_id, query, limit)


def test_a_question_finds_the_section_that_answers_it(db, confirmed_patient):
    found = search(db, confirmed_patient, "how much sodium can I have")

    answer = next(p for p in found if "Limit sodium to less than 2,000 mg" in p.text)
    assert answer.page == 2
    assert answer.id.startswith("D")


def test_a_brand_name_finds_the_medicine_written_under_its_generic_name(db, confirmed_patient):
    found = search(db, confirmed_patient, "did they change the lasix")

    assert any(p.section == "Your medicine list" and "furosemide" in p.text for p in found)


def test_a_question_the_papers_do_not_cover_returns_nothing(db, confirmed_patient):
    assert search(db, confirmed_patient, "zebra") == []


def test_at_most_the_asked_number_of_passages_come_back(db, confirmed_patient):
    assert len(search(db, confirmed_patient, "medicine", limit=2)) == 2


def test_a_patient_whose_papers_are_not_confirmed_gets_nothing(db):
    user = User(google_sub="draft", email="c@example.com", display_name="Cy")
    db.add(user)
    db.commit()
    patient = Patient(owner_user_id=user.id)
    db.add(patient)
    db.commit()
    add_version(db, patient.id, 1, ProfileStatus.DRAFT, [(patient1_profile().medicines[0], False)])

    assert search(db, patient.id, "furosemide") == []


# --- the two-patient leak test (ADR-0031): it must pass before retrieval merges ---


def test_one_patients_question_never_returns_another_patients_papers(db, confirmed_patient):
    other = other_patient(db)

    mine = search(db, confirmed_patient, "warfarin")
    theirs = search(db, other, "furosemide")

    assert mine == [] and theirs == []
    assert search(db, other, "warfarin")  # the other patient can find their own


def test_every_passage_belongs_to_the_patient_who_asked(db, confirmed_patient):
    other = other_patient(db)
    own_ids = {c.id: c.patient_id for c in chunks_of(db, confirmed_patient)}
    other_texts = {c.text for c in chunks_of(db, other)}

    for query in ("medicine", "take", "daily", "pain", "the papers"):
        for passage in search(db, confirmed_patient, query, limit=50):
            assert passage.text not in other_texts
        assert all(passage.id for passage in search(db, confirmed_patient, query, limit=50))
    assert own_ids  # patient 1 really has chunks, so the checks above were not vacuous


def test_a_patients_words_are_not_used_to_expand_another_patients_question(db, confirmed_patient):
    other = other_patient(db)

    # "coumadin" is warfarin's other name for the other patient only
    assert search(db, confirmed_patient, "coumadin") == []
    assert search(db, other, "coumadin")
