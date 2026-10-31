# ADR-0022: Downloadable `.ics` calendar file first; Google Calendar sync later

- **Status:** Accepted
- **Date:** 2026-10-31
- **Deciders:** team
- **Supersedes:** none

## Context

Medicine reminders are a core feature. Writing directly to Google Calendar needs extra Google permissions and Google's app review, and not every user uses Google Calendar.

## Decision

- The MVP gives users a **downloadable `.ics` file** that they add to any calendar app themselves (ADR-0006: built by plain code, private titles by default, no events for STOPPED or AS NEEDED medicines).
- **Google Calendar sync is a later, optional feature.** When built, the app asks for calendar permission only at that moment, when the user taps "Add to Google Calendar", never at sign-in.

## Alternatives considered

- **Calendar permission at sign-in** — more convenient, but a scarier first screen and a heavier Google review.

## Consequences

- Works with every calendar app from day one.
- No calendar permission handling or token storage in the MVP.
- When sync is added, it needs its own ADR covering scopes, token storage, and what happens when the profile changes.
