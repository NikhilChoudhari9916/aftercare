# ADR-0005: Three-tier safety gate — rules plus a classifier run 3 times

- **Status:** Accepted
- **Date:** 2026-10 (recorded 2026-10-31)
- **Deciders:** team
- **Supersedes:** none

## Context

Some questions describe emergencies ("my chest feels a bit tight but I'm fine"). Missing one is the worst failure the app can have. Over-escalating everything causes alarm fatigue (prompt v5 sent a back-pain question to the care team).

## Decision

Three tiers, decided in fixed code before any agent runs:
- **Tier 1, possible emergency:** a fixed 911 message, word for word, with no LLM text.
- **Tier 2, care team soon:** the answer leads with the care team name and phone number.
- **Tier 3, general question:** a normal grounded answer.

The tier is the more severe of (a) keyword rules in `data/red_flags.yaml` plus the patient's own warning signs, and (b) a small, fast LLM classifier run **3 times**, taking the most severe result. When unsure, choose the more serious tier. If the classifier fails or times out, default to **Tier 2**, never Tier 3.

## Alternatives considered

- **Rules only** — misses unusual wording.
- **LLM only** — can be inconsistent and can fail.

## Consequences

- Tier 1 recall must be **100%** on the eval set; any change to safety code runs the `aftercare-safety-review` skill.
- Three classifier calls per question add cost and delay, so the classifier uses the fast model.
- The eval suite also tracks over-escalation.
