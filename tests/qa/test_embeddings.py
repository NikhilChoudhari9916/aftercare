import sys

import numpy as np
import pytest

from app.qa.embeddings import EmbeddingUnavailable, SentenceTransformerEmbedder
from app.qa.hybrid import hybrid_rank, reciprocal_rank_fusion
from app.qa.vectors import build_index, from_bytes, nearest, to_bytes
from tests.qa.fakes import DIURETIC, ConceptEmbedder

DOCS = [
    "Weigh yourself every morning before breakfast",
    "Take furosemide 40 mg once daily in the morning",
    "Limit sodium to less than 2000 mg per day",
]


# --- merging two ranked lists ---


def test_a_document_high_in_both_lists_beats_one_that_tops_only_one():
    assert reciprocal_rank_fusion([[0, 1], [1]]) == [1, 0]
    assert reciprocal_rank_fusion([[5, 7], [7, 5]])[0] == 5  # a tie keeps the lower index


def test_a_document_found_by_only_one_list_is_kept():
    assert reciprocal_rank_fusion([[1], [2]]) == [1, 2]
    assert reciprocal_rank_fusion([[], []]) == []


# --- the vector index ---


def test_nearest_returns_the_close_vectors_closest_first_and_drops_the_far_ones():
    vectors = np.array([[1, 0], [0, 1], [0.8, 0.6]], dtype=np.float32)
    index = build_index(vectors)

    assert nearest(index, np.array([1, 0], dtype=np.float32), min_similarity=0.5) == [0, 2]
    assert nearest(index, np.array([1, 0], dtype=np.float32), min_similarity=0.95) == [0]


def test_an_index_survives_being_saved_and_loaded():
    index = build_index(np.eye(3, dtype=np.float32))

    again = from_bytes(to_bytes(index))

    assert nearest(again, np.array([0, 1, 0], dtype=np.float32), 0.5) == [1]


def test_an_empty_index_finds_nothing():
    assert nearest(build_index(np.zeros((0, 4), dtype=np.float32)), np.ones(4), 0.0) == []


# --- keyword and meaning together ---


def test_meaning_finds_what_the_words_miss():
    embedder = ConceptEmbedder(DIURETIC)

    ranked = hybrid_rank(DOCS, "what changed with my water pill", embedder, min_similarity=0.3)

    assert ranked[0] == 1  # furosemide, though "water pill" is not in it


def test_a_question_far_from_everything_returns_nothing():
    embedder = ConceptEmbedder(DIURETIC)

    assert hybrid_rank(DOCS, "zebra", embedder, min_similarity=0.9) == []


def test_no_documents_means_nothing_to_rank():
    assert hybrid_rank([], "anything", ConceptEmbedder(), 0.3) == []


def test_a_broken_model_raises_so_the_caller_can_fall_back():
    embedder = ConceptEmbedder()
    embedder.broken = True

    with pytest.raises(EmbeddingUnavailable):
        hybrid_rank(DOCS, "water pill", embedder, 0.3)


# --- the real model wrapper, without loading it ---


def test_a_model_that_cannot_be_loaded_is_reported_as_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)  # makes the import fail

    with pytest.raises(EmbeddingUnavailable, match="not available"):
        SentenceTransformerEmbedder("any-model").embed(["text"])
