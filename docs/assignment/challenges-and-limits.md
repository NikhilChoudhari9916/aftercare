# Key challenges and limitations

Written for the Assignment 4 slides. Everything here is checked against the code on `main` or marked
**UNVERIFIED**. Nothing is presented as done unless a file, line or test says so. A "pending PR"
item is **not** on `main`.

## Limits in the code (each one read from the code)

| Limit | Value | Where | Note |
|---|---|---|---|
| Tool calls per question | 6 | `app/config.py:47`, enforced at `app/agents/question_graph.py:329-330` | Counted across the retry, not per attempt |
| Agent time limit | 30 s | `config.py:48`, checked at `question_graph.py:294` | **Checked only before each model call.** A call already running is not interrupted |
| Classifier timeout | 10 s | `config.py:55`, `app/safety/classifier.py:77` | Applies to the 3 runs together. After it, `shutdown(wait=False)` leaves slow calls running in the background (`classifier.py:78`) |
| One model call | 60 s, with 2 SDK retries | `config.py:43`, `app/llm.py:81` | The security review (F6) estimates one call can take about 180 s with retries. That is reasoning from the settings; no test covers it |
| Question length | see below | `routes.py:58`, `routes.py:181`, `question_graph.py:263`, `ui/content.py:391` | |
| Session memory | last 10 turns | `config.py:53`, `app/memory/session.py` (`deque(maxlen=...)`), test `test_only_the_last_turns_are_kept` | Plus a cap of 500 conversations (`session.py:20`) and a 12-hour idle drop (`session.py:19`). The router reads only the last 4 turns (`question_graph.py:53`) |

**Question length, stated plainly:**
- **500 characters** is the real limit (`Settings.max_question_chars`, `config.py:52`). The server enforces it at `routes.py:181` and answers 422 with a friendly sentence. The UI repeats the number in `ui/content.py:391`, with a comment that it must match.
- **5000 characters** is only the request model's outer bound (`AskIn`, `routes.py:58`), there to reject an absurd body early.
- The same 500 is used a second time, for the router's *rewritten* question (`question_graph.py:263`): a longer rewrite is replaced by the patient's own words.
- A possible emergency in a question of any length gets the fixed 911 text before the length check (`routes.py:161-175`).

## Tool integration

- Tools are described MCP-style (name, description, JSON schema, typed result) in one registry (`app/tools/registry.py:34-48`). **It is not a running MCP server**; `platform-comparison.md` says the same.
- The registry holds 5 tools (`app/tools/__init__.py:8-18`); the one agent is given 4 (`question_graph.py:46-51`). Test: `test_the_agent_cannot_call_a_tool_it_was_not_given`.
- A bad tool call returns a plain error to the model instead of raising (`registry.py:71-87`; tests in `tests/tools/test_registry.py`). A tool that crashes also ends as a plain error (`question_graph.py:319-324`).
- `lookup_rxnorm` accepts any name up to 80 characters from the model and sends it to an outside service (`label_tools.py:54-77`). This is finding F7 in `security-review.md` and was open when that file was written.
- In the eval run, RxNorm was switched off and drug-label text came from synthetic stand-ins (`tests/eval/full_path.py:13`, `SourceLabels`, lines 86-97). So the eval says nothing about the live openFDA or RxNorm services.

## Orchestration logic

- There is **one specialist agent** (the medication agent). CLAUDE.md describes an orchestrator plus schedule and summary agents; they are not built (`app/agents/` holds only `question_graph.py` and `upload_graph.py`).
- The router is a small model that picks one of three routes (`Route`, `question_graph.py:69-74`). Its failure sends the question to the agent (255-256), and a Tier 2 question is forced to the agent (259-260).
- **Schedule and out-of-scope replies are fixed text written in code** (`SCHEDULE_REPLY`, `OUT_OF_SCOPE_REPLY`, lines 60-66). The schedule itself is built by code, not by the model (`app/summary/schedule.py:304`).
- A Tier 3 question that the router calls SCHEDULE or OUT_OF_SCOPE gets a fixed reply with no symptom check. This was finding F10, which the security review marks as partly fixed.
- Diet questions and visit prep have no dedicated path. See `use-case-map.md`.

## Context management

- The confirmed profile is written out as text and put in the prompt (`app/qa/profile_text.py`). Passages and drug labels come in through tool results as `D#` and `L#` IDs.
- The agent does not see earlier turns. The router sees the last 4 and rewrites the question, so "it" becomes a medicine name (`question_graph.py:186-198`).
- Short-term memory lives in the server's process memory, keyed by login session and patient (`session.py`). It is lost on restart and was not cleared on revoke when the security review was written (F9: fixed for logout only).
- **Long-term memory is not built**: no symptom log, dose log or saved questions exist in `app/` (searched `app/` and `ui/` for symptom, dose log and saved question; the only hits were unrelated).
- The search index is built on the first question, so that first question is slower (`docs/handoff.md`, "Things to know"; not re-tested here).

