# ADR-0006: Schedules, doses, and dates are computed by code, never the LLM

- **Status:** Accepted
- **Date:** 2026-10 (recorded 2026-10-31)
- **Deciders:** team
- **Supersedes:** none

## Context

LLMs make arithmetic and date mistakes. A wrong time or end date in a medicine schedule could cause real harm.

## Decision

The medicine schedule and the `.ics` calendar export are built by plain code from the confirmed profile (`app/summary/schedule.py`, `calendar_export.py`). Unrecognized frequencies are shown as written, and the patient is asked to set the timing. Calendar defaults: private titles, end dates for fixed courses, no events for STOPPED or AS NEEDED medicines, local time zone, follow-ups as one-time events.

## Alternatives considered

- **Ask the LLM to build the schedule** — convenient, but unverifiable and occasionally wrong.

## Consequences

- Schedules are fully unit-testable and repeatable.
- Unusual instructions need a human (the patient) to set timing instead of a guess.
- Agents read the schedule through a tool; they never compute times themselves.
