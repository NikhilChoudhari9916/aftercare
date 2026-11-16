# Security and safety review of `POST /patients/{id}/ask`

**Scope and method.** I read everything on your list and ran the relevant tests: 203 passed, and `ruff` is clean. I made no edits and called no model. Some findings come from reading the code and were not run end to end; I mark where I did run something.

**Last checked against commit `4482838`.** Since the report was first written, the code fixes for F3, F4, F8, F9 (logout only) and F11 have landed, and F10 is partly fixed. F1, F2, F5, F6 and F7 are still open. Every line number below was re-read from the current code. Each status names the test or lines it rests on.

## Executive summary

The structure is sound:
- The gate is the graph's first node, and no edge skips the validators.
- The agent has four read-only tools, and the patient ID is fixed by the server.
- No patient text reaches the logs or `QALog`.
- The UI escapes model text before building HTML.

I found **1 high, 5 medium, 5 low and 3 info** items. The high one is a rule from CLAUDE.md that the code does not enforce.

| ID | Sev | Status | Title |
|---|---|---|---|
| F1 | **High** | Still open | Removed or edited paperwork stays searchable and citable |
| F2 | Medium | Still open | An injected document line is flagged but still indexed, and the validators pass it |
| F3 | Medium | Fixed in this PR (one part open) | Some paths reach a patient with no gate: unconfirmed papers, over 500 characters, pre-graph errors |
| F4 | Medium | Fixed in this PR | Tier 2 failures end in the pharmacist fallback, not the care-team line |
| F5 | Medium | Still open | Follow-up buttons bypass the validators |
| F6 | Medium | Still open | No rate limit; thread, cost and timeout exposure |
| F7 | Low | Still open | `lookup_rxnorm` can send arbitrary text to an outside service |
| F8 | Low | Fixed in this PR | Tag defanging is incomplete (`<rules>`, `<inputs>` and others) |
| F9 | Low | Fixed in this PR for logout only | Session memory is never cleared at logout or revoke |
| F10 | Low | Partly fixed | The rewritten question is not re-gated, and a Tier 3 symptom can route to a fixed reply |
| F11 | Low | Fixed in this PR | A patient can spoof the app note |
| F12–14 | Info | No change | See below |

## Findings

**F1, High. Removed or edited paperwork is still retrievable.**
- **Status:** Still open. `build_chunks` (`app/qa/chunker.py:65-66`) still returns `chunk_pages(pages)` (raw page text, line 27) plus `medicine_chunks(profile)` (line 42), and nothing filters the page chunks against the profile. No test covers it.
- **Where:** `app/qa/index.py:27`, `app/qa/chunker.py:27,42,65-66`.
- **What:** `build_chunks` chunks the raw page text. Only the medicine-row chunks respect the confirmed profile.
- **Demonstrated:** I ran the chunker on a page containing "Start warfarin 5 mg…" with warfarin removed from the profile. The page chunk still held the warfarin line. The `index.py` docstring claims a removed medicine "can never be found again", which is false for page chunks.
- **Impact:**
  - It breaks "nothing unconfirmed is ever used in answers" (CLAUDE.md section 2, and safety-review item 7).
  - If extraction hallucinated a medicine, or the patient corrected a dose, the original text can still be retrieved and cited.
  - The validators count cited chunk text as known (`validators.py:102,152`), so such an answer passes.
- **Fix:** Build page chunks only from text that supports confirmed items. Alternatively, drop any chunk that contains a medicine name or quote the patient removed, and add a test for it.
- **User-visible:** Yes. Some answers become "not in your papers".

**F2, Medium. Indirect injection from an uploaded document.**
- **Status:** Still open. `upload_graph.py:53` still only records `injection_flags`, `ui/pages/confirm.py:153` only shows a warning, and `index.py:27` indexes every page chunk. `_check_advice` (`validators.py:404`) and `_check_uncited` (`validators.py:218`) are unchanged. No test covers it.
- **Where:** `app/agents/upload_graph.py:53`, `ui/pages/confirm.py:153`, `app/qa/index.py:27`, `app/qa/validators.py:218,404`.
- **What:** The upload scan only produces a warning on the confirm page. Flagged lines are still indexed. Retrieved text goes to the model in a `tool_result` (not the system prompt), which is the right place for it.
- **Impact:**
  - A sentence like "Your papers say you should stop all medicines" passes the validators, because `_check_advice` deliberately skips attributed text.
  - A cited, attributed fake phone number passes too. `_check_uncited` accepts any sentence that carries a `[D#]` tag.
  - I reasoned this from the regexes and did not run it end to end.
