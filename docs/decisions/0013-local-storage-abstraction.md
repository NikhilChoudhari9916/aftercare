# ADR-0013: Local file storage behind `app/storage.py`

- **Status:** Accepted
- **Date:** 2026-10-31
- **Deciders:** team
- **Supersedes:** none

## Context

Uploaded PDFs must be stored somewhere. During development everything is synthetic, and teammates and CI should not need cloud accounts or credentials to run the app or tests.

## Decision

Store uploads on the local disk at `storage/patients/{patient_id}/documents/{document_id}.pdf` (gitignored, never modified after upload). **All file access goes through `app/storage.py`** (`save_pdf`, `get_pdf`, `delete_patient_files`), so the storage location can change by editing one file.

## Alternatives considered

- **AWS S3 now** — needed for a deployed demo (see ADR-0020, proposed), but adds credentials and setup for everyone during development.

## Consequences

- Zero setup; tests are fast and need no secrets.
- Not suitable for a hosted deployment as is: most hosts wipe the local disk on redeploy.
- Real patient data would require encrypted cloud storage, access control, audit logs, and deletion after 30 days (`CLAUDE.md` section 15).
