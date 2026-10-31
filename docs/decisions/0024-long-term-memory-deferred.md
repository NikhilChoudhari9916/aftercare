# ADR-0024: Long-term memory is deferred; the rules are set now

- **Status:** Accepted
- **Date:** 2026-10-31
- **Deciders:** team
- **Supersedes:** none

## Context

The team wants the app to remember across sessions eventually. Memory about a patient is health data, and a wrong or invented "memory" could mislead an answer.

## Decision

- **MVP:** the app uses the confirmed profile (versioned), preferences, and the **current session's chat only**.
- **Phase 2 (after the MVP is evaluated):** short, patient-approved notes from past conversations (for example, preferred reading level, open questions).
- Rules for Phase 2, fixed now:
  1. Memory is separate from the profile and **never overrides** confirmed medicines or schedule; the profile wins any disagreement.
  2. **Code writes memory, agents don't** (ADR-0004). Agents may read it.
  3. The patient can view, delete, or switch off memory.
  4. Memory is health data: it carries `patient_id`, follows the 30-day retention and deletion rule, and is never written to console logs.
  5. It stores what the patient said or approved, never the model's guesses about their health.

## Consequences

- The MVP stays small, and Phase 2 needs one new table and an ADR for the details.
- Keep `Preference` and `QALog` (with patient ID) in the MVP, which is already planned.
