# Roadmap: sprints

One-week sprints, three people, three tracks. Every sprint ends with something that can be demoed, and `main` stays working. This plan follows the build order in `CLAUDE.md` section 12. Add the real end date and adjust the number of sprints.

**Tracks** (see `CONTRIBUTING.md`): **A** Documents (ingestion, extraction, enrichment, storage), **B** Safety and answers (gate, retrieval, agents, validators), **C** Experience and testing (NiceGUI, summary, schedule, eval runner).

**Right now one person is building.** Onboarding the other two is postponed. Until they join, work through the columns in order (A, then B, then C within each sprint). The table shows what can run in parallel once they do.

**Working agreement:** sprint planning on day 1 (pick issues, one task = one issue = one pull request), a short written standup on working days, a demo and retro on the last day. A task is done when it is merged, its tests pass in CI, and it follows the checklist in the PR template.

## Sprints

| Sprint | Goal (what you can demo) | A: Documents | B: Safety and answers | C: Experience and testing |
|---|---|---|---|---|
| 0 | The foundation is built and the two decisions that block week 1 are made | Foundation (build step 1): folders, `config.py`, tables, `storage.py`, load synthetic patients | Decisions made: backend owns sign-in (ADR-0033) and the in-process job runner (ADR-0034) | CI green on an empty test suite; one Google OAuth test client for local sign-in |
| 1 | **Sign in with Google and see "Hello" on a phone-width page** | Backend sign-in: `User`, `Patient`, `PatientAccess` (owner only), `/auth/*`, `/me`, role check | `red_flags.yaml` and the keyword rules (needs no login) | NiceGUI login page, signed-in home page, `api_client.py`; the two-process session works end to end |
| 2 | **Upload a PDF and see a job finish** | Job runner and `Job` table; upload endpoint; scan check; `delete_patient()` that grows with each store | Safety classifier (3 runs, most severe wins) and the gate; Tier 1 recall must be 100% | Schedule and `.ics` export (plain code, no login or AI needed) |
| 3 | **Extraction on the sample PDF yields 6 medicines, with a confirmation screen** | AI extraction, quote check, abbreviation cleanup; the hidden-instruction scan | Gate wired to the eval cases; eval runner starts | Confirmation screen (side-by-side with the original line); summary screen |
| 4 | **Enriched profile** | RxNorm, openFDA purpose and warnings, MedlinePlus definitions, cached | Chunking; hybrid retriever behind `retriever.py` (FAISS hidden behind it, finding 5); retrieval test | Upload, status, and confirm pages polished; `.ics` download button |
| 5 | **Ask a question and get a short cited answer** | Re-index when a profile changes | Medication agent, validators, short-term session memory; two-patient leak test | Ask page: citation tags, follow-up buttons, read-aloud |
| 6 | **Multi-part questions and diet questions** | Support the orchestrator's tools | Orchestrator, schedule and summary agents; prompt v8 with the `[T#]` tag | Eval runs on all 31 cases; fix failures |
| **Core demo** | Sign in, upload, confirm, summary, schedule, cited Q&A, safety gate | | | |
| 7 | **Visit prep and logs** | Memory records and the 30-day cleanup job | Long-term memory read tools; visit-prep agent | Symptom, dose, and saved-question pages; visit-prep page |
| 8 | **Aide access** | Invites, `PatientAccess` aide role | Role tests; run `security-reviewer` | Aide banner and access page |
| 9 | **Release** | Final cleanup | Full eval and report | README, demo video, public repo polish; optional S3 for a hosted demo (ADR-0020) |

If time runs short, cut from the bottom: sprints 7 and 8 are the stretch (finding 4). Everything above the **Core demo** line is the product.

## Why sign-in and the backend are one slice

- It proves the riskiest wiring first: the UI and the backend are separate processes, so the session has to cross between them.
- It gives all three people something to hang work on in week two.
- Track B's safety rules and track C's schedule code need no login, so nobody waits on sprint 1.

## Findings from the architecture review, and when to raise them

| # | Finding | Raise it in |
|---|---|---|
| 1 | Upload is slow; use a small in-process job runner with a `Job` table and a status endpoint, not Celery | **Decided (ADR-0034)**; built in sprint 2 |
| 2 | Decide which process owns Google sign-in and holds the session | **Decided (ADR-0033)**: the backend owns it; built in sprint 1 |
| 3 | The 30-day deletion and invite expiry need a scheduled cleanup job on the same runner as finding 1 | Sprint 7 |
| 4 | Scope fits about 9 sprints for three people; sprints 7 and 8 are the cut line | Sprint planning, every sprint |
| 5 | FAISS plus PyTorch is heavy for 30–60 vectors per patient; keep it behind `retriever.py` so it can be swapped | Sprint 4 |
| 6 | Encryption of memory records needs a key plan before any real data: record it as an ADR first | Sprint 7 |
| 7 | Config must refuse to start with `LOG_PATIENT_TEXT=1` outside development | Sprint 0 (`config.py`) |
| 8 | One `delete_patient()` removes the database rows, PDFs, and index together, with a test | Starts in sprint 2; extended in sprints 4 and 7 |

Other prompts to raise when the time comes: before sprint 2, adding `requirements.txt` needs the team's approval of each new package (`CLAUDE.md` section 16); before sprint 4, approve `faiss-cpu` and `sentence-transformers` and pick the embedding model; before sprint 6, the prompt v8 change goes through `aftercare-prompt-change`.
