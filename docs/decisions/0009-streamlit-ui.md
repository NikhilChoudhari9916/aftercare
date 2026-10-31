# ADR-0009: Streamlit for the MVP UI

- **Status:** Superseded by ADR-0010
- **Date:** 2026-10 (recorded 2026-10-31)
- **Deciders:** team
- **Supersedes:** none

## Context

The team needed a UI quickly, in Python, without front-end experience.

## Decision

Use Streamlit for the MVP UI, calling the FastAPI backend.

## Alternatives considered

- **React** — better UX, but needs JavaScript skills.

## Consequences

Kept for history. Replaced before any UI code was written, because Streamlit is built for desktop data dashboards: most patients will open AfterCare in a phone browser, and the design needs custom citation tags, follow-up buttons, read-aloud, and a side-by-side confirmation screen. See ADR-0010.
