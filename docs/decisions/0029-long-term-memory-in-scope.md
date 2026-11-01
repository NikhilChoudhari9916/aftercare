# ADR-0029: Short-term and long-term memory are in scope

- **Status:** Accepted
- **Date:** 2026-11-01
- **Deciders:** team
- **Supersedes:** ADR-0024

## Context

The Assignment 3 deck designs two kinds of memory and uses them in all five use cases. ADR-0024 deferred long-term memory but fixed the rules. The team has decided to build it. The rules of ADR-0024 stay; only the "deferred" part changes.

## Decision

**Short-term memory (one session).** The last 10 turns plus a rolling summary, the medicine or topic in focus ("that pill"), a pending clarifying question, and who is speaking (patient or aide). It is cleared when the session ends. Nothing moves to long-term memory unless the user confirms it.

**Long-term memory (per user), as structured records, not embeddings:** preferred name and role; the confirmed medicine list with the date confirmed (the versioned profile); a symptom log; a taken-and-missed medicine log; the confirmed follow-up visit date; saved questions for the doctor; and the discharge date, which defines the 30-day window.

**Lifecycle**
1. **Write:** only facts the user states or confirms; never model guesses.
2. **Store:** per user, structured records, encrypted. Field-level encryption must be in place before any real data is used; the library choice needs team approval as a new dependency.
3. **Retrieve:** by task and recency, for this user only.
4. **Update:** a newer confirmed fact replaces an older one. Conflicts are flagged, never merged.
5. **Forget:** automatic deletion 30 days after discharge, plus "forget this" and delete-all controls.

**When memory is used:** when the task needs it (visit prep reads the logs; a medicine question reads the confirmed list) or to resolve "it" and "that pill". **Memory is ignored or reset** on an urgent symptom (fixed message, no memory), when a new discharge document is uploaded (the old list is archived and the user re-confirms), when memory conflicts with the paperwork (the paperwork wins and both are shown), and when the profile changes.

**Retained from ADR-0024:** memory is separate from the profile and never overrides the confirmed medicines or schedule; code writes memory and agents only read it (ADR-0004); the user can view, edit, and delete it; it carries `patient_id`, follows the 30-day deletion rule, and never appears in console logs.

**Safety:** a symptom the user types still passes the safety gate first. Logging an urgent event to the symptom log happens only with the user's consent.

## Alternatives considered

- **Keep memory deferred (ADR-0024)** — smaller MVP, but visit prep, the medicine log, and "that pill" follow-ups all depend on it.
- **Store memory as embeddings** — values such as doses and dates must be exact, so structured records are right.

## Consequences

- New tables: `SymptomLogEntry`, `DoseLogEntry`, `SavedQuestion`, plus fields on `Patient` and `Preference` (`CLAUDE.md` section 9).
- A larger privacy surface, handled by ADR-0031.
- Built after the core question pipeline (`CLAUDE.md` section 12).
