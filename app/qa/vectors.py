import faiss
import numpy as np


def build_index(vectors: np.ndarray) -> faiss.Index:
    """An exact inner-product index. With unit-length vectors the score is the cosine."""
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(np.ascontiguousarray(vectors, dtype=np.float32))
    return index


def nearest(index: faiss.Index, query: np.ndarray, min_similarity: float) -> list[int]:
    """Every stored vector at least `min_similarity` close to the query, closest first."""
    if index.ntotal == 0:
        return []
    similarities, positions = index.search(
        np.ascontiguousarray(query.reshape(1, -1), dtype=np.float32), index.ntotal
    )
    return [
        int(position)
        for similarity, position in zip(similarities[0], positions[0], strict=True)
        if position >= 0 and similarity >= min_similarity
    ]


def to_bytes(index: faiss.Index) -> bytes:
    return faiss.serialize_index(index).tobytes()


def from_bytes(data: bytes) -> faiss.Index:
    return faiss.deserialize_index(np.frombuffer(data, dtype=np.uint8))
