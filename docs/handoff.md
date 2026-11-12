# Handoff: what is done, and what to pick up next

Written 2026-11-12 for the two teammates joining the build. Read [`TEAM_SETUP.md`](../TEAM_SETUP.md) first (about 15 minutes, and you can run the app **without any API key**), then this page, then [`CLAUDE.md`](../CLAUDE.md) sections 1 to 6 and 16.

**Deadlines:** the course assignment is due **Sunday Nov 15, 11:59 pm** (a thin end-to-end slice, [ADR-0036](decisions/0036-assignment-slice.md)). The full product plan in [`roadmap.md`](roadmap.md) continues after that.

## The state in one paragraph

A signed-in patient can upload a discharge PDF, have it read by the AI into a structured profile (every item with an exact quote from the papers), check and confirm each item, and then see a plain-language summary, a medicine schedule, and download a calendar file. The safety gate is built and tested but **no question can be asked yet**: the tools, retrieval, the validators, the question workflow and the Ask page are the big missing piece and are what the assignment grades most. All of it runs on synthetic data only.

## Done (merged to `main`, 383 tests passing)

| Area | What works | Where |
|---|---|---|
| Foundation | Config from `.env`, SQLite database, local file storage, `/health`, CI (ruff + pytest) | `app/config.py`, `db.py`, `storage.py`, `.github/` |
| Sign-in and roles | Google sign-in, server-side sessions, the owner/aide role check (`require_access`, 404 for strangers, 403 for the wrong role), denied-access audit events | `app/auth/` |
| Development test login | "Test patient Alex / Sam" buttons, refused in production and on non-local addresses ([ADR-0037](decisions/0037-dev-only-test-login.md)) | `app/auth/routes.py` |
| Upload and reading | PDF text check (scanned PDFs rejected), AI extraction into a typed profile, quote check, abbreviation cleanup (BID, PRN, ...), hidden-instruction scan, background job with progress | `app/ingestion/`, `app/extraction/`, `app/agents/upload_graph.py` (LangGraph), `app/jobs/` |
| Anthropic wrapper | The only module that imports the SDK; plain calls, **tool-use calls** (`complete(tools=...)`), structured output, typed errors, no patient text in errors | `app/llm.py` |
| Confirmation | Draft profile, per-item confirm / edit / remove, nothing used until confirmed | `app/documents/routes.py` |
| Summary, schedule, calendar | Plain code, confirmed items only, aide may read ([ADR-0040](decisions/0040-summary-schedule-calendar-from-code.md)) | `app/summary/` |
| Safety gate | `run_gate(question, context, llm=, settings=)`: fixed keyword rules (`data/red_flags.yaml`) plus the patient's own warning signs and medicine names, then a Haiku classifier run 3 times, most severe wins; Tier 1 returns the fixed 911 text and skips the model; any classifier problem counts as Tier 2 ([ADR-0041](decisions/0041-safety-gate-design.md)). Tier 1 recall is 100% on the 31 eval questions by rules alone, and `care_team_line()` builds the Tier 2 lead | `app/safety/`, `tests/safety/` |
| Web UI | Midnight-glass theme ([ADR-0039](decisions/0039-midnight-glass-theme.md)), self-hosted Inter font, pages: home, upload, confirm, summary, schedule; phone-friendly, accessible (contrast and tap-size tests) | `ui/` |
| Test helpers | `FakeLLM` (scripted model), `patient1_profile()` (what a good extraction looks like), PDF maker, sign-in helpers | `tests/fakes.py`, `tests/samples.py`, `tests/auth/helpers.py` |
| Demo without a key | Real backend with a fake model | `scripts/demo_backend.py` |
| Decisions | 40 ADRs; read the ones near your task | `docs/decisions/` |

## Not done, in the order to build it

Tracks are the ones in `CONTRIBUTING.md` (A documents, B safety and answers, C experience and testing). Each row is one or a few small PRs. **B1 to B5 are the critical path for the assignment**; the rest can run alongside.

