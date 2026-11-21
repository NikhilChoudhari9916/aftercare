import pytest
from sqlmodel import Session, select

from app.models import Chunk, Patient, ProfileStatus, ProfileVersion, RetrievalState, User
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


def test_removed_medicine_cannot_be_found_in_any_original_pdf_passage(client, db, ready):
    patient_id, extraction = ready
    removed = next(
        i
        for i in extraction["items"]
        if i["section"] == "medicines" and i["data"]["name_as_written"] == "amlodipine"
    )
    response = client.put(
        f"/patients/{patient_id}/profile",
        json=decide_all(extraction, **{removed["id"]: {"action": "remove"}}),
    )
    assert response.status_code == 200

    assert search(db, patient_id, "amlodipine norvasc") == []
    assert all(
        "amlodipine" not in c.text.casefold() and "norvasc" not in c.text.casefold()
        for c in chunks_of(db, patient_id)
    )
    assert search(db, patient_id, "furosemide")
    assert search(db, patient_id, "sodium")


def test_edited_dose_does_not_reappear_from_the_original_quote_or_pdf(client, db, ready):
    from app.summary.profile import load_confirmed_profile

    patient_id, extraction = ready
    item = next(
        i
        for i in extraction["items"]
        if i["section"] == "medicines" and i["data"]["name_as_written"] == "metoprolol succinate ER"
    )
    edited = {**item["data"], "dose": "37 mg"}
    assert (
        client.put(
            f"/patients/{patient_id}/profile",
            json=decide_all(extraction, **{item["id"]: {"data": edited}}),
        ).status_code
        == 200
    )

    passages = search(db, patient_id, "metoprolol", 50)
    text = " ".join(p.text for p in passages)
    assert "37 mg" in text
    assert "25 mg" not in text
    profile = load_confirmed_profile(db, patient_id)
    medicine = next(m for m in profile.medicines if m.name_as_written == "metoprolol succinate ER")
    assert medicine.dose == "37 mg"
    assert "25 mg" not in medicine.source_quote


@pytest.mark.parametrize(
    "section", ["medicines", "warning_signs", "follow_ups", "care_team", "diet_limits"]
)
def test_removals_from_each_section_are_absent_from_every_retrieval_chunk(
    client, db, ready, section
):
    patient_id, extraction = ready
    removed = next(i for i in extraction["items"] if i["section"] == section)
    assert (
        client.put(
            f"/patients/{patient_id}/profile",
            json=decide_all(extraction, **{removed["id"]: {"action": "remove"}}),
        ).status_code
        == 200
    )
    state = db.get(RetrievalState, extraction["version_id"])
    assert state.ready and not state.include_document_text
    assert all(removed["data"]["source_quote"] not in c.text for c in chunks_of(db, patient_id))


def test_legacy_chunks_are_rebuilt_before_keyword_or_embedding_search(
    db, confirmed_patient, tmp_path
):
    from app.qa.embedding_search import EmbeddingSearch
    from tests.qa.fakes import DIURETIC, ConceptEmbedder

    state = db.exec(
        select(RetrievalState).where(RetrievalState.patient_id == confirmed_patient)
    ).one()
    version_id = state.profile_version_id
    db.delete(state)
    stale = chunks_of(db, confirmed_patient)[0]
    stale.text = "Unapproved obsolete medicine zebradrug 999 mg"
    db.add(stale)
    db.commit()
    embedding = ConceptEmbedder(DIURETIC)
    retriever = Retriever(
        db, EmbeddingSearch(embedding, model_name="fake", min_similarity=0.0, storage_root=tmp_path)
    )

    passages = retriever.search(confirmed_patient, "medicine", 100)

    assert passages and all("zebradrug" not in p.text for p in passages)
    assert all("zebradrug" not in c.text for c in chunks_of(db, confirmed_patient))
    rebuilt = db.get(RetrievalState, version_id)
    assert rebuilt.ready and not rebuilt.include_document_text
    assert retriever.last_mode == "hybrid"


