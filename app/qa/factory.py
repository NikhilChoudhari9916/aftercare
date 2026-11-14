from functools import lru_cache

from sqlmodel import Session

from app.config import Settings
from app.qa.embedding_search import EmbeddingSearch
from app.qa.embeddings import SentenceTransformerEmbedder
from app.qa.retriever import Retriever


@lru_cache
def _embedder(model_name: str) -> SentenceTransformerEmbedder:
    """One model per process. It loads on first use, so building it costs nothing."""
    return SentenceTransformerEmbedder(model_name)


def build_retriever(db: Session, settings: Settings) -> Retriever:
    """The retriever the question workflow uses: keywords plus meaning, when enabled.

    If the embedding model is not installed or cannot load, each search falls back to keywords
    and `Retriever.last_mode` says so (CLAUDE.md section 15).
    """
    if not settings.embeddings_enabled:
        return Retriever(db)
    embeddings = EmbeddingSearch(
        _embedder(settings.embedding_model),
        model_name=settings.embedding_model,
        min_similarity=settings.embedding_min_similarity,
        storage_root=settings.storage_dir,
    )
    return Retriever(db, embeddings)
