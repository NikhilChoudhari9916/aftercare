# Orchestration platforms: what we compared and why LangGraph

Written for the Assignment 4 slides. **Be honest on the slide about what was built and what was only
assessed.** Only LangGraph and the plain-SDK style were used in this project; n8n and CrewAI were
assessed against our requirements, not built. Check each platform's current documentation before
quoting a feature.

## What our workflow needs

1. Conditional edges: a Tier 1 emergency ends early; a router sends a question one of three ways;
   a failed answer goes back once, then to a fallback.
2. A tool-using loop with hard limits (6 calls, 30 seconds).
3. Safety steps that no model can skip: the gate before everything, the validators after the agent.
4. Every step testable on its own without calling a model.
5. One process we can run and secure on a laptop; patient text stays in our own code.
6. Tools described MCP-style (name, description, JSON schema, typed result) so a real MCP server
   could serve them later.

## Comparison

| | LangGraph (chosen) | Plain SDK loop (our first design, ADR-0008) | n8n | CrewAI |
|---|---|---|---|---|
| Conditional logic | Conditional edges between named nodes | Hand-written `if` statements | Visual branches | Agents decide who works next |
| Tool loop and limits | Agent and tools nodes with an edge on "did it ask for a tool?"; limits in our code | Fully hand-written | Possible, but limits live in the tool's settings | Built in, but agent-driven |
| Safety steps that cannot be skipped | Yes: we wire the gate and validators as nodes and add no edge around them | Yes, if the code is careful | Harder to enforce and to test | Opposite of our rule: agents choose the path |
| Test each step alone | Nodes are plain functions; graph tests cover each edge | Easy, but control flow is tangled | Test through the service | Test through the framework |
| Run and secure | A Python library inside our backend | Nothing extra | A separate service to run and secure | A Python library |
| Explain with a diagram | The graph can print its own diagram | Diagram drawn by hand | Excellent | Role diagrams |
| Evidence in this project | **Built and tested** (upload graph, question graph) | Considered first, replaced | Assessed on paper | Assessed on paper |

## Decision

LangGraph (ADR-0035, ADR-0044): both of our workflows are already graphs, it keeps the safety steps
in tested Python we control, and it adds one library rather than one service.

## Costs we accepted

- One more abstraction to learn; graph state must never be logged (it holds patient text).
- A node that crashes ends the whole run, so `run_question` catches errors and returns the safe
  fallback.
- The 30-second limit is checked between steps, not inside a model call.
- Tools are MCP-**style**: one registry with schemas, not a running MCP server.
