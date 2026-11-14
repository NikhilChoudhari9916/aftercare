from typing import Literal

from sqlmodel import Session, select

from app.models import Chunk
from app.qa.aliases import expand_query
from app.qa.bm25 import bm25_rank
from app.qa.embedding_search import EmbeddingSearch
from app.qa.embeddings import EmbeddingUnavailable
from app.qa.hybrid import reciprocal_rank_fusion
from app.summary.profile import load_confirmed_profile
from app.tools.profile_tools import Passage


class Retriever:
    """Per-patient search over the confirmed papers. Fits the `DocumentSearch` the tools use.

    Every query starts with this patient's chunks, filtered here in code and never in a prompt
    (CLAUDE.md section 15, ADR-0031). It ranks by keywords (BM25) and, when an `EmbeddingSearch`
    is given, also by meaning, merging the two lists (ADR-0028). If the embedding model cannot
    run, it falls back to keywords and says so in `last_mode` (for QALog; no patient text).
    """

    def __init__(self, db: Session, embeddings: EmbeddingSearch | None = None) -> None:
        self._db = db
        self._embeddings = embeddings
        self.last_mode: Literal["keyword", "hybrid"] = "keyword"

    def search(self, patient_id: str, query: str, limit: int) -> list[Passage]:
        self.last_mode = "keyword"
        chunks = self._chunks(patient_id)
        if not chunks:
            return []
        question = self._expand(patient_id, query)
        ranked = bm25_rank([f"{chunk.section} {chunk.text}" for chunk in chunks], question)
        if self._embeddings is not None:
            try:
                close = self._embeddings.close_to(patient_id, chunks, question)
            except EmbeddingUnavailable:
                pass  # keywords only; `last_mode` tells the caller
            else:
                ranked = reciprocal_rank_fusion([ranked, close])
                self.last_mode = "hybrid"
        return [_passage(chunks[index]) for index in ranked[:limit]]

    def _chunks(self, patient_id: str) -> list[Chunk]:
        return list(
            self._db.exec(
                select(Chunk).where(Chunk.patient_id == patient_id).order_by(Chunk.position)
            ).all()
        )

    def _expand(self, patient_id: str, query: str) -> str:
        profile = load_confirmed_profile(self._db, patient_id)
        if profile is None:
            return query
        groups = [[m.name_as_written, *m.other_names] for m in profile.medicines]
        return expand_query(query, groups)


def _passage(chunk: Chunk) -> Passage:
    return Passage(id=chunk.ref, page=chunk.page, section=chunk.section, text=chunk.text)
