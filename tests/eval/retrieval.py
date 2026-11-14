"""The retrieval test: does the right source come back in the top 4? (CLAUDE.md section 8)

Run by hand to see the numbers: `python -m tests.eval.retrieval`. The same code is used by
tests/qa/test_retrieval_eval.py so the result cannot drift. No model and no internet.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.qa.aliases import expand_query
from app.qa.bm25 import bm25_rank
from app.qa.embeddings import Embedder, SentenceTransformerEmbedder
from app.qa.hybrid import hybrid_rank

ROOT = Path(__file__).resolve().parents[2]
CASES_FILE = Path(__file__).with_name("retrieval_cases.json")
TOP_K = 4

# Given the documents and the question, returns document indexes, best first.
Ranker = Callable[[list[str], str], list[int]]


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    question: str
    expected: list[str]
    returned: list[str]  # the top 4 source IDs, best first

    @property
    def expects_nothing(self) -> bool:
        return not self.expected

    @property
    def passed(self) -> bool:
        if self.expects_nothing:
            return not self.returned
        return all(source in self.returned for source in self.expected)

    @property
    def best_rank(self) -> int | None:
        """Where the first expected source landed (1 is best), or None if none did."""
        ranks = [self.returned.index(s) + 1 for s in self.expected if s in self.returned]
        return min(ranks) if ranks else None


def load_sources(path: str) -> tuple[list[str], list[str]]:
    """The hand-written source lines: their IDs ("D1", "L2") and their text."""
    ids, texts = [], []
    for line in (ROOT / path).read_text(encoding="utf-8").splitlines():
        match = re.match(r"\[([DLT]\d+)\]\s*(.*)", line)
        if match:
            ids.append(match.group(1))
            texts.append(match.group(2))
    return ids, texts


def run(ranker: Ranker = bm25_rank) -> list[CaseResult]:
    data = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    sources = {key: load_sources(patient["sources"]) for key, patient in data["patients"].items()}
    results = []
    for case in data["cases"]:
        patient = data["patients"][case["patient"]]
        ids, texts = sources[case["patient"]]
        query = expand_query(case["question"], patient["medicines"])
        top = [ids[index] for index in ranker(texts, query)[:TOP_K]]
        results.append(CaseResult(case["id"], case["question"], case["expected"], top))
    return results


def report(results: list[CaseResult]) -> str:
    covered = [r for r in results if not r.expects_nothing]
    empty = [r for r in results if r.expects_nothing]
    hits = sum(r.passed for r in covered)
    lines = [
        f"Right sources in the top {TOP_K}: {hits}/{len(covered)} ({hits / len(covered):.0%})",
        f"Correctly empty when the papers do not cover it: "
        f"{sum(r.passed for r in empty)}/{len(empty)}",
        "",
    ]
    for r in results:
        mark = "ok  " if r.passed else "MISS"
        lines.append(f"{mark} {r.case_id:7} expected {r.expected} got {r.returned}")
    return "\n".join(lines)


def hybrid_ranker(embedder: Embedder, min_similarity: float) -> Ranker:
    return lambda documents, query: hybrid_rank(documents, query, embedder, min_similarity)


if __name__ == "__main__":
    import sys

    print("== Keyword search only (BM25) ==")
    print(report(run()))
    if "--embeddings" in sys.argv:
        from app.config import get_settings

        settings = get_settings()
        model = SentenceTransformerEmbedder(settings.embedding_model)
        print(f"\n== Keywords plus meaning ({settings.embedding_model}) ==")
        print(report(run(hybrid_ranker(model, settings.embedding_min_similarity))))
