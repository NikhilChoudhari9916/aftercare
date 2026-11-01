# ADR-0030: Use cases, pipeline steps, and input scope from the Assignment 3 deck

- **Status:** Accepted
- **Date:** 2026-11-01
- **Deciders:** team
- **Supersedes:** none (clarifies ADR-0007 and ADR-0025)

## Context

The team agreed to build the decisions in the Assignment 3 deck, with one exception: **the input is the digital PDF only for now.** Other decisions were already made (ADR-0007, ADR-0021, ADR-0025) and are kept or clarified here.

## Decision

**Input.** A digital PDF for the discharge paperwork, and typed text for questions. **Photo upload and OCR, and voice or speech input, stay out** (reaffirms ADR-0007). The read-aloud button for answers stays.

**Five use cases are in scope:**
1. Summary
2. Medicine schedule (built by code, ADR-0006)
3. Medicine question
4. **Diet question:** answered from the paperwork's diet lines and the confirmed medicine list. No food-and-medicine interaction claims beyond what the sources say.
5. **Visit prep:** four parts: what the paperwork says about the visit; a short timeline from the symptom log; which medicines the log shows were taken or missed; and questions to ask the doctor, including anything the paperwork does not cover. It needs long-term memory (ADR-0029).

The **urgent-symptom path uses neither retrieval nor memory** (ADR-0005).

**Question pipeline:** input → safety gate (code) → load memory → orchestrator (picks the task and rewrites the question, so "it" becomes "lisinopril", using session focus and RxNorm) → specialist agents retrieve per patient (ADR-0028) → validators (code) → answer → save only user-confirmed facts to memory.

**Paperwork always wins.** References (FDA label, MedlinePlus, the glossary) may explain a term but never override or add to the paperwork. If memory or a reference disagrees with the paperwork, the paperwork wins and the conflict is shown, not merged.

**Two kinds of citation in the UI:** "From your papers (section)" for the patient's own paperwork, and "General information" for drug labels and MedlinePlus.

**Abbreviation glossary.** A small team-curated file, `data/abbreviations.yaml` (b.i.d., t.i.d., p.r.n., p.o., mEq, grains), is always in context so terms can be explained. Code still normalizes abbreviations in the upload pipeline.

**Kept from earlier decisions**
- **Caregivers:** the deck's "caregiver only if invited" is built as invited aides with a limited role (ADR-0032), which replaces the shared login of ADR-0021.
- **ADR-0025:** the diet agent with food–medicine interaction checks and the physiotherapy agent remain later, each with its own ADR first. Answering a diet question from the paperwork is a question type, not that agent.

## Consequences

- `CLAUDE.md` sections 1, 2, 4, 9, 10, 11, and 12 change in the same pull request.
- Diet and visit-prep questions need eval cases, and the term tag still needs prompt v8 (ADR-0023).
- Photo and voice are not designed or promised anywhere in the MVP.