## Reliability

- Any error inside the graph ends in the safe fallback, not an error page (`run_question`, `question_graph.py:506-523`; test `test_a_crash_inside_the_graph_ends_in_the_fallback_not_an_error`).
- **Some answers fall back because the validators reject them.** The checks include `UNCITED_FACT` and `TOO_HARD` (`app/qa/validators.py:26-38`). The team has seen answers fall back for this reason; no count is given here, because no clean eval run exists yet. **The cause of some other fallbacks is not known** (see the evidence section).
- The validators are checks, not proof: nothing checks that a cited passage really supports a claim (`docs/handoff.md`, "Known limits"). The eval's optional claims check exists for that, but no clean run of it is reported here.

## Security

The full review is in [`security-review.md`](security-review.md). In short, and **with statuses as of that file** (it names the commit it was checked against):

- It found 1 high, 5 medium, 5 low and 3 info items, F1 to F14.
- The structure it confirms: the gate is the first graph node, no edge skips the validators, the agent's tools are read-only, the patient ID is fixed by the server, and no patient text goes to logs or `QALog`.
- The high item (F1) is that removed or edited paperwork can still be retrieved and cited, which breaks "nothing unconfirmed is used".
- Other themes: injected text in a document (F2), follow-up buttons that skip the validators (F5), no rate limit and cost exposure (F6), an unrestricted RxNorm tool (F7).
- Several items were fixed after the first write-up, and some stayed open. Read the status column there, not here. If it has changed since, that file wins.

Not covered by that review or by tests as far as this write-up could check: real Google sign-in (the demo uses the development test login, ADR-0037), a hosted deployment, and real patient data (synthetic data only, by rule).

## Evaluation

- `tests/eval/eval_cases.json` has **33 cases** across three synthetic patients. Counted with `len(json.load(...)["cases"])`. CLAUDE.md and the handoff still say 31.
- The cases use synthetic data only, and the patterns are regular expressions, so a scoring rule can be wrong. One false positive ("not to take two doses") is fixed on a separate branch.
- **Evals so far used one run per case.** They say nothing about stability from run to run. The rule in CLAUDE.md is three runs per case.
- Eval results are not committed (`tests/eval/results` is gitignored), so a reader of the repository cannot check any number.
- The prompt-only eval has the model write the 911 text itself; in the app, code does (`docs/handoff.md`). The full-path eval measures the real path.
- Over-escalation is a known risk (too many "call your care team" replies). No number for it is given here.

## Evidence we have, each with its caveat

1. **Six questions were run by hand on the real model through the Ask page.** Water pill; "Can I take it at night?" (safe fallback); chest pain (fixed 911 text, no model); swollen ankles (Tier 2); reminders (pointer to the Schedule page); car insurance (polite decline). *Caveat:* observed by hand, six questions, one run each, screenshots are on the team's machine and **not in this repository**. This is a demonstration, not a measurement.
2. **A classifier cut-off bug.** The reply limit was 200 tokens, so the model's thinking could use it up and the run was counted as a failed reading (Tier 2). The fix raises the limit to 1000 tokens and reads the reply strictly (the last non-empty line must be exactly `TIER n`). *Caveat:* **pending PR #25, not on `main`.** On `main` the limit is still 200 (`classifier.py:20`) and `parse_tier` still takes the most serious tier named anywhere in the reply (`classifier.py:35-38`). A wrong reading fails toward Tier 2, not Tier 3 (`classifier.py:87-89`).
3. **A later full-path eval run failed for 14 of 33 questions with an API error. The cause is unconfirmed** (it could be credits, a rate limit or an outage; the error text was not captured, and a change to capture it is a pending PR). **A clean eval run is PENDING. No numbers from that run are reported here.**

## Known limits, in one list

- The demo uses a **development test login**, not Google sign-in (ADR-0037; `app/auth/routes.py:142`).
- Evals so far: one run per case.
- Eval drug-label data are synthetic stand-ins, and RxNorm was off.
- Only one specialist agent.
- Schedule and out-of-scope replies are fixed text in code.
- Long-term memory is not built. Visit prep is not built. Aide invites are not built (the role check exists, but only tests create an aide; `docs/handoff.md`).
- Some answers fall back because validators reject them; the cause of some other fallbacks is not yet known.
- Photo and voice input, a diet agent and a physiotherapy agent are deferred by decision (CLAUDE.md section 2).
