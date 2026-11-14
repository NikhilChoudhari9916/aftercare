from typing import Protocol

import numpy as np


class EmbeddingUnavailable(Exception):
    """The embedding model cannot be used (not installed, not downloaded, or it failed).

    Search then falls back to keywords only (CLAUDE.md section 15). The message has no patient text.
    """


class Embedder(Protocol):
    """Turns texts into vectors: one row per text, unit length, so a dot product is a cosine."""

    def embed(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    """A small open-source model that runs on this machine, so no patient text leaves it."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model = None

    def embed(self, texts: list[str]) -> np.ndarray:
        model = self._load()
        try:
            vectors = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        except Exception as error:  # the library raises many unrelated types
            raise EmbeddingUnavailable("The embedding model failed.") from error
        return np.asarray(vectors, dtype=np.float32)

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self._model_name)
            except Exception as error:  # not installed, not downloaded, or no network
                raise EmbeddingUnavailable("The embedding model is not available.") from error
        return self._model
