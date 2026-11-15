# Security and safety review of `POST /patients/{id}/ask`

**Scope and method.** I read everything on your list and ran the relevant tests: 203 passed, and `ruff` is clean. I made no edits and called no model. Some findings come from reading the code and were not run end to end; I mark where I did run something.

## Executive summary

The structure is sound:
- The gate is the graph's first node, and no edge skips the validators.
- The agent has four read-only tools, and the patient ID is fixed by the server.
- No patient text reaches the logs or `QALog`.
- The UI escapes model text before building HTML.

I found **1 high, 5 medium, 5 low and 3 info** items. The high one is a rule from CLAUDE.md that the code does not enforce.

| ID | Sev | Title |
|---|---|---|
| F1 | **High** | Removed or edited paperwork stays searchable and citable |
| F2 | Medium | An injected document line is flagged but still indexed, and the validators pass it |
| F3 | Medium | Some paths reach a patient with no gate: unconfirmed papers, over 500 characters, pre-graph errors |
| F4 | Medium | Tier 2 failures end in the pharmacist fallback, not the care-team line |
| F5 | Medium | Follow-up buttons bypass the validators |
| F6 | Medium | No rate limit; thread, cost and timeout exposure |
| F7 | Low | `lookup_rxnorm` can send arbitrary text to an outside service |
| F8 | Low | Tag defanging is incomplete (`<rules>`, `<inputs>` and others) |
| F9 | Low | Session memory is never cleared at logout or revoke |
| F10 | Low | The rewritten question is not re-gated, and a Tier 3 symptom can route to a fixed reply |
| F11 | Low | A patient can spoof the app note |
| F12–14 | Info | See below |

## Findings

**F1, High. Removed or edited paperwork is still retrievable.**
- **Where:** `app/qa/index.py:28`, `app/qa/chunker.py:27-39,65-66`.
- **What:** `build_chunks` chunks the raw page text. Only the medicine-row chunks respect the confirmed profile.
- **Demonstrated:** I ran the chunker on a page containing "Start warfarin 5 mg…" with warfarin removed from the profile. The page chunk still held the warfarin line. The `index.py` docstring claims a removed medicine "can never be found again", which is false for page chunks.
- **Impact:**
  - It breaks "nothing unconfirmed is ever used in answers" (CLAUDE.md section 2, and safety-review item 7).
  - If extraction hallucinated a medicine, or the patient corrected a dose, the original text can still be retrieved and cited.
  - The validators count cited chunk text as known (`validators.py:152-164`), so such an answer passes.
- **Fix:** Build page chunks only from text that supports confirmed items. Alternatively, drop any chunk that contains a medicine name or quote the patient removed, and add a test for it.
- **User-visible:** Yes. Some answers become "not in your papers".

**F2, Medium. Indirect injection from an uploaded document.**
- **Where:** `app/agents/upload_graph.py:53`, `ui/pages/confirm.py:153`, `app/qa/index.py`, `app/qa/validators.py:363-423`.
- **What:** The upload scan only produces a warning on the confirm page. Flagged lines are still indexed. Retrieved text goes to the model in a `tool_result` (not the system prompt), which is the right place for it.
- **Impact:**
  - A sentence like "Your papers say you should stop all medicines" passes the validators, because `_check_advice` deliberately skips attributed text.
  - A cited, attributed fake phone number passes too. `_check_uncited` accepts any sentence that carries a `[D#]` tag.
  - I reasoned this from the regexes and did not run it end to end.
- **Fix:** Exclude flagged lines from chunks, or label them so the agent says "this line looks like an instruction". Consider also rejecting an attributed stop, skip or double instruction unless it matches a confirmed STOPPED medicine.
- **User-visible:** Rarely.

**F3, Medium. Paths with no gate.**
- **Where:** `app/qa/routes.py:136-146`.
- **What:** Before the graph runs, the route returns 404 if the papers are not confirmed, and 422 if the question is over 500 characters. Errors in prompt or profile loading there become a 500. In all three cases the gate has not run.
- **Impact:** Someone describing chest pain at length, or asking before confirming, gets no 911 text. The not-confirmed page (`ui/layout.py:58`) has no 911 banner either.
- **Fix:** Run the keyword rules on the full text first, with an empty context if there is no profile. Return the fixed text on Tier 1 before any other check.
- **User-visible:** Yes, only in those cases.

