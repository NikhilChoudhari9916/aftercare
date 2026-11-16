# ADR-0044: The question workflow for the assignment slice

- **Status:** Accepted
- **Date:** 2026-11-14
- **Deciders:** team
- **Supersedes:** none (builds what ADR-0035 and ADR-0036 describe)

## Context

The safety gate, the tool registry, the retriever and the validators existed but nothing connected
them. The assignment needs one working workflow with tool use, conditional logic and a screen to
use it (ADR-0036).

## Decision

One LangGraph question graph in `app/agents/question_graph.py`, called by `POST /patients/{id}/ask`
(owner or aide):

`safety_gate` -> Tier 1: the fixed 911 text and stop. Otherwise `load_context` -> `router` ->
`agent` <-> `tools` (the ReAct loop) -> `validators` -> `finalize`, with one retry and then
`fallback`.

- **Router (Haiku, `prompts/router_system_prompt_v1.txt`):** picks MEDICINE, SCHEDULE or
  OUT_OF_SCOPE and rewrites the question so "it" names the medicine. SCHEDULE and OUT_OF_SCOPE get
  a fixed reply written in code, with no agent. A Tier 2 symptom always goes to the agent. If the
  router fails, the question goes to the agent, which has its own scope rule.
- **One specialist for now:** the medication agent (prompt v7, Sonnet) with four tools only:
  `get_confirmed_medicines`, `search_patient_document`, `search_fda_label`, `lookup_rxnorm`.
  The schedule and summary agents of CLAUDE.md section 4 stay later; a schedule question is
  answered by pointing to the Schedule page, which is built by code (ADR-0006).
- **Tool result IDs:** passages already carry `D#`; a drug label is given `L#` by the workflow
  (`app/qa/sources.py`). The validators receive exactly those sources and may cite nothing else.
- **Limits, all ending in the safe fallback:** 6 tool calls, 30 seconds (checked between steps; a
  single slow model call can overrun it), a failed model call, two failed answers, any unexpected
  error. The validators run on the model's own 911 text too, so a missed emergency is not replaced
  by the fallback.
- **The gate result goes to the agent as an app note** in the first user message, so the model
  knows the tier the code decided. Prompt v7 is unchanged.
- **Short-term memory** (`app/memory/session.py`): the last 10 turns and the medicine in focus, in
  this process's RAM only, keyed by login session and patient. It is never written to disk or to a
  log, and an emergency or a fallback is never remembered.
- **`QALog`:** one row per question with the tier, task, outcome, cited IDs, tool names and counts,
  failed check names, retrieval mode and timings. No question or answer text (ADR-0031).
- **Ask page** (`ui/pages/ask.py`): chat box, source labels instead of codes, follow-up buttons,
  an always-visible 911 line, and the disclaimer under every answer.

## Alternatives considered

- **Orchestrator plus three specialist agents now:** matches CLAUDE.md, but each agent needs its own
  prompt and eval, and none can be validated by Sunday.
- **Letting the model call the router, gate or validators as tools:** rejected; fixed code decides
  whether safety checks run (ADR-0004).

## Consequences

- New: `QALog`, `app/memory/`, `app/qa/{routes,sources,profile_text}.py`, the router prompt, the
  question graph, the Ask page. Existing tests that list the navigation links were updated.
- The router prompt and v7 inside the agent loop have **not** been evaluated on the real model yet;
  the full-path eval (handoff C2) must run before anything on a slide claims accuracy.
- Memory is lost on a server restart and is not shared between server processes.