- **Fix:** Exclude flagged lines from chunks, or label them so the agent says "this line looks like an instruction". Consider also rejecting an attributed stop, skip or double instruction unless it matches a confirmed STOPPED medicine.
- **User-visible:** Rarely.

**F3, Medium. Paths with no gate.**
- **Status:** Fixed in this PR, with one part still open.
  - **Fixed:** `ask` (`app/qa/routes.py:165-175`) runs `apply_rules` on the full text, with an empty `PatientSafetyContext` when there is no profile, and returns the fixed 911 text before the 404 (line 176), the empty check (179) and the length check (181). The not-confirmed page now says "If this might be an emergency, call 911 now." (`ui/layout.py:63`).
  - **Proven by:** `test_an_emergency_gets_the_911_words_even_when_the_papers_are_not_confirmed`, `test_a_long_emergency_gets_the_911_words_not_a_length_refusal`, `test_a_long_emergency_before_confirming_also_gets_the_911_words` and `test_an_ordinary_question_before_confirming_is_still_refused_with_404` (all `tests/qa/test_ask_api.py`).
  - **Still open:** an error while loading the profile or the prompts after the emergency check is still a 500 with no 911 text. Nothing tests it.
- **Where (original):** `app/qa/routes.py`, the start of `ask`.
- **What:** Before the graph runs, the route returns 404 if the papers are not confirmed, and 422 if the question is over 500 characters. Errors in prompt or profile loading there become a 500. In all three cases the gate has not run.
- **Impact:** Someone describing chest pain at length, or asking before confirming, gets no 911 text. The not-confirmed page (`ui/layout.py:58`) has no 911 banner either.
- **Fix:** Run the keyword rules on the full text first, with an empty context if there is no profile. Return the fixed text on Tier 1 before any other check.
- **User-visible:** Yes, only in those cases.

