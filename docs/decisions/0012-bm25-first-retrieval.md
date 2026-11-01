# ADR-0012: BM25 + aliases first; embeddings only if a retrieval test fails

- **Status:** Superseded by ADR-0028
- **Date:** 2026-10 (recorded 2026-10-31)
- **Deciders:** team
- **Supersedes:** none

## Context

Each patient's searchable material is tiny: one discharge document (about 20–40 chunks) plus FDA label sections for 5–15 medicines. Drug names are exact words, and RxNorm already maps everyday and brand names to the generic name.

## Decision

- Phase 1: keyword search (**BM25**, `rank_bm25`) over that patient's chunks only, with the question expanded using the medicine's other names ("water pill" → furosemide, Lasix).
- Phase 2, **only if** `tests/eval/retrieval_cases.json` shows the right source in the top 5 less than 95% of the time: hybrid search (BM25 + embeddings), starting with a local open-source embedding model; vectors in SQLite.
- Chunking by document section, one chunk per medicine-table row, and FDA labels by label section (`CLAUDE.md` section 15).

## Alternatives considered

- **Embeddings from day one** — another service, cost, and privacy surface before we know it helps.
- **A hosted embedding provider** — a second vendor seeing patient text; needs a separate decision.

## Consequences

- Simple, fast, explainable retrieval to start.
- We must build the retrieval test, which also gives evidence for the report either way.
