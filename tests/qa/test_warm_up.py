"""The first question must not wait for the embedding model or the patient's vectors."""

import logging
import sys
import threading
import time
import types

import numpy as np

from app.qa.embedding_search import FINGERPRINT_FILE, INDEX_FILE, EmbeddingSearch
from app.qa.embeddings import SentenceTransformerEmbedder
from app.qa.factory import warm_embedder, warm_patient_index
from app.qa.retriever import Retriever
from app.storage import patient_dir
from tests.auth.helpers import make_settings
from tests.documents.test_upload_api import decide_all
from tests.qa.conftest import other_patient
from tests.qa.fakes import DIURETIC, ConceptEmbedder, wait_for_warm_up
from tests.qa.test_index_and_retriever import chunks_of


def index_folder(root, patient_id):
    return patient_dir(root, patient_id) / "index"


def use_embedder(monkeypatch, embedder) -> None:
    monkeypatch.setattr("app.qa.factory._embedder", lambda name: embedder)


def fake_model(monkeypatch, *, seconds: float = 0.05) -> list[int]:
    """Stand in for the sentence-transformers library. The list counts how often a model loaded."""
    loads: list[int] = []

    class Model:
        def __init__(self, name: str) -> None:
            time.sleep(seconds)
            loads.append(1)

        def encode(self, texts, normalize_embeddings, convert_to_numpy):
            return np.ones((len(texts), 4), dtype=np.float32)

    monkeypatch.setitem(
        sys.modules, "sentence_transformers", types.SimpleNamespace(SentenceTransformer=Model)
    )
    return loads


# --- the model loads in the background, once ---


def test_the_model_loads_once_in_the_background_and_then_reports_ready(monkeypatch):
    loads = fake_model(monkeypatch)
    embedder = SentenceTransformerEmbedder("fake")
    assert not embedder.is_ready

    embedder.start_loading()
    embedder.start_loading()  # asking again while it loads must not start a second load
    wait_for_warm_up()

    assert embedder.is_ready
    assert len(loads) == 1


