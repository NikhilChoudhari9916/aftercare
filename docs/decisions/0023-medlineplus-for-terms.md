# ADR-0023: MedlinePlus as the cited source for plain-language term definitions

- **Status:** Accepted
- **Date:** 2026-10-31
- **Deciders:** team
- **Supersedes:** none

## Context

Patients want terms in their papers explained: if the papers say "MI", the app should say that in plain language it means a heart attack. But the answer prompt forbids using general knowledge (v7 rule 1), so every definition needs a source we can cite.

## Decision

- Use **MedlinePlus** (US National Library of Medicine, free, via MedlinePlus Connect or its health-topic data) as the source for plain-language definitions of medical terms.
- The app explains only terms that **appear in the patient's own papers**. It never says whether the patient has a condition, and it never explains a symptom the papers don't mention. Symptom questions still go through the safety gate first (ADR-0005).
- Definitions are fetched during enrichment for terms found in the confirmed profile, stored as `Chunk`s of source type `TERM` (`CLAUDE.md` section 15), and cited as a new source type, "From MedlinePlus".
- Because the prompt only knows `[D#]` and `[L#]` source IDs today, adding `[T#]` requires a **new prompt version (v8)** through the `aftercare-prompt-change` skill: eval before and after, plus new eval cases for term questions, logged in `prompts/PROMPT_LOG.md`.
- The summary agent handles term questions.

## Alternatives considered

- **Let the model explain from general knowledge** — fluent but uncited, and against the grounding rule.
- **A hand-written glossary** — fully controlled, but small and costly to maintain.
- **UMLS or SNOMED** — richer, but license and setup overhead for a course project.

## Consequences

- Term explanations are cited and checkable.
- Coverage is limited to what MedlinePlus has; for anything else the answer says the sources don't cover it and points to the care team or pharmacist.
- One more external API to call, cache, and test with mocks.
