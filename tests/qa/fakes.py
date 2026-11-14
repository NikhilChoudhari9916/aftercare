import re
import zlib

import numpy as np

from app.qa.embeddings import EmbeddingUnavailable

WORD_DIMS = 48


class ConceptEmbedder:
    """A pretend embedding model. Texts that use words of one concept share a dimension, the way
    a real model puts "water pill" near "furosemide"; other words are spread by hashing.
    """

    def __init__(self, concepts: dict[str, set[str]] | None = None) -> None:
        self._concepts = concepts or {}
        self.calls = 0
        self.broken = False

    def embed(self, texts: list[str]) -> np.ndarray:
        self.calls += 1
        if self.broken:
            raise EmbeddingUnavailable("The embedding model is not available.")
        names = sorted(self._concepts)
        vectors = np.zeros((len(texts), len(names) + WORD_DIMS), dtype=np.float32)
        for row, text in enumerate(texts):
            lowered = text.casefold()
            for column, name in enumerate(names):
                if any(word in lowered for word in self._concepts[name]):
                    vectors[row, column] = 3.0
            for word in re.findall(r"[a-z0-9]+", lowered):
                vectors[row, len(names) + zlib.crc32(word.encode()) % WORD_DIMS] += 1.0
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.where(norms == 0, 1.0, norms)


DIURETIC = {"diuretic": {"water pill", "furosemide", "lasix", "diuretic"}}
