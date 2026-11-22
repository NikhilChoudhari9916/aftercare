import re
from typing import Literal

from sqlmodel import Session, select

from app.models import Chunk, ChunkSource, DocumentPage, ProfileVersion, RetrievalState
from app.qa.aliases import expand_query
from app.qa.bm25 import bm25_rank
from app.qa.chunker import chunk_pages
from app.qa.embedding_search import EmbeddingSearch
from app.qa.embeddings import EmbeddingUnavailable
from app.qa.hybrid import reciprocal_rank_fusion
from app.qa.index import index_patient
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
        profile = load_confirmed_profile(self._db, patient_id)
        if profile is None:
            return []
        state = self._db.get(RetrievalState, profile.version_id)
        if state is None or state.patient_id != patient_id or not state.ready:
            # Do this before ranking or loading vectors: an old index can hold removed text.
            index_patient(self._db, patient_id)
        if profile.review_notices:
            return []
        chunks = list(
            self._db.exec(
                select(Chunk)
                .where(
                    Chunk.patient_id == patient_id,
                    Chunk.profile_version_id == profile.version_id,
                )
                .order_by(Chunk.position)
            ).all()
        )

        version = self._db.get(ProfileVersion, profile.version_id)
        if version is None or version.patient_id != patient_id:
            return []
        pages = list(
            self._db.exec(
                select(DocumentPage).where(
                    DocumentPage.patient_id == patient_id,
                    DocumentPage.document_id == version.document_id,
                )
            ).all()
        )
        approved = {(part.page, " ".join(part.text.split())) for part in chunk_pages(pages)}
        # Whole paragraphs also support fixed synthetic eval sources and legacy indexes.
        # A substring is insufficient: "take two tablets" must not match a cropped piece
        # of the original "Do not take two tablets" and lose its negation.
        approved.update(
            (page.number, " ".join(paragraph.split()))
            for page in pages
            for paragraph in re.split(r"\n\s*\n", page.text)
            if paragraph.strip()
        )
        return [
            chunk
            for chunk in chunks
            if (
                chunk.source == ChunkSource.DOCUMENT
                and (chunk.page, " ".join(chunk.text.split())) in approved
            )
        ]

    def _expand(self, patient_id: str, query: str) -> str:
        profile = load_confirmed_profile(self._db, patient_id)
        if profile is None:
            return query
        groups = [[m.name_as_written, *m.other_names] for m in profile.medicines]
        return expand_query(query, groups)


def _passage(chunk: Chunk) -> Passage:
    return Passage(
        id=chunk.ref,
        page=chunk.page,
        section=chunk.section,
        text=chunk.text,
        original_document=True,
    )
