# ADR-0027: openFDA labels contribute purpose and warnings only, never dosage

- **Status:** Accepted
- **Date:** 2026-11-01
- **Deciders:** team
- **Supersedes:** none (narrows the label sections listed in `CLAUDE.md` section 15)

## Context

The Assignment 3 design deck excludes dosage sections of FDA labels "so the app can never suggest a dose". Our earlier chunking plan also listed dosage, drug interactions, and patient information sections. A label's dosing text is generic, and the patient's actual dose comes from their own confirmed paperwork. If dosage text is retrievable, an answer could quote a generic dose that differs from the patient's prescription.

HW2 also showed the gap this fills: "What is this pill for?" kept ending in "ask your pharmacist" because strict grounding had no source for a medicine's purpose.

## Decision

- Enrichment keeps only two sections of each FDA label: **indications and usage** (purpose) and **warnings** (including a boxed warning).
- **Dosage and administration is never chunked, stored, or indexed.** Drug interactions and patient-information sections are also left out for now; adding them needs a new ADR and eval cases.
- Doses, times, and how to take each medicine come only from the confirmed paperwork.
- The validators already require that doses in an answer match the confirmed profile; this decision removes the other path by which a dose could enter an answer.

## Alternatives considered

- **Keep all label sections** — richer answers, but a generic dose could contradict the prescription.
- **Keep dosage but add a validator rule** — one more rule to get wrong; not indexing it is simpler and safer.

## Consequences

- Some questions (for example "can I crush this?") are no longer answered from the label unless the paperwork says it; the answer points to the pharmacist.
- The synthetic label snippets in `data/synthetic/*_sources.txt` for patients 1 and 2 include a few administration notes (for example "swallow whole"). They are test fixtures and may be trimmed later; P3's snippets follow this rule.
