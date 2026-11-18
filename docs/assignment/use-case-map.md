# Use cases: code path, tools and tests

Checked against `main`. "Slice demo" means one of the three use cases ADR-0036 chose for the
assignment demo: **upload to summary, a cited question, the schedule**. Where something is not built,
or built only in part, this page says so.

| # | Use case | Slice demo | State |
|---|---|---|---|
| 1 | Plain-language summary | **Yes** (as part of "upload to summary") | Built |
| 2 | Medication schedule (and calendar file) | **Yes** | Built |
| 3 | Medicine questions | **Yes** ("a cited question") | Built, with the limits in `challenges-and-limits.md` |
| 4 | Diet questions | No | **Partly built**: no code of its own, see below |
| 5 | Visit prep | No | **Not built** |

## 1. Plain-language summary

- **Code path:**
  - Upload: `POST /documents` (`app/documents/routes.py:114`) starts a job (`app/jobs/`) that runs the upload graph (`app/agents/upload_graph.py`: ingest, extract, check_quotes, normalize).
  - The patient confirms through `PUT /patients/{id}/profile` (`app/documents/routes.py:186`) and the Confirm page (`ui/pages/confirm.py`).
  - The summary is `build_summary` (`app/summary/summary.py:76`), served by `GET /patients/{id}/summary` (`app/summary/routes.py:29`) and shown by `ui/pages/summary.py`. It is plain code over the confirmed profile, with no agent and no model call.
- **Tools used:** none in the summary. The upload step makes one model call for extraction (`app/extraction/extractor.py`).
- **Tests:**
  - `tests/summary/test_summary.py`: `test_patient_one_summary_follows_the_papers_section_by_section`, `test_every_line_points_back_to_a_page_of_the_papers`, `test_it_reads_at_about_a_sixth_grade_level`, `test_it_never_diagnoses_or_gives_dose_advice`
  - `tests/summary/test_routes.py`: `test_nothing_is_built_from_papers_that_are_not_confirmed_yet`, `test_removed_items_never_reach_the_summary_schedule_or_calendar`
  - `tests/agents/test_upload_graph.py`: `test_a_good_pdf_becomes_a_verified_profile_in_one_model_call`, `test_an_invented_quote_sends_the_model_back_once_with_feedback`
  - `tests/documents/test_upload_api.py`: `test_confirming_applies_edits_removals_and_confirms_everything_kept`
- **Not covered:** MedlinePlus term explanations. There is no `medlineplus.py` in `app/enrichment/` (it has `cache.py`, `openfda.py`, `rxnorm.py`), so terms are not explained from a cited source (ADR-0023).

## 2. Medication schedule

- **Code path:** `build_schedule` (`app/summary/schedule.py:304`), the patient's own reminder times (`app/summary/plan.py`, `PUT /patients/{id}/plan`, `app/summary/routes.py:40`), and the calendar file (`app/summary/calendar_export.py`, `GET /patients/{id}/schedule.ics`, `routes.py:52`). UI: `ui/pages/schedule.py`. All plain code.
- **Tools used:** none on this page. A question about the schedule asked on the Ask page gets a fixed pointer to the Schedule page (`SCHEDULE_REPLY`, `app/agents/question_graph.py:60`). A `get_schedule` tool exists in the registry (`app/tools/profile_tools.py:67`) but the agent is **not** given it (`question_graph.py:46-51`).
- **Tests:**
  - `tests/summary/test_schedule.py`: `test_unclear_frequencies_are_never_guessed`, `test_stopped_and_as_needed_medicines_are_never_on_the_daily_schedule`, `test_patient_one_schedule_matches_the_papers`
  - `tests/summary/test_calendar_export.py`: `test_titles_are_private_by_default_and_hold_no_medicine_names`, `test_stopped_and_as_needed_medicines_make_no_events`, `test_a_fixed_course_stops_on_its_end_date`
  - `tests/summary/test_plan_routes.py`: `test_the_owner_saves_a_plan_and_the_schedule_and_calendar_follow_it`, `test_an_aide_can_read_the_plan_but_not_change_it`
  - `tests/agents/test_question_graph.py`: `test_a_schedule_question_gets_a_fixed_reply_and_never_reaches_the_agent`
- **Not tested automatically:** the planning form in a browser (no Playwright; `docs/handoff.md`, "Reminder planning").

## 3. Medicine questions

- **Code path:** `POST /patients/{id}/ask` (`app/qa/routes.py:146`) runs the endpoint checks, then the question graph (`app/agents/question_graph.py`): safety gate, router, the medication agent with tools, validators, finalize. The Ask page is `ui/pages/ask.py`; citation tags are made in `ui/content.py` (tests in `tests/ui/test_ask_content.py`).
- **Tools used (the agent is given these four):** `get_confirmed_medicines`, `search_patient_document`, `search_fda_label`, `lookup_rxnorm` (`question_graph.py:46-51`; registry `app/tools/__init__.py:8-18`).
- **Tests:**
  - `tests/agents/test_question_graph.py`: `test_the_agent_uses_a_tool_then_answers_with_a_citation`, `test_more_tool_calls_than_allowed_end_in_the_fallback`, `test_a_failed_answer_is_retried_once_with_the_reasons`, `test_two_failed_answers_end_in_the_safe_fallback`, `test_an_emergency_gets_the_fixed_words_and_nothing_else_runs`
  - `tests/qa/test_ask_api.py`: `test_a_cited_answer_comes_back_with_its_source_and_a_log_row_without_text`, `test_a_second_question_can_say_it_and_the_first_one_is_remembered`, `test_a_question_never_finds_another_patients_papers`
  - `tests/qa/test_validators.py` (the checks), `tests/safety/test_gate.py` and `tests/safety/test_classifier.py` (the gate)
  - `tests/qa/test_full_path.py` and `tests/qa/test_run_eval.py` (the eval runners, with a fake model)
- **Real-model evidence:** only the hand-run questions and the eval runs described, with their caveats, in `challenges-and-limits.md`. No clean eval result is reported.

## 4. Diet questions: partly built

What exists:
- Diet lines are extracted into the profile (`diet_limits`, `app/extraction/schema.py:51,61`).
- They appear in the summary as "Food and drink" (`app/summary/summary.py:125-133`).
- They are written into the prompt text (`app/qa/profile_text.py:64-65`).
- The validators treat them as known text (`app/qa/validators.py:161`).

What does not exist: I searched `app/` for `diet` and found only those places. There is **no diet route, tool, agent or router branch**. A diet question goes through the same medication-agent path as use case 3, so it can be answered only as far as the agent chooses to use those lines. There is **no test** for a diet question: `grep` for "diet" in `tests/qa` found nothing, and no eval case asks about the diet lines (the only food-related case, `T9`, asks about alcohol with medicines, which is a medicine question). The summary's diet section is covered only as one name in a list of sections (`tests/summary/test_summary.py:24`). The food and medicine interaction agent is deferred by decision (ADR-0025).

## 5. Visit prep: not built

I searched `app/` and `ui/` for `visit-prep`, `visit_prep`, symptom, dose log and saved question, and found no route, table, page or test. The `GET /patients/{id}/visit-prep` endpoint in CLAUDE.md section 11 does not exist. Two related things are built and are **not** visit prep:
- Follow-up visits and the "call to book" reminder in the schedule and calendar (`app/summary/plan.py`, `VisitPlan`).
- A follow-up appears in the summary.

The symptom log, dose log, saved questions and the long-term memory lifecycle (ADR-0029, ADR-0030) are not built.
