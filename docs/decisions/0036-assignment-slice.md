# ADR-0036: A thin end-to-end slice for the assignment, with deliberate deferrals

- **Status:** Accepted
- **Date:** 2026-11-11
- **Deciders:** team
- **Supersedes:** none (reorders the roadmap; every deferred item stays in scope)

## Context

The course assignment is due Sunday Nov 15 and needs a working end-to-end workflow with tool use, orchestration, a simple UI covering two or three use cases, and slides. The roadmap would reach a working question-answering flow only in sprint 5 or 6. The team chose to pull a thin slice forward and keep synthetic data only.

## Decision

Build these three use cases end to end:
1. **Upload to summary:** upload the discharge PDF, extract medicines, the patient confirms, and a plain-language summary is shown.
2. **Cited question:** safety gate, router, a tool-using medication agent, validators, and a short cited answer.
3. **Schedule:** a medication schedule and downloadable calendar file, built by plain code (ADR-0006).

**Deliberately deferred (still in scope, restored to the roadmap after the assignment):**
- Hybrid retrieval with FAISS and embeddings (ADR-0028): the slice uses **BM25 only**.
- Long-term memory (ADR-0029): the slice keeps **short-term session memory only**.
- Aide invites and roles (ADR-0032), MedlinePlus definitions (ADR-0023), the scheduled 30-day cleanup and invite expiry.
- The full job runner features beyond what upload needs (ADR-0034): a minimal in-process runner with a `Job` table.

**Not deferred, because they are the safety case:** the safety gate with the fixed 911 message, the output validators, patient confirmation before anything is used, the two-patient access tests, and no patient text in logs (ADR-0031).

## Consequences

- The roadmap order changes: sprints 2 to 6 are replaced for now by this slice; `docs/roadmap.md` is updated.
- Prompts for extraction, routing, and classification are new and go through the `aftercare-prompt-change` skill; prompt v7 is reused for the medication agent.
- Slides report what actually ran, including the eval results and the limits of the BM25-only slice.
