# ADR-0046: Original excerpts and explicit confirmation edit history

- **Status:** Accepted by explicit user instruction, 2026-11-21
- **Supersedes:** Answer release in ADR-0045, synthesized answer evidence in ADR-0043,
  and treating edited fields as paper facts in ADR-0040

## Context

A model support reviewer can mistakenly approve an inference: an evening instruction does not
establish a sleep-related purpose. Checking that a quotation exists does not prove a paraphrase.
Also, confirmation previously overwrote extracted values without retaining the before/after
record. A user-entered dose could then become a generated passage labelled as original paperwork.
The original document must remain the authority. Edits must be disclosed, never silently merged.

## Decision

- The answering model may select retrieved D IDs, but its clinical wording is never released.
  Code displays complete original excerpts instead, preserving negations and qualifications.
  Existing draft validators and model support review remain additional rejection checks; an
  affirmative model verdict cannot authorize a generated medical interpretation.
- Active indexes contain original page passages only. At every retrieval, code also compares
  each passage with the current original DocumentPage for this patient, document version and
  page. A passage must match a complete canonical chunk or original paragraph, not an arbitrary
  cropped substring that might omit a negation. A DOCUMENT label or a D ID alone is insufficient.
  Historical synthesized passages,
  wrong-page text, edited profile values and other patients' text cannot become answer evidence.
- A purpose question requires an explicit purpose statement tied to the requested medicine.
  The selector deliberately recognizes limited literal constructions. If none can be verified,
  return "I couldn't verify a medicine purpose in the retrieved original text." This describes
  verification failure, rather than claiming a search proves the entire document lacks a fact.
  Other unverified answers use the corresponding fixed verification-failure response.
- Add a separate ProfileChange table, retaining before/after JSON for edits and removals.
  Original DocumentPage records and PDF files remain untouched. Confirmation validates the
  entire request before saving changes. Startup creates this additional table without resetting
  an existing database; existing rows are preserved.
- Show the item identity, **originally extracted** value, **user-edited** value, the original
  page text, and "Please check your documents or call your healthcare provider." An extracted
  value is labelled as an extraction, because it too can be wrong (250 mg extracted from a
  document that actually says 25 mg). User confirmation is not proof of original provenance.
- Show comparisons in Review, Summary, Schedule and Ask. Changed items are excluded from the
  clinical profile used by summaries, schedules and tools. Ask returns the comparison before
  routing or answering, and does not remember it as a conversation fact. Calendar export is
  blocked while a discrepancy remains, and the UI hides its download and reminder-planning
  controls. Unchanged summary/schedule items remain visible.
- For legacy profiles with missing approval metadata or no recoverable edit history, display
  that limitation and withhold clinical profile items. Never reconstruct an original value from
  a saved edit. There is no automatic clinical override: check the original and use the existing
  upload/review flow with corrected paperwork when necessary.
- Emergency handling still runs first and returns the identical fixed 911 response. Tier 2
  excerpt/conflict replies retain a fixed care-team instruction; an unverified extracted phone
  number is not added to an excerpt reply. External information and memory are not evidence.
- Change history is patient data in the same protected database as the profile, subject to the
  existing owner/aide read permissions. It is never copied into QALog or console logs. No new
  public history endpoint, dependency, prompt version or model setting is introduced.

## Consequences

Answers are original excerpts rather than a free-form plain-language medical paraphrase. They
can be longer than the prior draft's word/readability targets. Draft checks still run; original
quoted wording is preserved instead of being rewritten to meet those targets. Retrieval may
select an irrelevant passage or miss a relevant one; limited purpose matching may abstain even
when the document explains a purpose in different words. These are retrieval/usability limits,
not permission to release a model's interpretation. PDF text extraction itself still needs
validation against the visual original; this change does not establish clinical correctness.

A single edit/removal currently blocks the whole Ask answer path and calendar download; it does
not selectively answer unrelated questions. Old before/after history cannot be backfilled.
Existing prompt v11's full live benchmark remains pending. No live calls or API credits are
needed for these code and regression tests. See the offline review in
[original-evidence-review.md](../original-evidence-review.md).
