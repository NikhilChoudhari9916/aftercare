# ADR-0004: Two pipelines; fixed code decides whether safety checks run

- **Status:** Accepted
- **Date:** 2026-10 (recorded 2026-10-31)
- **Deciders:** team
- **Supersedes:** none

## Context

LLM agents are flexible but can be wrong, skip steps, or be manipulated by text in a document or question. Safety checks must run every time, no matter what an agent does.

## Decision

- **Upload pipeline** (once per document): fixed steps, no agents — text check → extraction → quote check → abbreviation cleanup → patient confirmation → save profile → enrichment → indexing.
- **Question pipeline** (every question): safety gate → orchestrator and specialist agents → output validators.
- **Agents decide *how* to answer; fixed code decides *whether* safety checks run.** `app/agents/runner.py` always calls the gate first and the validators last. No agent can call, skip, or change them, and no agent can write patient data.

## Alternatives considered

- **Let an agent call a "safety check" tool** — the agent could forget or be talked out of calling it.
- **One big prompt, no agents** — simpler, but handles multi-part questions poorly.

## Consequences

- Safety holds even when an agent misbehaves.
- Agents get only read-only, least-privilege tools.
- Clear module boundaries: safety and validator code never import agent code.
