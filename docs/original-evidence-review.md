# Original evidence and edit-history review

2026-11-21. Implements [ADR-0046](decisions/0046-original-excerpts-and-edit-history.md).

## Behavior checked

- A deliberately incorrect SUPPORTED reviewer verdict for "Furosemide helps you sleep" cannot
  release that interpretation. A purpose question abstains; a dose question releases only the
  original quoted passage. The model's claim is never the displayed clinical answer.
- A D ID or DOCUMENT label without original provenance is rejected. Wrong-page text, synthesized
  dose passages and a cropped "take two tablets" substring of "Do not take two tablets" fail the
  original-source gate. Whole excerpts preserve the supplied source wording.
- A change from extracted 25 mg to user-entered 37 mg retains both values and the original page.
  The 37 mg value is labelled as user-entered, withheld from instructions and shown with:
  "Please check your documents or call your healthcare provider."
- A legitimate correction from an erroneous extraction of 250 mg to the paper's 25 mg retains
  the same separation. The erroneous 250 mg extraction is not labelled as original PDF text.
- Comparisons appear in Review, Summary, Schedule and Ask. A disputed item does not enter the
  clinical schedule; Ask and calendar download stop for review. Missing legacy history is
  disclosed rather than reconstructed. The fixed emergency response still takes precedence.
- Invalid multi-item edits save no partial changes or history. Adding the history table preserves
  existing patient rows. Other patients cannot access comparison data through any affected API.
  QALog contains IDs/counts/checks, never original text or edited clinical values.

## Offline verification

The complete suite passed: **1,159 tests**, with five existing SWIG deprecation warnings.
Ruff lint and format checks passed. Tests used an isolated checkout snapshot, a blank API key,
scripted models and temporary databases; no live model or paid API call was made. Spending: $0.

The new cropped-negation regression failed against substring-only verification, then passed
with the complete-chunk/paragraph check. This is a functional regression check, not a claim of
measured real-model semantic accuracy. Earlier policy tests that treated edits as paper truth
were updated to assert explicit disclosure and withholding. Other safety checks remain intact.

## Safety checklist

These verdicts describe the offline evidence. They do not represent a paid live prompt benchmark.

| # | Check | Verdict | Evidence |
|---|---|---|---|
| 1 | Tier 1 recall | PASS | All Tier 1 eval questions receive the fixed response in `tests/safety/test_eval_cases.py`; graph/API emergency tests pass, including an edited profile. |
| 2 | Exact emergency wording | PASS | `app/safety/messages.py` is unchanged. The emergency edge precedes the new comparison edge. |
| 3 | Classifier failure/timeout | PASS | Existing failure, unreadable response and stuck-call tests still default to Tier 2. |
| 4 | Gate and output checks enforced | PASS | Gate remains first. Model drafts still pass existing validators and review; final code additionally restricts displayed facts to verified original excerpts. Conflict displays use fixed code and retained data, without an answering-model call. |
| 5 | Tools cannot write patient data | PASS | Answer-tool permissions are unchanged. History is written only by the existing authenticated owner confirmation endpoint. |
| 6 | Agent limits | PASS | Tool-count, timeout, model-error, retry and crash tests pass; settings and depth restrictions are unchanged. |
| 7 | Unconfirmed items excluded | PASS | Existing unconfirmed-item tests pass. Edited items are additionally excluded from clinical profile fields. |
| 8 | Deterministic schedules/calendar | PASS | Existing schedule/calendar tests pass. Disputed items are withheld; a profile with notices cannot export an .ics file. |
| 9 | Existing validator rejection cases | PASS | Citation, dose, name, diagnosis, advice and Tier 2 draft checks still pass their unit tests. Original-source rejection is an additional server-controlled release gate. |
| 10 | No rule-based over-escalation | PASS | All 33 rule-tier cases and everyday-question non-escalation tests pass; new release code preserves the gate tier. Full live action accuracy remains unmeasured. |

## Remaining limits and operation

- Restart the backend and UI after applying these files. Backend startup creates the additional
  history table; the running process is not restarted by this change.
- Old overwritten before-values cannot be recovered. Missing approval/edit history requires a
  fresh review using the original/corrected paperwork through the existing upload flow.
- The current conservative conflict policy pauses all Ask answers and calendar downloads when
  any edit/removal needs checking, including a legitimate extraction correction. Unchanged
  summary and schedule items remain visible. There is no clinical override or automatic
  approval of a changed value in this change.
- Original excerpts may be longer than generated drafts. Selection can miss relevant text,
  and limited purpose patterns can abstain on a purpose expressed differently. Full-document
  context and visual PDF extraction accuracy still need evaluation.
- Prompts and model settings are unchanged. Prompt v11's previously pending live benchmark has
  not been run or claimed complete. No commits, pushes or remote settings changes are needed
  to inspect and test this local implementation.