def test_two_threads_asking_at_once_still_load_the_model_once(monkeypatch):
    loads = fake_model(monkeypatch)
    embedder = SentenceTransformerEmbedder("fake")

    threads = [threading.Thread(target=embedder.embed, args=(["x"],)) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert len(loads) == 1


def test_a_model_that_cannot_load_is_logged_and_stays_not_ready(monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)  # as if not installed
    embedder = SentenceTransformerEmbedder("fake")

    with caplog.at_level(logging.WARNING, logger="app.qa.embeddings"):
        embedder.start_loading()
        wait_for_warm_up()

    assert not embedder.is_ready
    assert "keywords only" in caplog.text


def test_starting_the_backend_starts_loading_unless_warm_up_is_off(monkeypatch):
    embedder = ConceptEmbedder()
    embedder.started = 0
    embedder.start_loading = lambda: setattr(embedder, "started", embedder.started + 1)
    use_embedder(monkeypatch, embedder)

    warm_embedder(make_settings(embeddings_warm_up=False))
    warm_embedder(make_settings(embeddings_warm_up=True, embeddings_enabled=False))
    assert embedder.started == 0

    warm_embedder(make_settings(embeddings_warm_up=True))
    assert embedder.started == 1


# --- a question that arrives while the model is still loading ---


class LoadingEmbedder(ConceptEmbedder):
    """Not ready until the test says so, like a model that is still loading."""

    def __init__(self, concepts):
        super().__init__(concepts)
        self.is_ready = False
        self.started = 0

    def start_loading(self) -> None:
        self.started += 1


def test_a_question_during_loading_uses_keywords_instead_of_waiting(
    db, confirmed_patient, tmp_path
):
    embedder = LoadingEmbedder(DIURETIC)
    search = EmbeddingSearch(embedder, model_name="fake", min_similarity=0.1, storage_root=tmp_path)
    retriever = Retriever(db, search)

    found = retriever.search(confirmed_patient, "how much sodium", 4)

    assert found  # keywords still answer
    assert retriever.last_mode == "keyword"  # and the log can show why
    assert embedder.calls == 0  # nothing was embedded, so nobody waited
    assert embedder.started == 1  # but loading was started for the next question

    embedder.is_ready = True
    retriever.search(confirmed_patient, "how much sodium", 4)
    assert retriever.last_mode == "hybrid"


# --- two searches at once on one patient ---


class SlowEmbedder(ConceptEmbedder):
    def embed(self, texts):
        time.sleep(0.2)
        return super().embed(texts)


def test_two_questions_at_once_build_the_patients_index_only_once(db, confirmed_patient, tmp_path):
    embedder = SlowEmbedder(DIURETIC)
    search = EmbeddingSearch(embedder, model_name="fake", min_similarity=0.1, storage_root=tmp_path)
    chunks = chunks_of(db, confirmed_patient)
    errors: list[BaseException] = []

    def ask() -> None:
        try:
            search.close_to(confirmed_patient, chunks, "water pill")
        except BaseException as error:  # the test must see a failure on any thread
            errors.append(error)

    threads = [threading.Thread(target=ask) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == []
    assert embedder.calls == 1 + 3  # one build of the index, then one embedding per question
    folder = index_folder(tmp_path, confirmed_patient)
    assert {p.name for p in folder.iterdir()} == {INDEX_FILE, FINGERPRINT_FILE}


# --- the index is built when the patient confirms ---


def test_the_vectors_are_ready_before_the_first_question(
    db, confirmed_patient, tmp_path, monkeypatch
):
    embedder = ConceptEmbedder(DIURETIC)
    use_embedder(monkeypatch, embedder)
    settings = make_settings(storage_dir=tmp_path, embeddings_warm_up=True)

    warm_patient_index(db.get_bind(), settings, confirmed_patient)

    folder = index_folder(tmp_path, confirmed_patient)
    assert {p.name for p in folder.iterdir()} == {INDEX_FILE, FINGERPRINT_FILE}
    built = embedder.calls

    # The model name is part of the fingerprint, so search with the settings' model name.
    retriever = Retriever(
        db,
        EmbeddingSearch(
            embedder,
            model_name=settings.embedding_model,
            min_similarity=0.1,
            storage_root=tmp_path,
        ),
    )
    retriever.search(confirmed_patient, "water pill", 4)

    assert embedder.calls == built + 1  # only the question was embedded: nothing was rebuilt
    assert retriever.last_mode == "hybrid"


def test_warming_one_patient_never_touches_another(db, confirmed_patient, tmp_path, monkeypatch):
    other = other_patient(db)
    use_embedder(monkeypatch, ConceptEmbedder(DIURETIC))

    warm_patient_index(
        db.get_bind(),
        make_settings(storage_dir=tmp_path, embeddings_warm_up=True),
        confirmed_patient,
    )

    assert index_folder(tmp_path, confirmed_patient).exists()
    assert not index_folder(tmp_path, other).exists()


def test_warming_does_nothing_when_it_is_off(db, confirmed_patient, tmp_path, monkeypatch):
    embedder = ConceptEmbedder(DIURETIC)
    use_embedder(monkeypatch, embedder)

    warm_patient_index(
        db.get_bind(),
        make_settings(storage_dir=tmp_path, embeddings_warm_up=False),
        confirmed_patient,
    )

    assert embedder.calls == 0
    assert not index_folder(tmp_path, confirmed_patient).exists()


def test_a_warm_up_failure_is_logged_and_never_breaks_confirming(
    db, confirmed_patient, tmp_path, monkeypatch, caplog
):
    embedder = ConceptEmbedder(DIURETIC)
    embedder.broken = True
    use_embedder(monkeypatch, embedder)

    with caplog.at_level(logging.WARNING, logger="app.qa.factory"):
        warm_patient_index(
            db.get_bind(),
            make_settings(storage_dir=tmp_path, embeddings_warm_up=True),
            confirmed_patient,
        )

    assert "could not be warmed up" in caplog.text
    assert not index_folder(tmp_path, confirmed_patient).exists()


def test_confirming_through_the_api_starts_the_warm_up_for_that_patient(client, ready, monkeypatch):
    patient_id, extraction = ready
    started: list[str] = []
    monkeypatch.setattr(
        "app.documents.routes.warm_patient_index",
        lambda engine, settings, patient: started.append(patient),
    )

    response = client.put(f"/patients/{patient_id}/profile", json=decide_all(extraction))

    assert response.status_code == 200
    assert started == [patient_id]