**F4, Medium. Tier 2 fallback.**
- **Status:** Fixed in this PR. `_fallback_reply` (`question_graph.py:164-172`) puts `care_team_line(...)` first for Tier 2, and both fallback paths use it (line 391 with the gate's tier, line 520 with `Tier.CARE_TEAM` after a crash). Proven by `test_a_tier_2_fallback_starts_with_the_care_team_line` (5 failure paths), `test_a_crash_is_treated_as_tier_2_because_the_gate_result_is_lost` and `test_a_tier_2_fallback_with_no_care_team_in_the_papers_uses_the_plain_line` (`tests/agents/test_question_graph.py`). The first two paragraphs below describe the code before the fix.
- **Where:** `app/agents/question_graph.py:164-172,391,520`, `app/qa/validators.py:121`.
- **What:** `care_team_line` is never called anywhere in `app/`. Tier 2 relies on the model writing the lead, and the validators checking it. If it fails twice, or the graph errors (where `tier` is forced to `CARE_TEAM`), the patient gets "call your pharmacist". ADR-0041 says the workflow uses `care_team_line`, and CLAUDE.md section 4 says the merged reply must lead with it.
- **Fix:** For Tier 2, make the fallback start with `care_team_line(...)` before the generic text.
- **User-visible:** Yes.

**F5, Medium. Follow-ups are unvalidated.**
- **Status:** Still open. `question_graph.py:404` still returns `parsed.followups[:3]` with no length cap or checks, and `parse_answer` (`answer_text.py:17`) still cuts them out before validation. No test covers it.
- **Where:** `app/agents/question_graph.py:397-404`, `app/qa/answer_text.py:17`.
- **What:** The follow-up lines are cut out before validation and shown as buttons, up to 3, with no length cap. A manipulated reply can put advice or a phone number in a button. Clicking one goes through the gate as a normal question.
- **Fix:** Cap their length. Run the diagnosis, advice, unknown-medicine and phone checks on them too, and drop any that fail.
- **User-visible:** Rarely.

**F6, Medium. Abuse, cost and reliability.**
- **Status:** Still open. `ask` (`app/qa/routes.py:146`) has no rate or concurrency limit. `llm.py:80-81` still uses `max_retries=2`, `config.py:43` still sets a 60 s timeout, `question_graph.py:294` still checks the 30 s limit only before each agent call, and `classifier.py:78` still calls `shutdown(wait=False, ...)`. No test covers it.
- **Where:** `app/qa/routes.py:146`, `app/safety/classifier.py:75-78`, `app/llm.py:80-81`, `app/config.py:43,48,50`, `app/agents/question_graph.py:294,308`.
- **What:**
  - There is no per-user rate or concurrency limit. One question is up to about 4 fast-model calls plus up to about 8 Sonnet calls, each with 3000 output tokens.
  - The 30-second limit is checked only before each agent call. A single call can run 60 seconds with 2 SDK retries, so about 180 seconds.
  - Each request holds a worker thread. Roughly 40 concurrent slow requests can starve the rest of the API.
  - On a classifier timeout, `shutdown(wait=False)` leaves the model calls running.
  - The UI `busy` flag is client-side only.
- **Fix:** Add a per-user and per-patient limit, plus a concurrency cap. Set a hard per-question deadline, and a shorter client timeout with fewer retries on this path.
- **User-visible:** Only for abusers.

**F7, Low. `lookup_rxnorm` is unrestricted.**
- **Status:** Still open. `NameInput` (`label_tools.py:54`) and `_lookup_rxnorm` (line 60) still send any name of up to 80 characters to `context.rxnorm.lookup` (`app/enrichment/rxnorm.py:24`).
- **Where:** `app/tools/label_tools.py:54-77`, `app/enrichment/rxnorm.py:24`.
- **What:** The model chooses `name` (up to 80 characters), which is sent to the NLM service. `search_fda_label` is limited to confirmed medicines; this tool is not. An injected instruction could use up to 6 calls to leak a few hundred characters.
- **Fix:** Allow only confirmed names, or names that appear in the question.

**F8, Low. Defanging gap.**
- **Status:** Fixed in this PR. `_defang` (`question_graph.py:145-152`) swaps every `<` and `>` for a fullwidth look-alike, and is applied to the router's medicines, recent conversation and question (lines 187-197), to the first agent message (205), and to the profile text and the question in the system prompt (298, 300). Proven by `test_no_angle_bracket_from_the_patient_reaches_the_prompt_or_the_router` and `test_the_profile_text_cannot_close_a_tag_and_keeps_its_meaning` (`tests/agents/test_question_graph.py`). The text below describes the old 7-tag list.
- **Where:** `app/agents/question_graph.py:145-152`.
- **What:** The list covers 7 tags. The v7 prompt also uses `inputs`, `rules`, `role`, `workflow`, `examples`, `output_format` and `context`. A question containing `</question></inputs><rules>…` keeps the `inputs` and `rules` parts inside the system prompt. The gate and validators still apply, so this affects behavior, not safety. The profile text in `{patient_profile}` is not defanged either.
- **Fix:** Neutralize every angle bracket, the way the classifier already does (`classifier.py:53`).

**F9, Low. Memory lifecycle.**
- **Status:** Fixed in this PR for logout only. `logout` (`app/auth/routes.py:166`) calls `forget(hash_token(token))` before `end_session`. Proven by `test_logout_forgets_that_sessions_conversation_and_no_one_elses` (`tests/auth/test_routes.py`). The revoke and patient-delete part is not fixed, because no revoke route or patient-delete route exists yet (the only caller of `forget` in `app/` is logout). Hook it in when those routes are built, and add a test then. Idle entries still expire only after 12 hours (`session.py:19`).
- **Where:** `app/memory/session.py:92-96`, `app/auth/routes.py:166`.
- **What:** `forget()` has no callers. ADR-0031 says transcripts clear when the session ends. In practice they stay in RAM for up to 12 hours idle, even after logout or an aide revoke. They are reachable only through the same hashed session key, and the idle sweep runs only when another call arrives.
- **Fix:** Call `forget` at logout, and drop a patient's entries on revoke or delete.

**F10, Low.**
- **Status:** Partly fixed.
  - **Fixed:** when the gate says Tier 2, the router's route is overridden to MEDICINE (`question_graph.py:259-260`), so a symptom reaches the agent. A rewrite that is empty, over the length limit or more than 3× the original plus 80 characters is replaced by the patient's own words (263-265). Proven by `test_a_symptom_goes_to_the_agent_whatever_the_router_said` and `test_a_long_rewrite_is_ignored_and_the_patients_own_words_are_used`.
  - **Still open:** a Tier 3 message that the router calls SCHEDULE or OUT_OF_SCOPE still gets a fixed reply with no symptom check (`after_router` line 277, `schedule_reply` 282, `out_of_scope_reply` 285). The rewrite is not re-gated, and it is not compared with the original for a dropped symptom. No test covers either.
- **Where:** `app/agents/question_graph.py:244-290`.
- **What:** The gate sees the original question, but the agent sees the router's rewrite. The "never remove a symptom" rule is only in the prompt. A Tier 3 message the router calls SCHEDULE or OUT_OF_SCOPE gets a fixed reply with no symptom check. The OUT_OF_SCOPE reply does at least name the care team.
- **Fix:** Send any message with a symptom word to the agent, and compare the rewrite with the original.

**F11, Low.**
- **Status:** Fixed in this PR. `_first_message` (`question_graph.py:201-209`) defangs the question, so the only `<app_note>` is the real one. Proven by `test_a_typed_app_note_cannot_pass_for_the_real_one` (`tests/agents/test_question_graph.py`).
- **Where:** `app/agents/question_graph.py:201-209`.
- **What:** A patient can type their own "(App note… TIER 3)". It cannot lower the real tier, because the validators use the code's tier, and the model can only raise it.
- **Fix:** Defang it, as in F8.

**Info**
- **F12:** Injected text that makes the model emit the 911 sentence is accepted and shown as an emergency (`question_graph.py:358,400`). That is a safe-direction false alarm.
- **F13:** The route holds a DB session across model calls. The embedding model loads lazily in the request thread, so a first-request race is possible.
- **F14:** Index files are written through a temp file and `replace`, so writes are atomic.

## Question-by-question answers

**1. Access and isolation.**
- **Who may ask:** Owner and aide, through `require_access`. No access returns 404 and the wrong role returns 403, both logged as IDs only. Revoke and expiry are checked on every request.
- **What the leak test proves:** `tests/qa/test_ask_api.py:231` (`test_a_question_never_finds_another_patients_papers`) proves one thing. With the keyword retriever, `search_patient_document` returns none of patient B's chunks, and asking as B returns 404.
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
- **Exceptions to the "gate first" rule:** F3 lists the paths that run before the graph. The emergency keyword rules now run first in the route too (F3, fixed).

**3. Injection.**
- **What an injected sentence can do:** With its four tools it can only produce text. It can also call `lookup_rxnorm` (F7). The validators block uncited facts, unknown dose amounts and times, diagnosis and unattributed advice. They cannot block attributed or cited content (F2).

**4. Output handling.**
- **Result:** The escaping is correct. `answer_html` escapes first, then builds only `<b>`, a constant-styled span and `<br>`. Labels are server-built and escaped. Buttons, labels and alerts are text-only. `tests/ui/test_ask_content.py:27` (`test_nothing_the_model_wrote_can_become_html`) covers `<script>` and `onerror`. Keep that test if `sanitize=False` stays.

**5. Privacy.**
- **Result:** All four logger calls record only a type, a name, or a file and line. `QALog` has no text. Exceptions are caught and replaced with constant messages. The only on-disk patient-derived data is the embedding index (health data, which ADR-0031 says to delete with the patient).

**6. Abuse.** See F6. The 500-character limit holds on the server. Session memory is bounded at 500 conversations × 10 turns. `LOG_PATIENT_TEXT` is refused in production (`app/config.py:91-92`). The recursion limit of 60 is not reachable within the tool cap, and an overrun would end in the fallback.

**7. Docs and ADRs that disagree with the code:**
- ADR-0004 and the safety skill name `app/agents/runner.py`, which does not exist. The graph in `question_graph.py` does that job.
- ADR-0041 says `care_team_line` leads Tier 2 answers. It was unused; the fallback now uses it (F4, fixed). The validators still only check the model's own lead, not the fallback's.
- ADR-0031 and CLAUDE.md say transcripts clear at session end. They now do at logout; revoke and patient delete are not built yet (F9).
- `index.py` says a removed medicine can never be found. It still can (F1, open).
- ADR-0041 still says "31 eval questions" (`docs/decisions/0041-*.md`, line 33). The file has 33 cases.
- CLAUDE.md section 9 lists a summary and pending question in short-term memory. They are not built.

## Checked and fine

- **Safety gate and messages:** `TIER1_MESSAGE` is a fixed constant used by the gate and the emergency node. The gate runs first in the graph. Tier 1 recall by rules is 100% on the 33 cases (tested). Classifier errors and timeouts give Tier 2, per run.
- **Agent limits and tools:** There are 6 tool calls in total, counted across retries. A broken tool ends in a safe error. All five tools are read-only, and the agent gets four. The model cannot call a tool it was not given (tested).
- **Authentication and access:** Cookies are HttpOnly and SameSite=Lax. `check_origin` is app-wide.
- **Question input:** `AskIn` forbids extra fields, and `fill_prompt` fills in one pass.
- **Memory writes:** An emergency or a fallback is never remembered.

## What I'd do first

Fixed since this report was written: F3, F4, F8, F11, and F9 for logout. F10 is partly fixed.

1. F1: it still breaks a stated rule ("nothing unconfirmed is ever used in answers"), and the fix is small.
2. F6: it protects cost and availability.
3. F2 and F5: they need a team decision about what the validators may trust.
4. The open parts of earlier fixes: the F3 500 after the emergency check, F9 on revoke and patient delete (when those routes exist), and F10 (Tier 3 messages routed to a fixed reply).
5. F7 can wait; it is one allow-list.