**F4, Medium. Tier 2 fallback.**
- **Where:** `app/agents/question_graph.py:366-373,493-501`, `app/qa/validators.py:121-126`.
- **What:** `care_team_line` is never called anywhere in `app/`. Tier 2 relies on the model writing the lead, and the validators checking it. If it fails twice, or the graph errors (where `tier` is forced to `CARE_TEAM`), the patient gets "call your pharmacist". ADR-0041 says the workflow uses `care_team_line`, and CLAUDE.md section 4 says the merged reply must lead with it.
- **Fix:** For Tier 2, make the fallback start with `care_team_line(...)` before the generic text.
- **User-visible:** Yes.

**F5, Medium. Follow-ups are unvalidated.**
- **Where:** `app/agents/question_graph.py:383`, `app/qa/answer_text.py:25`.
- **What:** The follow-up lines are cut out before validation and shown as buttons, up to 3, with no length cap. A manipulated reply can put advice or a phone number in a button. Clicking one goes through the gate as a normal question.
- **Fix:** Cap their length. Run the diagnosis, advice, unknown-medicine and phone checks on them too, and drop any that fail.
- **User-visible:** Rarely.

**F6, Medium. Abuse, cost and reliability.**
- **Where:** `app/qa/routes.py:123`, `app/safety/classifier.py:75-78`, `app/llm.py:77-82`, `app/config.py` (`llm_timeout_seconds` 60), `app/agents/question_graph.py:273`.
- **What:**
  - There is no per-user rate or concurrency limit. One question is up to about 4 fast-model calls plus up to about 8 Sonnet calls, each with 3000 output tokens.
  - The 30-second limit is checked only before each agent call. A single call can run 60 seconds with 2 SDK retries, so about 180 seconds.
  - Each request holds a worker thread. Roughly 40 concurrent slow requests can starve the rest of the API.
  - On a classifier timeout, `shutdown(wait=False)` leaves the model calls running.
  - The UI `busy` flag is client-side only.
- **Fix:** Add a per-user and per-patient limit, plus a concurrency cap. Set a hard per-question deadline, and a shorter client timeout with fewer retries on this path.
- **User-visible:** Only for abusers.

**F7, Low. `lookup_rxnorm` is unrestricted.**
- **Where:** `app/tools/label_tools.py:55-79`, `app/enrichment/rxnorm.py`.
- **What:** The model chooses `name` (up to 80 characters), which is sent to the NLM service. `search_fda_label` is limited to confirmed medicines; this tool is not. An injected instruction could use up to 6 calls to leak a few hundred characters.
- **Fix:** Allow only confirmed names, or names that appear in the question.

**F8, Low. Defanging gap.**
- **Where:** `app/agents/question_graph.py:69-73`.
- **What:** The list covers 7 tags. The v7 prompt also uses `inputs`, `rules`, `role`, `workflow`, `examples`, `output_format` and `context`. A question containing `</question></inputs><rules>…` keeps the `inputs` and `rules` parts inside the system prompt. The gate and validators still apply, so this affects behavior, not safety. The profile text in `{patient_profile}` is not defanged either.
- **Fix:** Neutralize every angle bracket, the way the classifier already does (`classifier.py:53`).

**F9, Low. Memory lifecycle.**
- **Where:** `app/memory/session.py:92-96`.
- **What:** `forget()` has no callers. ADR-0031 says transcripts clear when the session ends. In practice they stay in RAM for up to 12 hours idle, even after logout or an aide revoke. They are reachable only through the same hashed session key, and the idle sweep runs only when another call arrives.
- **Fix:** Call `forget` at logout, and drop a patient's entries on revoke or delete.

**F10, Low.**
- **Where:** `app/agents/question_graph.py:223-259`.
- **What:** The gate sees the original question, but the agent sees the router's rewrite. The "never remove a symptom" rule is only in the prompt. A Tier 3 message the router calls SCHEDULE or OUT_OF_SCOPE gets a fixed reply with no symptom check. The OUT_OF_SCOPE reply does at least name the care team.
- **Fix:** Send any message with a symptom word to the agent, and compare the rewrite with the original.

**F11, Low.**
- **Where:** `app/agents/question_graph.py:182-188`.
- **What:** A patient can type their own "(App note… TIER 3)". It cannot lower the real tier, because the validators use the code's tier, and the model can only raise it.
- **Fix:** Defang it, as in F8.

