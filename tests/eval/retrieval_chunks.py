"""Retrieval over the chunks the app really makes, not the hand-written source lines.

`retrieval.py` measures the ranking on hand-written sources. This measures the whole path for
Patient 1: PDF text, chunker, medicine rows, alias expansion, ranking. A case passes when every
phrase that answers the question appears in the top 4 chunks.

Run by hand: `python -m tests.eval.retrieval_chunks [--embeddings]`. No model call; the
embedding model runs locally.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from app.ingestion.pdf_reader import read_pdf
from app.qa.aliases import expand_query
from app.qa.bm25 import bm25_rank
from app.qa.chunker import build_chunks
from tests.eval.retrieval import TOP_K, Ranker, hybrid_ranker
from tests.summary.helpers import confirmed

ROOT = Path(__file__).resolve().parents[2]
CASES_FILE = Path(__file__).with_name("retrieval_chunk_cases.json")
PDF = ROOT / "data/synthetic/patient1_discharge_summary.pdf"


@dataclass(frozen=True)
class ChunkResult:
    case_id: str
    question: str
    missing: list[str]  # phrases not found in the top 4 chunks

    @property
    def passed(self) -> bool:
        return not self.missing


def _flat(text: str) -> str:
    return " ".join(text.split()).casefold()


def run(ranker: Ranker = bm25_rank) -> list[ChunkResult]:
    profile = confirmed()
    chunks = build_chunks(read_pdf(PDF.read_bytes(), max_pages=30), profile)
    documents = [f"{chunk.section} {chunk.text}" for chunk in chunks]
    groups = [[m.name_as_written, *m.other_names] for m in profile.medicines]
    results = []
    for case in json.loads(CASES_FILE.read_text(encoding="utf-8"))["cases"]:
        query = expand_query(case["question"], groups)
        top = " ".join(_flat(documents[i]) for i in ranker(documents, query)[:TOP_K])
        missing = [p for p in case["must_find"] if _flat(p) not in top]
        results.append(ChunkResult(case["id"], case["question"], missing))
    return results


def report(results: list[ChunkResult]) -> str:
    hits = sum(r.passed for r in results)
    lines = [
        f"Answer found in the top {TOP_K} chunks: {hits}/{len(results)} "
        f"({hits / len(results):.0%})",
        "",
    ]
    for r in results:
        lines.append(f"{'ok  ' if r.passed else 'MISS'} {r.case_id:4} {r.question}")
        if r.missing:
            lines.append(f"       not found: {r.missing}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    print("== Keyword search only (BM25) ==")
    print(report(run()))
    if "--embeddings" in sys.argv:
        from app.config import get_settings
        from app.qa.embeddings import SentenceTransformerEmbedder

        settings = get_settings()
        model = SentenceTransformerEmbedder(settings.embedding_model)
        print(f"\n== Keywords plus meaning ({settings.embedding_model}) ==")
        print(report(run(hybrid_ranker(model, settings.embedding_min_similarity))))
