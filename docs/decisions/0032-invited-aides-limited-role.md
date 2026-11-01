# ADR-0032: Aides are invited by email and get a limited role

- **Status:** Accepted
- **Date:** 2026-11-01
- **Deciders:** team
- **Supersedes:** part of ADR-0021 (the shared login and the single kind of user)

## Context

ADR-0021 had the aide sign in with the patient's login and made everyone the same kind of user. The Assignment 3 deck says a caregiver sees the data "only if invited", and the team wants to restrict what an aide can do with the patient's records. A restriction cannot be enforced on someone using the patient's own Google login, because the system sees the patient. A "switch to aide mode" button would also not restrict anything.

## Decision

**Access.** The patient invites an aide by Google email. The aide signs in with their **own** Google account and gets the **aide** role for that patient. The patient is the **owner**. Google sign-in stays identity-only (ADR-0021).

**Permissions.** The server checks the role on every request.

| Action | Owner (patient) | Aide |
|---|---|---|
| View summary, schedule, calendar file, visit prep, and the logs | yes | yes |
| Ask questions | yes | yes |
| Add taken or missed doses | yes | yes |
| Add saved questions for the doctor | yes | yes |
| Add symptom log entries | yes | no |
| Upload or replace documents | yes | no |
| Confirm, edit, or remove extracted medicines | yes | no |
| Delete or forget memory, change memory settings, delete the patient's data | yes | no |
| Change preferences, including calendar title privacy | yes | no |
| Invite or remove aides | yes | no |

**Invites.** A pending invite shows nothing until the aide signs in with the invited email (Google reports it as verified) and accepts. Invites expire after 7 days by default. The patient sees who has access and can revoke it at any time; revoking takes effect on the aide's next request. One aide may have access to more than one patient. Memberships are deleted when the patient's data is deleted.

**Everything else is unchanged for an aide:** the safety gate and validators run the same way, and an aide gets the same facts as the patient. "Who is speaking" in session memory comes from the signed-in role, not from a toggle. An aide's questions are session-only like anyone's (ADR-0031).

**Records.** A `PatientAccess` table (patient, user, role, invited by, status, created, expires) replaces the single "patient belongs to user" link, and an `AccessEvent` table records invites, acceptances, revocations, and denied attempts (IDs only, no patient text).

## Alternatives considered

- **Shared login with an aide mode** (ADR-0021) — simplest, but not a real restriction.
- **Per-aide switches for each permission** — more control, more to build and explain; revisit if the preset proves too coarse.
- **View and ask only** — safer, but an aide who manages the pill box could not log doses.

## Consequences

- The access check in `app/auth/dependencies.py` becomes a role check, built in from the sign-in step (owner only at first). Aide invites and the aide role are built together with long-term memory, because the aide's dose logging needs it (`CLAUDE.md` section 12).
- Tests must cover every owner-only endpoint returning 403 for an aide, the invite and revoke flow, and that an aide of patient A cannot read patient B (extends the two-patient leak test of ADR-0031). Run the `security-reviewer` skill on this work.
- The UI shows an aide a clear "You are viewing as an aide" banner, and shows the patient who has access.
- Anyone who uses the patient's own login is still the patient. The UI should say so when the patient adds an aide.
