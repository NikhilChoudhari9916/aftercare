# ADR-0001: Record architecture decisions as ADRs

- **Status:** Accepted
- **Date:** 2026-10-31
- **Deciders:** team
- **Supersedes:** none

## Context

Three people are building AfterCare over eight weeks, and many decisions were made in planning chats that the rest of the team (and Claude Code) can't see. Without a written record, decisions get silently reversed or re-argued.

## Decision

Record each significant decision as a short, numbered ADR in `docs/decisions/`. Accepted ADRs are never rewritten; a changed decision gets a new ADR that supersedes the old one.

## Alternatives considered

- **Only `CLAUDE.md`** — says *what* we do, but loses *why* and the history of changes.
- **A wiki or chat thread** — not versioned with the code, and Claude Code can't read it.

## Consequences

- Anyone can see why the project looks the way it does, and when it changed.
- Changing a decision costs one small PR, which is the point: it forces a conversation.
- `CLAUDE.md` stays the current rulebook; ADRs are the reasoning and history behind it.