def test_an_incomplete_index_is_rebuilt_before_search(db, confirmed_patient):
    state = db.exec(
        select(RetrievalState).where(RetrievalState.patient_id == confirmed_patient)
    ).one()
    state.ready = False
    db.add(state)
    db.commit()
    before = {c.id for c in chunks_of(db, confirmed_patient)}

    assert search(db, confirmed_patient, "furosemide")
    assert state.ready
    assert before.isdisjoint({c.id for c in chunks_of(db, confirmed_patient)})


def test_old_profile_version_chunks_cannot_be_returned_even_if_left_in_storage(
    db, confirmed_patient
):
    current = db.exec(
        select(ProfileVersion).where(ProfileVersion.patient_id == confirmed_patient)
    ).one()
    old = ProfileVersion(
        patient_id=confirmed_patient,
        document_id=current.document_id,
        version=0,
        status=ProfileStatus.CONFIRMED,
    )
    db.add(old)
    db.commit()
    db.add(
        Chunk(
            patient_id=confirmed_patient,
            profile_version_id=old.id,
            source="DOCUMENT",
            ref="D999",
            position=999,
            page=1,
            section="Old papers",
            text="obsolete zebradrug",
        )
    )
    db.commit()

    assert search(db, confirmed_patient, "zebradrug") == []


def test_confirming_identical_data_preserves_the_unchanged_document_search(client, db, ready):
    patient_id, extraction = ready
    overrides = {item["id"]: {"data": item["data"]} for item in extraction["items"]}
    assert (
        client.put(
            f"/patients/{patient_id}/profile", json=decide_all(extraction, **overrides)
        ).status_code
        == 200
    )
    state = db.get(RetrievalState, extraction["version_id"])
    assert state.ready and state.include_document_text
    assert any(
        "Weigh yourself every morning" in p.text
        for p in search(db, patient_id, "weigh myself every morning")
    )


def test_corrected_profiles_remain_isolated_in_hybrid_search(client, db, ready, tmp_path):
    from app.qa.embedding_search import EmbeddingSearch
    from tests.qa.fakes import DIURETIC, ConceptEmbedder

    patient_id, extraction = ready
    removed = next(
        i
        for i in extraction["items"]
        if i["section"] == "medicines" and i["data"]["name_as_written"] == "amlodipine"
    )
    assert (
        client.put(
            f"/patients/{patient_id}/profile",
            json=decide_all(extraction, **{removed["id"]: {"action": "remove"}}),
        ).status_code
        == 200
    )
    other = other_patient(db)
    retriever = Retriever(
        db,
        EmbeddingSearch(
            ConceptEmbedder(DIURETIC), model_name="fake", min_similarity=0.0, storage_root=tmp_path
        ),
    )
    ours = {c.text for c in chunks_of(db, patient_id)}
    theirs = {c.text for c in chunks_of(db, other)}

    for query in ("amlodipine", "warfarin", "furosemide"):
        mine = {p.text for p in retriever.search(patient_id, query, 100)}
        other_found = {p.text for p in retriever.search(other, query, 100)}
        assert mine <= ours and other_found <= theirs
        assert all("amlodipine" not in text and "warfarin" not in text for text in mine)
        assert all("furosemide" not in text for text in other_found)


def test_startup_adds_retrieval_state_to_an_existing_database_without_losing_rows(tmp_path):
    from sqlalchemy import inspect
    from sqlmodel import SQLModel

    from app.db import init_db, make_engine

    engine = make_engine(f"sqlite:///{tmp_path / 'existing.db'}")
    SQLModel.metadata.create_all(engine)
    RetrievalState.__table__.drop(engine)
    with Session(engine) as db:
        user = User(google_sub="existing", email="existing@example.com", display_name="Existing")
        db.add(user)
        db.commit()
        user_id = user.id
    init_db(engine)
    assert "retrievalstate" in inspect(engine).get_table_names()
    with Session(engine) as db:
        assert db.get(User, user_id) is not None
    engine.dispose()
