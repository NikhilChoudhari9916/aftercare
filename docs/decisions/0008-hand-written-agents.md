# ADR-0008: Hand-written agents on the Anthropic SDK, with hard limits

- **Status:** Accepted
- **Date:** 2026-10 (recorded 2026-10-31)
- **Deciders:** team
- **Supersedes:** none

## Context

Questions can have several parts ("Can I take Advil, and when do I take metoprolol?"). We need an orchestrator and specialist agents, and the team should understand exactly what they do.

## Decision

An orchestrator agent delegates to medication, schedule, and summary agents, exposed to it as tools, using the Anthropic SDK's tool use written by hand — no agent framework. Sub-agents return a Pydantic-validated `{answer, citations, needs_care_team}`. Guardrails: at most 6 tool calls per question, depth 1, a 30-second timeout, least-privilege read-only tools, every call logged to `QALog`, and a safe fallback message on any limit. Only `app/llm.py` calls the SDK.

## Alternatives considered

- **LangGraph or another framework** — more features, but another thing to learn and debug; possible later.
- **A single prompt** — simpler, but weaker on multi-part questions.

## Consequences

- Full control and easy-to-read code; more code to write ourselves.
- Limits are configured in `app/config.py` and covered by tests.
