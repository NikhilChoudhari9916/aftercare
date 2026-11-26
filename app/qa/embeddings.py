import logging
import threading
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingUnavailable(Exception):
    """The embedding model cannot be used (not installed, not downloaded, or it failed).

    Search then falls back to keywords only (CLAUDE.md section 15). The message has no patient text.
    """


class Embedder(Protocol):
    """Turns texts into vectors: one row per text, unit length, so a dot product is a cosine."""

    def embed(self, texts: list[str]) -> np.ndarray: ...


def is_ready(embedder: Embedder) -> bool:
    """Whether `embed` can answer now without a long wait.

    An embedder with nothing to load (such as a test fake) is always ready.
    """
    return getattr(embedder, "is_ready", True)


def start_loading(embedder: Embedder) -> None:
    """Begin loading in the background, if this embedder has anything to load."""
    loader = getattr(embedder, "start_loading", None)
    if loader is not None:
        loader()


class SentenceTransformerEmbedder:
    """A small open-source model that runs on this machine, so no patient text leaves it."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model = None
        self._load_lock = threading.Lock()  # the model loads once, even if two threads ask at once
        self._loader_lock = threading.Lock()
        self._loader: threading.Thread | None = None

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    def start_loading(self) -> None:
        """Load the model in a background thread, so a patient's question never waits for it."""
        with self._loader_lock:
            if self.is_ready or (self._loader is not None and self._loader.is_alive()):
                return
            self._loader = threading.Thread(
                target=self._warm_up, name="embedding-warm-up", daemon=True
            )
            self._loader.start()

    def embed(self, texts: list[str]) -> np.ndarray:
        model = self._load()
        try:
            vectors = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        except Exception as error:  # the library raises many unrelated types
            raise EmbeddingUnavailable("The embedding model failed.") from error
        return np.asarray(vectors, dtype=np.float32)

    def _warm_up(self) -> None:
        try:
            self.embed(["warm up"])  # the first real encode also has set-up cost to pay up front
        except EmbeddingUnavailable:
            logger.warning("The embedding model could not be loaded; searches use keywords only.")

    def _load(self):
        with self._load_lock:
            if self._model is None:
                try:
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(self._model_name)
                except Exception as error:  # not installed, not downloaded, or no network
                    raise EmbeddingUnavailable("The embedding model is not available.") from error
            return self._model
