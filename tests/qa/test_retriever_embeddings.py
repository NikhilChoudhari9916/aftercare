from pathlib import Path

import pytest

from app.models import Chunk
from app.qa.embedding_search import FINGERPRINT_FILE, INDEX_FILE, EmbeddingSearch
from app.qa.index import index_patient
from app.qa.retriever import Retriever
from app.storage import get_index_file, patient_dir
from tests.qa.conftest import other_patient
from tests.qa.fakes import DIURETIC, ConceptEmbedder
from tests.qa.test_index_and_retriever import chunks_of


def retriever(db, tmp_path: Path, embedder: ConceptEmbedder, min_similarity=0.3):
    search = EmbeddingSearch(
        embedder, model_name="fake", min_similarity=min_similarity, storage_root=tmp_path
    )
    return Retriever(db, search)


def test_meaning_search_adds_what_keywords_cannot_find(db, confirmed_patient, tmp_path):
    # Patient 1's papers say LASIX and furosemide but never "water pill".
    keywords_only = Retriever(db).search(confirmed_patient, "is my water pill the same", 4)
    both = retriever(db, tmp_path, ConceptEmbedder(DIURETIC))
    found = both.search(confirmed_patient, "is my water pill the same", 4)

    def furosemide_row(passages):
        return any(
            p.section == "Your medicine list" and p.text.startswith("furosemide") for p in passages
        )

    assert not furosemide_row(keywords_only)
    assert furosemide_row(found)
    assert both.last_mode == "hybrid"


def test_a_model_that_cannot_run_falls_back_to_keywords_and_says_so(
    db, confirmed_patient, tmp_path
):
    embedder = ConceptEmbedder(DIURETIC)
    embedder.broken = True
    search = retriever(db, tmp_path, embedder)

    found = search.search(confirmed_patient, "how much sodium", 4)

    assert found  # keyword search still answers
    assert search.last_mode == "keyword"


def test_the_index_is_kept_in_the_patients_own_folder_and_reused(db, confirmed_patient, tmp_path):
    embedder = ConceptEmbedder(DIURETIC)
    search = retriever(db, tmp_path, embedder)

    search.search(confirmed_patient, "water pill", 4)
    after_first = embedder.calls
    search.search(confirmed_patient, "sodium", 4)

    folder = patient_dir(tmp_path, confirmed_patient) / "index"
    assert {p.name for p in folder.iterdir()} == {INDEX_FILE, FINGERPRINT_FILE}
    assert embedder.calls == after_first + 1  # only the new question was embedded


def test_the_index_is_rebuilt_when_the_papers_are_indexed_again(db, confirmed_patient, tmp_path):
    embedder = ConceptEmbedder(DIURETIC)
    search = retriever(db, tmp_path, embedder)
    search.search(confirmed_patient, "water pill", 4)
    before = get_index_file(tmp_path, confirmed_patient, FINGERPRINT_FILE)

    index_patient(db, confirmed_patient)
    search.search(confirmed_patient, "water pill", 4)

    assert get_index_file(tmp_path, confirmed_patient, FINGERPRINT_FILE) != before


# --- the two-patient leak test, with meaning search too (ADR-0031) ---


def test_meaning_search_never_returns_another_patients_papers(db, confirmed_patient, tmp_path):
    other = other_patient(db)
    embedder = ConceptEmbedder({"blood": {"warfarin", "coumadin", "blood thinner"}, **DIURETIC})
    search = retriever(db, tmp_path, embedder, min_similarity=0.0)  # let everything through
    other_texts = {c.text for c in chunks_of(db, other)}
    own_texts = {c.text for c in chunks_of(db, confirmed_patient)}

    for query in ("blood thinner", "warfarin", "water pill", "medicine", "sodium"):
        assert {p.text for p in search.search(confirmed_patient, query, 50)} <= own_texts
        assert {p.text for p in search.search(other, query, 50)} <= other_texts


def test_each_patients_vectors_are_stored_apart(db, confirmed_patient, tmp_path):
    other = other_patient(db)
    search = retriever(db, tmp_path, ConceptEmbedder(DIURETIC))

    search.search(confirmed_patient, "water pill", 4)
    search.search(other, "warfarin", 4)

    mine = get_index_file(tmp_path, confirmed_patient, INDEX_FILE)
    theirs = get_index_file(tmp_path, other, INDEX_FILE)
    assert mine and theirs and mine != theirs
    assert patient_dir(tmp_path, confirmed_patient) != patient_dir(tmp_path, other)


def test_a_patients_chunks_are_a_stable_view_of_their_own_rows(db, confirmed_patient):
    chunks = chunks_of(db, confirmed_patient)
    assert all(isinstance(c, Chunk) and c.patient_id == confirmed_patient for c in chunks)


@pytest.mark.parametrize("name", ["../x", "a/b", "..\\x"])
def test_an_index_file_name_cannot_leave_the_patients_folder(tmp_path, name):
    from app.storage import save_index_file

    with pytest.raises(ValueError):
        save_index_file(tmp_path, "00000000-0000-4000-8000-000000000000", name, b"x")
