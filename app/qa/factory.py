import logging
from functools import lru_cache

from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.config import Settings
from app.qa.embedding_search import EmbeddingSearch
from app.qa.embeddings import EmbeddingUnavailable, SentenceTransformerEmbedder
from app.qa.retriever import Retriever

logger = logging.getLogger(__name__)


@lru_cache
def _embedder(model_name: str) -> SentenceTransformerEmbedder:
    """One model per process. It loads on first use, so building it costs nothing."""
    return SentenceTransformerEmbedder(model_name)


def _warm_up_on(settings: Settings) -> bool:
    return settings.embeddings_enabled and settings.embeddings_warm_up


def warm_embedder(settings: Settings) -> None:
    """Start loading the embedding model in the background when the backend starts."""
    if _warm_up_on(settings):
        _embedder(settings.embedding_model).start_loading()


def warm_patient_index(engine: Engine, settings: Settings, patient_id: str) -> None:
    """Build a patient's meaning index in the background right after they confirm.

    Best effort: the patient has already confirmed, and a question builds the index itself if
    this did not finish. So a failure is logged (with no patient text), never raised.
    """
    if not _warm_up_on(settings):
        return
    try:
        with Session(engine) as db:
            build_retriever(db, settings).warm(patient_id)
    except EmbeddingUnavailable:
        logger.warning(
            "The search index could not be warmed up: the embedding model is unavailable."
        )
    except Exception as error:
        logger.warning("The search index could not be warmed up (%s).", type(error).__name__)


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
