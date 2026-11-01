# ADR-0021: Google sign-in for identity only; patients and aides are the same kind of user

- **Status:** Accepted for Google sign-in with identity only. The shared login and the single kind of user are superseded by ADR-0032.
- **Date:** 2026-10-31
- **Deciders:** team
- **Supersedes:** none

## Context

Patients need an account so their profile, schedule, and preferences are saved and private, and Google sign-in avoids storing passwords. A patient's aide (family member or caregiver) often helps with the discharge papers. Earlier notes deferred caregiver accounts.

## Decision

- Users sign up and sign in with **Google** (OAuth 2.0 / OpenID Connect). A first sign-in creates the account.
- Ask for **identity only** (`openid`, `email`, `profile`). No calendar or other Google permissions at sign-in (see ADR-0022).
- **One kind of user.** An aide who wants access signs in with the patient's login. There are no separate caregiver roles or invitations in the MVP; separate caregiver accounts stay deferred.
- Every patient record belongs to a `User`. Every API endpoint that touches patient data requires a signed-in user and checks that the patient belongs to them, on top of the existing `patient_id` filtering.
- Sessions are server-side or signed cookies; the auth library is chosen in the auth pull request and needs team approval before it is added as a dependency.

## Alternatives considered

- **Email and password** — more to build and secure, and passwords become something to leak.
- **Separate caregiver accounts with invitations** — better audit trail and finer control, but a larger build; revisit later.
- **No accounts** — simplest, but nothing could be saved or protected per person.

## Consequences

- No passwords to store.
- Anyone who has the Google account can see that patient's data, so the UI should say so plainly.
- Each teammate creates their own Google OAuth client (test mode, `localhost` redirect) for development. Client secrets live only in `.env`.
- New `User` table; new auth endpoints (`CLAUDE.md` section 11).
