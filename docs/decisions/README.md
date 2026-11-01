# Decision log (ADRs)

Every important project decision is recorded here as an **Architecture Decision Record (ADR)**: one short, numbered file that says what we decided, why, and what it costs us. This is how we keep a history of *why* the project looks the way it does.

## Rules

1. **One decision per file**, numbered in order: `NNNN-short-title.md`. Copy [`template.md`](template.md).
2. **Accepted ADRs are never rewritten.** To change a decision, write a **new** ADR that says `Supersedes: ADR-NNNN`, and change only the old one's status line to `Superseded by ADR-MMMM`. Git keeps the full history; the files keep the reasoning.
3. **Statuses:** `Proposed` (open for discussion) → `Accepted` (the team agreed) → `Superseded by ADR-NNNN` or `Deprecated`.
4. A new or changed ADR goes through a pull request like code. Accepting one needs approval from **both** other teammates.
5. When an ADR changes how we build things, update `CLAUDE.md` in the **same** pull request, so Claude Code follows the current decision.

## Index

| ADR | Decision | Status |
|-----|----------|--------|
| [0001](0001-record-decisions.md) | Record architecture decisions as ADRs | Accepted |
| [0002](0002-scope-explain-only.md) | Scope: explain only, adults, first 30 days, synthetic data | Accepted |
| [0003](0003-backend-and-ui-separation.md) | FastAPI backend; UI is a separate client over HTTP | Accepted |
| [0004](0004-two-pipelines-safety-in-code.md) | Two pipelines; fixed code decides whether safety checks run | Accepted |
| [0005](0005-three-tier-safety-gate.md) | Three-tier safety gate: rules + classifier run 3 times | Accepted |
| [0006](0006-deterministic-schedule.md) | Schedules, doses, and dates computed by code, never the LLM | Accepted |
| [0007](0007-digital-pdf-and-confirmation.md) | Digital PDFs only; patient confirms every extracted item | Accepted |
| [0008](0008-hand-written-agents.md) | Hand-written agents on the Anthropic SDK, with hard limits | Accepted |
| [0009](0009-streamlit-ui.md) | Streamlit for the MVP UI | Superseded by ADR-0010 |
| [0010](0010-nicegui-ui.md) | NiceGUI for the web UI | Accepted |
| [0011](0011-sqlite-sqlmodel.md) | SQLite + SQLModel for the MVP database | Accepted |
| [0012](0012-bm25-first-retrieval.md) | BM25 + aliases first; embeddings only if a retrieval test fails | Superseded by ADR-0028 |
| [0013](0013-local-storage-abstraction.md) | Local file storage behind `app/storage.py` | Accepted |
| [0014](0014-versioned-prompts-and-eval.md) | Prompts are versioned files, gated by the eval suite | Accepted |
| [0015](0015-team-git-workflow.md) | Protected `main`, reviewed PRs, pre-commit, and CI | Accepted |
| [0016](0016-claude-code-setup.md) | Coding principles in `CLAUDE.md`; two official plugins | Accepted |
| [0017](0017-public-repository.md) | Public GitHub repository from the start | Accepted |
| [0018](0018-model-choice.md) | Sonnet 5.5 for main work, Haiku 5.5 for fast checks, Opus when needed | Accepted |
| [0019](0019-python-312.md) | Python 3.12 for everyone and CI | Accepted |
| [0020](0020-s3-for-deployed-demo.md) | S3 storage only for the final demo; local for all development | Accepted (deferred to demo phase) |
| [0021](0021-google-sign-in-shared-login.md) | Google sign-in for identity only; patients and aides are the same kind of user | Sign-in stands; shared login superseded by ADR-0032 |
| [0022](0022-ics-first-calendar-later.md) | Downloadable `.ics` first; Google Calendar sync later | Accepted |
| [0023](0023-medlineplus-for-terms.md) | MedlinePlus as the cited source for plain-language terms | Accepted |
| [0024](0024-long-term-memory-deferred.md) | Long-term memory deferred; rules set now | Superseded by ADR-0029 |
| [0025](0025-diet-and-physio-agents-later.md) | Diet and physio agents planned as later specialists | Accepted |
| [0026](0026-third-party-skills.md) | Eight third-party Claude Code skills, with guardrails | Accepted |
| [0027](0027-fda-purpose-and-warnings-only.md) | openFDA labels contribute purpose and warnings only, never dosage | Accepted |
| [0028](0028-hybrid-retrieval-faiss.md) | Per-patient hybrid retrieval (BM25 + embeddings in FAISS) | Accepted |
| [0029](0029-long-term-memory-in-scope.md) | Short-term and long-term memory are in scope | Accepted |
| [0030](0030-deck-scope-and-pipeline.md) | Use cases, pipeline steps, and input scope from the Assignment 3 deck (PDF input only) | Accepted |
| [0031](0031-privacy-and-data-handling.md) | Privacy and data-handling rules from the Assignment 3 deck | Accepted |
| [0032](0032-invited-aides-limited-role.md) | Aides are invited by email and get a limited role | Accepted |
| [0033](0033-backend-owns-sign-in.md) | The backend owns Google sign-in and the session | Accepted |
| [0034](0034-in-process-job-runner.md) | Slow work runs as background jobs in an in-process runner | Accepted |
