# ADR-0045: Answers from confirmed uploaded papers only

- **Status:** Partly superseded by ADR-0046 (original evidence and edit handling)
- **Supersedes:** External-answer-source provisions of ADR-0002, ADR-0023 and ADR-0027

## Context

The application must explain only what the patient confirmed from their submitted papers.
An external label, general medical knowledge or an earlier generated answer cannot establish a
patient-specific fact. A citation must support the claim, rather than merely identify a real source.

## Decision

- Expose only `get_confirmed_medicines` and `search_patient_document` to the answer agent.
  The Ask endpoint supplies no outside data clients. Existing external-service modules remain
  available for historical tests but are not answer sources.
- Use answer prompt v11. Purpose, name, dose, timing, swallowing and visit claims must be
  directly supported by confirmed paper evidence. Missing purposes get
  "Your uploaded papers don't explain what this medicine is for." Other missing information
  gets "Your uploaded papers don't provide that information." A successful paper search is
  required before asserting absence; a failed lookup is not evidence of missing information.
- Each factual sentence must cite its own retrieved D passage. A structured support check
  reviews every enumerated claim against only those passages, preserving negation, identity
  and current versus historical instructions. Code verifies the completeness of the verdicts
  and exact supporting quote provenance. Errors and uncertain or unsupported claims fail
  closed, then use the existing retry and safe-fallback path.
- Resolve an unambiguous medicine reference from the immediately preceding user question.
  Do not use a generated answer or a stale focus to invent a reference. Ignore model rewrites
  that add facts, change doses or remove symptoms. The safety gate still reads the original input.
- Restrict follow-up buttons to generic paper questions, so generated buttons cannot add
  unsupported medical assumptions.
- Keep fixed emergency handling, confirmed-profile authority, per-patient isolation and the
  existing output checks.

## Consequences and verification

There is no external-label fallback for a missing paper fact. One small-model support review is
added for an otherwise valid factual answer; exact abstentions and simple clarification need
no review call. Support verification remains model-based: exact-quote checks prevent fabricated
quotes but are not an independent proof of semantic entailment.

Offline tests cover unsupported purposes with real citation IDs, fabricated and borrowed quotes,
missing verdicts, reviewer errors, external tool restrictions, no-cost abstention, bottle claims,
reference resolution and ambiguity. The full live baseline/new-prompt comparison with three
repeats per case is pending under the user's $2 maximum. Offline results do not establish live
answer or reviewer accuracy. No real patient data may be used.

## Safety review

| Check | Result | Evidence |
|---|---|---|
| 1 | PASS offline | All emergency eval cases retain the fixed 911 response. |
| 2 | PASS | Emergency text and keyword gate are unchanged. |
| 3 | PASS | Existing classifier error and timeout tests retain Tier 2. |
| 4 | PASS | The original question reaches the gate before reference resolution; graph tests pass. |
| 5 | PASS | The agent has only two read-only paper tools; external tools are blocked even with a broader caller registry. |
| 6 | PASS offline | Existing call-cap/fallback tests pass; no support-review call starts after the time budget is spent. Time limits remain checked between calls. |
| 7 | PASS offline | Existing removals, corrections, legacy-index and patient-isolation tests pass. |
| 8 | PASS offline | Schedule/calendar tests retain deterministic behavior and STOPPED/AS_NEEDED exclusions. |
| 9 | PASS offline | Existing validators and new claim-verdict/quote-provenance failure tests pass. |
| 10 | N/A for live behavior | Rule and scripted cases pass. Live before/after action accuracy remains pending. |
