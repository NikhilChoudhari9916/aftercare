from app.qa.bm25 import bm25_rank
from app.qa.embeddings import Embedder
from app.qa.vectors import build_index, nearest

RRF_K = 60  # the usual constant: it keeps one very high rank from outweighing the other list


def reciprocal_rank_fusion(rankings: list[list[int]], k: int = RRF_K) -> list[int]:
    """Merge ranked lists: a document scores 1/(k + rank) in each list it appears in."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, document in enumerate(ranking, start=1):
            scores[document] = scores.get(document, 0.0) + 1 / (k + rank)
    return sorted(scores, key=lambda document: (-scores[document], document))


def hybrid_rank(
    documents: list[str], query: str, embedder: Embedder, min_similarity: float
) -> list[int]:
    """Keyword and meaning-based search merged. Used by the retrieval test.

    Raises EmbeddingUnavailable if the model cannot run; the caller decides the fallback.
    """
    if not documents:
        return []
    vectors = embedder.embed(documents)
    close = nearest(build_index(vectors), embedder.embed([query])[0], min_similarity)
    return reciprocal_rank_fusion([bm25_rank(documents, query), close])