| # | Task | Track | Needs | Done when |
|---|---|---|---|---|
| B1 | ~~Safety gate~~ **Built** (see Done). **Still to do for B1:** run the classifier on the real model over the eval questions, three runs each, and record Tier 1 recall (must be 100%) and any over-escalation in `prompts/PROMPT_LOG.md` (the safety classifier row says "Pending real run"). Call `run_gate` first in the question workflow (B5) from a worker thread | B | API key | Log row filled in; Tier 1 recall still 100% |
| B2 | **Tools** in one registry, each with a name, description, JSON schema and structured result: `get_confirmed_medicines`, `get_schedule` (call `build_schedule` in `app/summary/schedule.py`), `search_patient_document`, `search_fda_label`, `lookup_rxnorm`. External calls use `httpx`, timeouts and a cache. **FDA: purpose and warnings only, never dosage** ([ADR-0027](decisions/0027-fda-purpose-and-warnings-only.md)) | B / A | Network for real runs only | Unit tests with mocked HTTP; `app/tools/` |
| B3 | **Retriever.** Chunk the confirmed papers by section, one table row per chunk; BM25 (`rank_bm25`, ask before pinning the version); every query filtered by `patient_id` in code ([CLAUDE.md section 15](../CLAUDE.md)). FAISS and embeddings come later, behind the same `retriever.py` ([ADR-0028](decisions/0028-hybrid-retrieval-faiss.md)) | B | New package: team approval | **Two-patient leak test passes** before it merges |
| B4 | **Validators** (plain code): cited IDs were retrieved; doses, times and names match the confirmed profile; no dose-change advice or diagnosis; under about 40 words, about 6th-grade (`textstat` is already installed); Tier 2 includes the care team contact ([section 6](../CLAUDE.md)) | B | none | Unit tests per rule; safety review skill |
| B5 | **Question workflow** (LangGraph, same style as `upload_graph.py`): `safety_gate` (Tier 1 ends the graph) → `load_context` → `router` (Haiku) → medication agent ReAct loop with the tools → `validators` (retry once with the reason, then the safe fallback) → `finalize` (strip `<analysis>`). At most 6 tool calls, 30 s, depth 1, every call logged to `QALog` without patient text. Add `POST /patients/{id}/ask` (owner or aide) | B | B1 to B4, API key | Graph tests for each branch: Tier 1 bypass, tool cap, validator retry then fallback; role tests; leak test on `/ask` |
| B6 | **Prompts** as files in `prompts/`: classifier, router, summary; v7 stays the medication agent prompt. Every change goes through the `aftercare-prompt-change` skill and `prompts/PROMPT_LOG.md` | B | API key | Log row with before and after eval numbers |
| C1 | **Ask page** in `ui/`: chat box, citation tags ("From your papers, page N"), follow-up buttons, an always-visible 911 line. Reuse `ui/components/` and the theme; it must work at 375 px | C | B5's endpoint | Looks right on phone and desktop; contrast tests still pass |
| C2 | **Eval runner** `tests/eval/run_eval.py` over the 31 cases in `tests/eval/eval_cases.json` (right action, required facts, forbidden patterns, optional claims check; CSV out). Report Tier 1 recall and over-escalation | C | API key; run by hand (`pytest -m eval`), never in CI | A results table for the slides |
| A1 | **First real extraction run** on `data/synthetic/patient1_discharge_summary.pdf` (expect 6 medicines, amlodipine STOPPED, acetaminophen AS_NEEDED) and record it in `prompts/PROMPT_LOG.md` (the extraction row says "Pending real run") | A | API key | Log row filled in |
| A2 | **Enrichment** after confirmation: RxNorm aliases, openFDA purpose and warnings, cached; MedlinePlus definitions for terms in the papers ([ADR-0023](decisions/0023-medlineplus-for-terms.md), needs prompt v8 with the `[T#]` tag first) | A | B2 | Mocked-HTTP tests |
| A3 | Optional guard: say "this doesn't look like discharge papers" when an upload has no medicines or care-team details (today an unrelated PDF is read like any other, and the patient only sees whatever the AI found, which may be nothing) | A | none | Test with a non-medical PDF |
| Later | Long-term memory, symptom and dose logs, visit prep, aide invites and accepting them, the 30-day cleanup job, hybrid retrieval with FAISS, S3 for a hosted demo. Order and detail in [`roadmap.md`](roadmap.md) sprints 7 to 9 | all | | |

