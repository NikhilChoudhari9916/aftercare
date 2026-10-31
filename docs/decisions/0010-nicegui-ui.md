# ADR-0010: NiceGUI for the web UI

- **Status:** Accepted
- **Date:** 2026-10-31
- **Deciders:** team
- **Supersedes:** ADR-0009

## Context

AfterCare is a web app, and most patients will open it in a phone browser, tired and just home from the hospital. The UI needs: a side-by-side confirmation screen (each medicine next to its original line), small "From your papers" citation tags, tappable follow-up buttons, a read-aloud button, and a chat that doesn't reload the whole page on every click. The team prefers to stay in Python.

## Decision

Build the web UI with **NiceGUI**, in `ui/`, as its own process that calls the FastAPI backend over HTTP through `ui/api_client.py` (ADR-0003). Even though NiceGUI runs on FastAPI internally, it is not mounted inside the backend app.

- Pages: upload, confirm, summary, schedule, ask (`ui/pages/`).
- Reusable pieces: citation tag, follow-up buttons, read-aloud (`ui/components/`). Read-aloud uses the browser's built-in speech synthesis via NiceGUI's JavaScript bridge.
- Every page must work at phone width (about 375 px) and on desktop.

## Alternatives considered

- **Streamlit** (ADR-0009) — fastest to start, but desktop-dashboard layouts, limited custom components, and full-script reruns.
- **React + Vite + TypeScript + Tailwind** — best UX and resume value, but needs JavaScript skills the team doesn't want to take on now. Still possible later because of ADR-0003.
- **Reflex** — also pure Python, but compiles to a separate React app, adding build complexity.

## Consequences

- Python only, with responsive Quasar/Vue components and event-driven updates (no full reruns).
- Smaller community than Streamlit or React: fewer examples to copy.
- `CLAUDE.md` sections 3 and 10 updated in the same change.