**Info**
- **F12:** Injected text that makes the model emit the 911 sentence is accepted and shown as an emergency (`question_graph.py:337`). That is a safe-direction false alarm.
- **F13:** The route holds a DB session across model calls. The embedding model loads lazily in the request thread, so a first-request race is possible.
- **F14:** Index files are written through a temp file and `replace`, so writes are atomic.

## Question-by-question answers

**1. Access and isolation.**
- **Who may ask:** Owner and aide, through `require_access`. No access returns 404 and the wrong role returns 403, both logged as IDs only. Revoke and expiry are checked on every request.
- **What the leak test proves:** `tests/qa/test_ask_api.py:230` proves one thing. With the keyword retriever, `search_patient_document` returns none of patient B's chunks, and asking as B returns 404.
- **Not covered:**
  - the hybrid and embedding path and its per-patient index files
  - `get_confirmed_medicines` and `search_fda_label` across patients
  - session memory across users or patients
  - the shared RxNorm and openFDA cache
  - concurrent requests

  The isolation holds in the code: `ToolContext.patient_id` is set by the server, and memory is keyed by session and patient. It is just not all tested.

**2. Gate.**
- **No bypass inside the graph:** There is no edge that skips the gate or the validators.
- **AI service down:** Keyword Tier 1 still works with the service down (tested). A classifier failure counts as Tier 2.
- **Tier 2 forcing:** The router cannot override it.
- **Exceptions to the "gate first" rule:** F3 lists the paths that run before the graph.

**3. Injection.**
- **What an injected sentence can do:** With its four tools it can only produce text. It can also call `lookup_rxnorm` (F7). The validators block uncited facts, unknown dose amounts and times, diagnosis and unattributed advice. They cannot block attributed or cited content (F2).

**4. Output handling.**
- **Result:** The escaping is correct. `answer_html` escapes first, then builds only `<b>`, a constant-styled span and `<br>`. Labels are server-built and escaped. Buttons, labels and alerts are text-only. `tests/ui/test_ask_content.py:26` covers `<script>` and `onerror`. Keep that test if `sanitize=False` stays.

**5. Privacy.**
- **Result:** All four logger calls record only a type, a name, or a file and line. `QALog` has no text. Exceptions are caught and replaced with constant messages. The only on-disk patient-derived data is the embedding index (health data, which ADR-0031 says to delete with the patient).

**6. Abuse.** See F6. The 500-character limit holds on the server. Session memory is bounded at 500 conversations × 10 turns. `LOG_PATIENT_TEXT` is refused in production (`app/config.py:91`). The recursion limit of 60 is not reachable within the tool cap, and an overrun would end in the fallback.

**7. Docs and ADRs that disagree with the code:**
- ADR-0004 and the safety skill name `app/agents/runner.py`, which does not exist. The graph in `question_graph.py` does that job.
- ADR-0041 says `care_team_line` leads Tier 2 answers. It is unused (F4).
- ADR-0031 and CLAUDE.md say transcripts clear at session end. They do not (F9).
- `index.py` says a removed medicine can never be found. It can (F1).
- ADR-0041 still says "31 eval questions". The file now has 33.
- CLAUDE.md section 9 lists a summary and pending question in short-term memory. They are not built.

## Checked and fine

- **Safety gate and messages:** `TIER1_MESSAGE` is a fixed constant used by the gate and the emergency node. The gate runs first in the graph. Tier 1 recall by rules is 100% on the 33 cases (tested). Classifier errors and timeouts give Tier 2, per run.
- **Agent limits and tools:** There are 6 tool calls in total, counted across retries. A broken tool ends in a safe error. All five tools are read-only, and the agent gets four. The model cannot call a tool it was not given (tested).
- **Authentication and access:** Cookies are HttpOnly and SameSite=Lax. `check_origin` is app-wide.
- **Question input:** `AskIn` forbids extra fields, and `fill_prompt` fills in one pass.
- **Memory writes:** An emergency or a fallback is never remembered.

## What I'd do first

1. F1 and F3: they break stated rules, and the fixes are small.
2. F4, then F6: the first fixes a user-visible safety gap, the second protects cost and availability.
3. F2 and F5: they need a team decision about what the validators may trust.
4. The rest can wait. F8 is one line.
