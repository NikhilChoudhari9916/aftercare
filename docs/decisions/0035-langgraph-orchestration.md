# ADR-0035: LangGraph orchestrates the upload and question workflows

- **Status:** Accepted
- **Date:** 2026-11-11
- **Deciders:** team
- **Supersedes:** ADR-0008

## Context

ADR-0008 chose a hand-written tool-use loop and no framework. The course assignment (workflow with tool use, orchestration, MCP-style tools, multi-step and conditional logic) asks the team to evaluate at least two orchestration platforms and implement the workflow on one. Both of our workflows are already graphs: the question pipeline is gate, route, specialist, validators, with retries and early exits, and the upload pipeline has early exits for scanned PDFs and unmatched quotes.

## Decision

Use **LangGraph** (`StateGraph`) for both workflows:

- **Upload graph:** ingest PDF, conditional (no text layer: reject), LLM extraction, quote check, conditional (unmatched quotes: flag the items), abbreviation cleanup, stop at "waiting for confirmation".
- **Question graph:** `safety_gate`, conditional (Tier 1: fixed 911 text and end), `load_context`, `router`, a specialist ReAct loop (agent, tools, agent, with a conditional edge on "did the agent ask for a tool?"), `validators`, conditional (fail once: back to the specialist with the reason; fail twice: safe fallback), `finalize`.

Rules that keep ADR-0004 intact inside a framework:
1. **The safety gate and validators are nodes we wire into the graph.** The agent's tool list never contains them, and the graph has no edge that skips them.
2. **Nodes are plain functions** that take and return state, so each is unit-testable without the graph. Graph tests cover each conditional edge.
3. **`app/llm.py` stays the only module that imports the Anthropic SDK.** We do not add `langchain-anthropic`; nodes call our wrapper.
4. Tools are described MCP-style (name, description, JSON input schema, structured result) in one registry in `app/tools/`, so they could be served over a real MCP server later.
5. The ReAct loop is capped: at most 6 tool calls and 30 seconds per question; any limit gives the safe fallback.

The comparison that supports this choice (LangGraph, a plain SDK loop, n8n, CrewAI) is in `docs/assignment/platform-comparison.md`.

## Alternatives considered

- **Plain SDK loop (ADR-0008)** — no dependency and maximum control, but routing, retries, and early exits become hand-written control flow that is harder to show, test edge by edge, and explain.
- **n8n** — a visual workflow tool, good for diagrams, but a separate service to run and secure, and a poor fit for keeping safety logic in tested Python.
- **CrewAI** — role-based multi-agent framework; it makes agents decide who works next, which is the opposite of "fixed code decides whether safety checks run".

## Consequences

- New dependencies: `langgraph` (which brings `langchain-core` and a few small `langgraph-*` packages), pinned in `requirements.txt`.
- ADR-0008 is superseded; `CLAUDE.md` sections 3 and 4 are updated in the same change.
- One more abstraction to learn, and graph state must stay free of patient text in logs (ADR-0031).
