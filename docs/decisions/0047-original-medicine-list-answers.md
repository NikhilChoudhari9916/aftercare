# ADR-0047: Fixed original-list answers for two common questions

- **Status:** Accepted by explicit user request, 2026-11-21
- **Extends:** ADR-0046 (original evidence remains authoritative)

Generated draft checks could reject useful responses before original-excerpt release. For the
explicit new-medicine and all-medicine-purpose questions, a server-owned graph node now calls a
typed read-only tool that reads complete original medicine-list entries. It recognizes a limited
set of headings and explicit status markers, checks full list coverage, preserves warnings, and
never derives a purpose from a medicine's name, timing or a modified extraction. Unknown layouts
fall back to the existing router/ReAct path. This does not turn free-form model text into evidence.

A medicine-taking pronoun without an unambiguous recent identity gets a fixed clarification.
With explicit context, the normal reference resolver and original-paper answer path are retained.
Emergency and edit-comparison branches precede both nodes. A Tier 2 reply keeps a care-team line.
The tool is code-invoked for these intents, not added to the agent's two-tool allowlist. The
existing tool schema/registry mechanism executes it; there is no separate MCP transport server.
No prompt version, model setting or dependency changes. Offline tests cover original rows,
negative purpose wording, incomplete extraction, edits, emergencies, ambiguity and patient scope.
The seven-question live sample and browser smoke test are documented under docs/assignment/.
