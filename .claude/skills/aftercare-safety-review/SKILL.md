---
name: aftercare-safety-review
description: Pass/fail safety checklist for AfterCare. Use before finishing any change to app/safety/, app/agents/, app/qa/validators.py, app/extraction/, app/summary/schedule.py, data/red_flags.yaml, or anything in prompts/.
---

# AfterCare safety review

Run this before you call a safety-relevant change done. Check each item against the actual diff and test output, not from memory. Report every item as PASS, FAIL, or N/A with one line of evidence, and paste the table into the pull request.

| # | Check | How to verify |
|---|-------|---------------|
| 1 | Tier 1 recall is still 100%: every "Call 911" eval case returns the fixed 911 text | Run the safety gate tests and the Tier 1 eval cases |
| 2 | The Tier 1 message is unchanged, word for word, and comes from `app/safety/messages.py`, not from an LLM | Diff `messages.py`; check the gate returns it without calling the orchestrator |
| 3 | Classifier error or timeout still defaults to Tier 2, never Tier 3 | Unit test with the classifier mocked to raise and to time out |
| 4 | The gate and validators still run on every question, and no agent can call, skip, or change them | Read `app/agents/runner.py`; agents' tool lists do not include gate or validator functions |
| 5 | No agent tool can write patient data | Check every tool in `app/tools/` is read-only |
| 6 | Agent guardrails intact: at most 6 tool calls, depth 1, 30-second timeout, safe fallback on any limit | Values come from `app/config.py`; tests cover each limit |
| 7 | Unconfirmed profile items are never used in answers, schedules, or calendar files | Test with an unconfirmed medicine present |
| 8 | Schedules, doses, and dates are computed by code, not the LLM; STOPPED and AS NEEDED medicines get no calendar events | `app/summary/schedule.py` and `calendar_export.py` tests |
| 9 | Validators still reject: uncited facts, doses or names not in the profile, dose-change advice, diagnosis, Tier 2 answers missing the care team line | Validator unit tests, plus `global_must_not_match` from `tests/eval/eval_cases.json` |
| 10 | No over-escalation regression: "Just answer" cases are not turned into "Call care team" | Compare eval action accuracy before and after |

Any FAIL blocks the change. Fix it, or stop and tell the user exactly what failed and why. Never edit a test or an eval case to turn a FAIL into a PASS.
