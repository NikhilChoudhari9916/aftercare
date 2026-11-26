import json
import threading
from pathlib import Path

import faiss

from app.models import Chunk
from app.qa.embeddings import Embedder, EmbeddingUnavailable, is_ready, start_loading
from app.qa.vectors import build_index, from_bytes, nearest, to_bytes
from app.storage import get_index_file, save_index_file

INDEX_FILE = "vectors.faiss"
FINGERPRINT_FILE = "vectors.json"

_locks_guard = threading.Lock()
_patient_locks: dict[str, threading.Lock] = {}


def _patient_lock(patient_id: str) -> threading.Lock:
    """One lock per patient, so two questions (or a question and the warm-up after confirming)
    never read and write the same index files at once. Other patients are not held up.
    """
    with _locks_guard:
        return _patient_locks.setdefault(patient_id, threading.Lock())


class EmbeddingSearch:
    """Meaning-based search over one patient's chunks, with the vectors kept per patient.

    The index lives in the patient's own folder (storage/patients/{id}/index/) and is rebuilt
    when their chunks change. Vectors are health data: they are deleted with the patient.
    """

    def __init__(
        self,
        embedder: Embedder,
        *,
        model_name: str,
        min_similarity: float,
        storage_root: Path | None = None,
    ) -> None:
        self._embedder = embedder
        self._model_name = model_name
        self._min_similarity = min_similarity
        self._storage_root = storage_root

    def close_to(self, patient_id: str, chunks: list[Chunk], query: str) -> list[int]:
        """Positions in `chunks` that are close in meaning to the query, closest first.

        Raises EmbeddingUnavailable if the model cannot run, or is still loading: the caller then
        uses keywords for this one question instead of making the patient wait.
        """
        if not is_ready(self._embedder):
            start_loading(self._embedder)
            raise EmbeddingUnavailable("The embedding model is still loading.")
        index = self._index_for(patient_id, chunks)
        return nearest(index, self._embedder.embed([query])[0], self._min_similarity)

    def prepare(self, patient_id: str, chunks: list[Chunk]) -> None:
        """Build the patient's vectors now (loading the model if needed), so a question need not.

        Raises EmbeddingUnavailable if the model cannot run.
        """
        self._index_for(patient_id, chunks)

    def _index_for(self, patient_id: str, chunks: list[Chunk]) -> faiss.Index:
        with _patient_lock(patient_id):
            return self._load(patient_id, chunks) or self._build(patient_id, chunks)

    def _fingerprint(self, chunks: list[Chunk]) -> bytes:
        # Chunk IDs are new on every re-index, so any change to the papers invalidates the index.
        return json.dumps({"model": self._model_name, "chunks": [c.id for c in chunks]}).encode()

    def _load(self, patient_id: str, chunks: list[Chunk]) -> faiss.Index | None:
        if self._storage_root is None:
            return None
        saved = get_index_file(self._storage_root, patient_id, FINGERPRINT_FILE)
        data = get_index_file(self._storage_root, patient_id, INDEX_FILE)
        if saved is None or data is None or saved != self._fingerprint(chunks):
            return None
        return from_bytes(data)

    def _build(self, patient_id: str, chunks: list[Chunk]) -> faiss.Index:
        index = build_index(self._embedder.embed([f"{c.section}. {c.text}" for c in chunks]))
        if self._storage_root is not None:
            save_index_file(self._storage_root, patient_id, INDEX_FILE, to_bytes(index))
            save_index_file(
                self._storage_root, patient_id, FINGERPRINT_FILE, self._fingerprint(chunks)
            )
        return index
