# ADR-0003: FastAPI backend; the UI is a separate client over HTTP

- **Status:** Accepted
- **Date:** 2026-10 (recorded 2026-10-31)
- **Deciders:** team
- **Supersedes:** none

## Context

The UI technology was likely to change (it already has: ADR-0009 → ADR-0010). Safety logic must not depend on, or be bypassable from, the UI.

## Decision

All logic lives in a **FastAPI** backend (`app/`). The web UI (`ui/`) is a separate process that only calls the backend's HTTP API (`CLAUDE.md` section 11). The UI never imports from `app/`.

## Alternatives considered

- **UI and logic in one app** — faster to start, but swapping the UI would mean rewriting logic, and safety code could be skipped by a UI shortcut.

## Consequences

- The UI can be replaced (for example with React) without touching the backend.
- Every feature needs an API endpoint before the UI can use it.
- The backend can be tested fully without any UI.
