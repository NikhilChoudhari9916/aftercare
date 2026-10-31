# ADR-0014: Prompts are versioned files, gated by the eval suite

- **Status:** Accepted
- **Date:** 2026-10 (recorded 2026-10-31)
- **Deciders:** team
- **Supersedes:** none

## Context

The answer prompt went through seven versions (v1–v7) during design. Small wording changes caused real regressions (v5 over-escalated a back-pain question). Prompt changes need the same discipline as code.

## Decision

- Prompts live as files in `prompts/`, never as strings in Python. **v7** is the baseline answer prompt (the medication agent's prompt).
- A change creates a new version file; old versions are kept. One idea per version.
- Every prompt or model change re-runs `tests/eval/` (29 cases, 2 synthetic patients, 3 runs each) before and after, and is logged in `prompts/PROMPT_LOG.md`. Procedure: the `aftercare-prompt-change` skill.
- Hard targets: 100% of Tier 1 cases get the 911 message; no unsupported claims; no dose advice; no new over-escalation.

## Consequences

- Every prompt change has evidence behind it, which also feeds the course reports.
- Eval runs cost API calls, so they run by hand, not in CI.
