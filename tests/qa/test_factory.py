import sys

from app.qa.factory import build_retriever
from tests.auth.helpers import make_settings


def test_embeddings_are_on_by_default_and_the_retriever_still_answers_without_the_model(
    db, confirmed_patient, tmp_path, monkeypatch
):
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)  # as if it were not installed
    retriever = build_retriever(db, make_settings(storage_dir=tmp_path))

    found = retriever.search(confirmed_patient, "how much sodium", 4)

    assert found  # keywords still answer
    assert retriever.last_mode == "keyword"  # and the caller can see it fell back


def test_embeddings_can_be_switched_off(db, confirmed_patient, tmp_path):
    retriever = build_retriever(db, make_settings(storage_dir=tmp_path, embeddings_enabled=False))

    assert retriever.search(confirmed_patient, "how much sodium", 4)
    assert retriever.last_mode == "keyword"