### For the assignment (due Sunday)

Still needed besides the code: a **workflow diagram**, a **comparison of at least two orchestration platforms with the one we chose** (LangGraph; reasons are in [ADR-0035](decisions/0035-langgraph-orchestration.md)), a short **challenges** write-up, and **3 to 5 slides** citing Claude and Claude Code and the data sources (synthetic Patient 1, HW2 samples, RxNorm, openFDA). Slides and the README must say the demo uses the **development test login**, not real Google sign-in. Everything on a slide must be something that actually ran.

If time runs short, cut in this order: UI polish, extra platforms in the comparison, repeat eval runs. **Never cut:** the safety gate, the validators, the confirmation step, tests, the slides.

## Rules that bite (the short list)

- **Safety is fixed code, not a prompt.** Agents decide *how* to answer; code decides *whether* the gate and validators run. Ask before changing any safety behavior.
- **Paperwork always wins.** FDA labels and glossary entries explain; they never override or add to what the patient's own papers say.
- **Nothing unconfirmed is ever used** in an answer, summary or schedule.
- **No patient text in logs or `QALog`.** IDs, counts and tool names only.
- **Only `app/llm.py` imports `anthropic`.** Model IDs live only in `app/config.py` (read from `.env`).
- **Prompts are files** in `prompts/`; a change makes a new version file and goes through the `aftercare-prompt-change` skill.
- **Never let the model compute doses, times or dates.** Code does.
- **Every patient query filters by `patient_id` first**, and every endpoint checks the role. Retrieval and memory need a two-patient leak test.
- **Ask before adding a package**, then pin it exactly in `requirements.txt`.
- **Synthetic data only.** Never commit `.env`, keys, `storage/` or `*.db`.
- Unit tests never call the real model or the internet. Use `FakeLLM` and mocked HTTP.

## Patterns to copy

- A new endpoint: `app/summary/routes.py` (owner and aide) or `app/documents/routes.py` (owner only), with the tests in `tests/summary/test_routes.py` (owner, aide, stranger, signed out, unconfirmed).
- A LangGraph workflow with branches: `app/agents/upload_graph.py` and `tests/agents/test_upload_graph.py`.
- A model call with a fake in tests: `app/extraction/extractor.py` and `tests/extraction/test_extractor.py`.
- A new UI page: `ui/pages/summary.py` and `ui/pages/schedule.py`; talk to the backend only through `ui/api_client.py` (never import from `app/` in `ui/`).

## Things to know

- **The demo backend's fake model** returns the Patient 1 profile for any PDF. Real reading needs your own `ANTHROPIC_API_KEY`.
- **Calendar reminders** cover the next 30 days from today (not from the discharge date), so they are never already over when someone opens the app late. Times use fixed everyday defaults (8:00, 13:00, 18:00, 21:00) in the phone's own time zone.
- **Aide role:** the role check and the aide's read access exist and are tested, but there is no invite or accept flow yet, so an aide only exists in tests.
- **No full `delete_patient()` yet.** `app/storage.py` can delete a patient's files; the database rows and (later) the search index need to join it ([roadmap](roadmap.md) finding 8).
- **The UI does not reload itself.** Restart `python -m ui.main` after editing UI code.
- **Branch protection** asks for one review. The repo owner has been merging stacked PRs with the bypass option; with three people, review each other's PRs.
- `CONTRIBUTING.md` still has `_name_` placeholders for who owns which track. Fill them in at your first sync.
- Google sign-in with a real test client is optional until the demo. Each person uses their own Google project and keys (see `TEAM_SETUP.md`); never share keys or put them in the repo.
