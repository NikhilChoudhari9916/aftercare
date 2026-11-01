# ADR-0028: Per-patient hybrid retrieval (BM25 + embeddings in FAISS)

- **Status:** Accepted
- **Date:** 2026-11-01
- **Deciders:** team
- **Supersedes:** ADR-0012

## Context

The Assignment 3 design deck specifies hybrid retrieval over a per-patient index. HW2 showed why plain keyword matching is not enough on its own: one medicine can be written two ways in the same paperwork ("Prinivil" and "lisinopril"), and strict grounding without retrieval was safe but thin (completeness 3.9 of 5). ADR-0012 planned BM25 first and embeddings only if a test failed. The team has now decided to build the deck's design.

## Decision

- **Hybrid search per patient:** keyword search (BM25, using the medicine's other names from the confirmed profile and RxNorm) plus embedding similarity. The two ranked lists are merged (reciprocal rank fusion).
- **Filter before searching:** by `patient_id`, and by the task's sections (for example a medicine question searches Discharge Medications and Hospital Course; visit prep searches Followup). The filter is enforced in code, never in the prompt.
- **Top 4 chunks.** Below a score threshold the answer is "That is not in your paperwork." The threshold is set from the retrieval test, not guessed.
- **Embeddings:** a local open-source model (sentence-transformers), so patient text never leaves the machine. The exact model is pinned in `app/config.py` when retrieval is built.
- **Index:** one FAISS index per patient (`faiss-cpu`), stored under `storage/patients/{patient_id}/index/` through `app/storage.py` and deleted with the patient's data. Public sources (RxNorm, openFDA, MedlinePlus) are cached separately and refreshed weekly.
- **External sources are called only when the paperwork chunks do not explain a term or medicine.**
- **Fallback:** if the embedding step fails, retrieval falls back to BM25 only and records that in `QALog` (no patient text).
- **Keep the retrieval test** (`tests/eval/retrieval_cases.json`). Compare BM25-only against hybrid and report both; target: the right source in the top 4 at least 95% of the time.
- Chunking is unchanged (`CLAUDE.md` section 15): by document section, one chunk per medicine row, FDA labels limited to purpose and warnings (ADR-0027).

## Alternatives considered

- **BM25 only, add embeddings if tests fail (ADR-0012)** — simpler, but the team chose the deck's design, and the comparison test still gives us the evidence.
- **A hosted embedding service** — a second vendor would see patient text.
- **A separate vector database** — more to run, and the per-patient corpus is tiny.

## Consequences

- New dependencies, approved here: `faiss-cpu` and `sentence-transformers` (which pulls in PyTorch, so installs are large). Exact versions are pinned in the pull request that adds them, after checking Python 3.12 support.
- CI and unit tests never download or run the real model; they use a small fake embedder.
- A new upload rebuilds that patient's index.
