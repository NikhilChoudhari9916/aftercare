# Statements that disagree with the code (a list, not fixes)

Checked against `main` at commit `b216bdb`. **Nothing here has been fixed**; each line says what a
file claims and what the code shows. Line numbers are from the files as they stand on this branch.
Where an item could not be checked from the repository it says UNVERIFIED. Items already listed in
`security-review.md` section 7 are marked "also in the security review".

## Confirmed disagreements

| # | File : line | It says | The code shows |
|---|---|---|---|
| 1 | `docs/decisions/0004-two-pipelines-safety-in-code.md:16` | `app/agents/runner.py` always calls the gate first and the validators last | `app/agents/runner.py` does not exist (`app/agents/` holds `question_graph.py` and `upload_graph.py`). The graph does that job (`question_graph.py:425-454`). Also in the security review |
| 2 | `CLAUDE.md:225` | `app/agents/runner.py` is the fixed question pipeline | Same file, does not exist |
| 3 | `CLAUDE.md:199` | `app/agents/` holds `orchestrator.py`, `medication.py`, `schedule.py`, `summary.py`, `runner.py` | None of the five exist. Only `question_graph.py` and `upload_graph.py` do. See item 4 for the missing agents |
| 4 | `CLAUDE.md:101-104`, and section 2 "MVP (build now)" | An orchestrator plus a medication, a schedule and a summary agent | One specialist agent only. A router picks MEDICINE, SCHEDULE or OUT_OF_SCOPE (`question_graph.py:69-74`); schedule and out-of-scope replies are fixed text (60-66) |
| 5 | `CLAUDE.md:191` | `app/jobs/` holds `runner.py`, steps, and `cleanup.py` (scheduled) | `app/jobs/` holds `extraction.py`, `messages.py`, `runner.py`. `cleanup.py` does not exist |
| 6 | `CLAUDE.md:190, 192, 193, 195, 200, 208, 211` | Lists `auth/invites.py`; `memory/records.py` and `lifecycle.py`; `ingestion/scan_check.py` and `tables.py`; `enrichment/medlineplus.py`; `tools/schedule_tools.py` and `memory_tools.py`; `ui/components/citation_tag.py`, `followup_buttons.py`, `read_aloud.py`; `data/abbreviations.yaml` | None of these files exist. `CLAUDE.md:221` calls the list a "target layout, not a to-do list", so this is expected, but the file does not say which entries are built. `get_schedule` lives in `app/tools/profile_tools.py:67` |
| 7 | `CLAUDE.md:178` | Short-term memory is "last 10 turns plus a summary, focus medicine, pending question" | `app/memory/session.py` keeps the last turns and the focus medicine only (`Turn` and `Recall`, near the top of the file). No summary and no pending question. Also in the security review |
| 8 | `CLAUDE.md:157` | `eval_cases.json` has 31 cases | **33**. Counted by `python3 -c "import json; print(len(json.load(open('tests/eval/eval_cases.json'))['cases']))"`. `tests/qa/test_full_path.py:185` already asserts "33 cases x 3 runs = 99 questions" |
| 9 | `docs/handoff.md:16, 27, 55` | 31 cases (and "93 answers") | 33 cases (99 answers at 3 runs) |
| 10 | `docs/roadmap.md:23` | "Eval runs on all 31" | 33 |
| 11 | `docs/decisions/0041-safety-gate-design.md:33-34` | "31 eval questions" for the Tier 1 recall and the real-model measurement | The file has 33 cases. The line 34 measurement (2026-11-12, 31 questions) was made before the extra cases; whether it still holds is UNVERIFIED. Line 33 is also in the security review |
| 12 | `docs/handoff.md:9` | "Merge the open pull request from `feat/validators`" | `git log` shows it merged as #23 (`be0a136`) |
| 13 | `docs/handoff.md:38` | Nothing connects the gate, tools, retriever and validators: no question workflow, no `/ask`, no Ask page | All exist: `POST /patients/{id}/ask` (`app/qa/routes.py:146`), the graph (`app/agents/question_graph.py`), the page (`ui/pages/ask.py`); merged as #24 |
| 14 | `docs/handoff.md:40` | "878 tests pass with the open pull request; 741 on `main`" | The count has changed. The number on this branch is in the report that came with these docs |
| 15 | `docs/handoff.md:57` | Web UI pages: home, upload, confirm, summary, schedule | `ui/pages/ask.py` also exists |
| 16 | `docs/handoff.md:68-72` | B5, B5a (QALog "does not exist yet"), B5b to B5e are still to do | `QALog` exists (`app/models.py:213`); the endpoint, graph, profile text (`app/qa/profile_text.py`), tool context and session memory (`app/memory/session.py`) exist |
| 17 | `docs/decisions/0036-assignment-slice.md:20, 31` | The slice uses BM25 only | A hybrid retriever (keyword plus optional embeddings) is built (ADR-0043; `app/qa/hybrid.py`), and `embeddings_enabled` defaults to True (`app/config.py:65`). Whether the running demo uses embeddings depends on whether the optional package is installed: UNVERIFIED |
| 18 | `CLAUDE.md:240`, `236` (section 11) | Endpoints for symptoms, doses, saved questions, visit prep, memory, invites and access | None exist in `app/*/routes.py` (the routes are listed by `grep` for `@router`; there are none of these). Planned, not built; the file does not mark them as such |

## Need a person to judge (UNVERIFIED)

| File : line | It says | Why it could not be checked |
|---|---|---|
| `docs/assignment/platform-comparison.md:23-29` (the n8n and CrewAI columns) | For example: n8n limits "live in the tool's settings", is "harder to enforce and to test", "a separate service to run and secure", "excellent" diagrams; CrewAI "agents decide who works next", "built in, but agent-driven", "opposite of our rule" | Neither platform was built or run in this project; the file itself says they were "assessed against our requirements, not built" (lines 4-5) and to check current documentation. These cells are the team's opinion, not evidence. **UNVERIFIED** |
| `CLAUDE.md:5`, `docs/handoff.md:16, 20` | "No answer prompt has been run on the real model yet"; v7 "never run on the real model" | Local eval results exist on the author's machine (gitignored, `tests/eval/results/`), and live questions were run by hand, so this may be out of date. `prompts/PROMPT_LOG.md:11` still asks for the first full run to be recorded. Whether a validated v7 baseline exists is **UNVERIFIED** |
| `docs/architecture.md` | The diagrams | Not compared with the code in this pass |
| `docs/assignment/security-review.md` | Finding statuses | Checked against commit `4482838` (its own line 5). Statuses may have changed since; not re-checked here |
| `prompts/PROMPT_LOG.md` | The log rows | Not edited and not re-verified (rules for this task) |

## Not disagreements, but easy to misread

- `CLAUDE.md:221` says the folder layout is a target, so missing files in it are not errors on their own.
- Classifier reply limit: `main` has 200 tokens and takes the most serious tier named in a reply (`app/safety/classifier.py:20, 35-38`). A change to 1000 tokens and a strict reading is in pending PR #25 and is **not** on `main`.
