# ADR-0007: Digital PDFs only; the patient confirms every extracted item

- **Status:** Accepted
- **Date:** 2026-10 (recorded 2026-10-31)
- **Deciders:** team
- **Supersedes:** none

## Context

Extraction can be wrong, and every later answer depends on it. Scanned documents and photos need OCR, which adds a second error source.

## Decision

- Accept **digital PDFs only** (with a text layer). Scanned PDFs get a friendly rejection. Photo upload and OCR are deferred.
- Every extracted item must include a `source_quote`, which code fuzzy-matches against the document text.
- The patient **confirms, edits, or removes** each item, shown next to its original line. **Nothing unconfirmed is ever used** in answers, schedules, or calendar files. The profile is versioned.

## Alternatives considered

- **Trust the extraction** — one silent error would flow into every answer.
- **Support scans now** — more users, but more errors and more build time.

## Consequences

- One extra step for the user, but a much safer profile.
- Some real-world documents can't be used in the MVP.
- Tests must cover the "unconfirmed item is ignored" rule.
