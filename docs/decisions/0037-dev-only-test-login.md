# ADR-0037: A development-only test login, until a Google test client exists

- **Status:** Accepted
- **Date:** 2026-11-11
- **Deciders:** team
- **Supersedes:** none (a fallback for how ADR-0021 and ADR-0033 are run locally)

## Context

Real Google sign-in needs an OAuth client in a Google Cloud project (`TEAM_SETUP.md`). The developer's Google Cloud console is locked while an appeal for an unrelated suspended project is reviewed, so no client can be created for now. The assignment is due on 2026-11-15 and every patient endpoint needs a signed-in user.

## Decision

Add a **development-only test login**. The real Google sign-in stays exactly as it is and is switched on as soon as a client exists.

- It is off unless `DEV_LOGIN=1` is set. It is a setting in `app/config.py`.
- **The app refuses to start** if `DEV_LOGIN` is on while `APP_ENV=production`, or when `BACKEND_URL` is not `localhost`, `127.0.0.1`, or `[::1]`.
- `POST /auth/dev-login` also answers 404 unless the request's own host is one of those local names, and always when the setting is off.
- It signs in one of two **fixed synthetic people** ("alex" and "sam", with `dev:` subject IDs and `@aftercare.test` emails; `.test` can never be a real address). Two people exist so the two-patient privacy tests and demo have someone to be "the other patient".
- It goes through the same code as Google sign-in: the same user lookup, the same first-sign-in patient creation, the same server-side session and cookie, the same role checks. Nothing about authorization is relaxed.
- The UI shows the test buttons only when its own `DEV_LOGIN` is on, and labels them "Test sign-in (development only)".
- It carries no passwords, so no credentials can leak. It has no real-person data.

## Alternatives considered

- **Wait for the console to unlock.** The timing is out of our control and the assignment has a fixed date.
- **A second Google account or a new Gmail for the OAuth client.** It might be blocked by the school's rules, and a new account made right after a suspension may look like evasion.
- **Disable auth in development.** It would test a different code path from the real one and hide role bugs.

## Consequences

- Tests show: refused in production, refused when off, refused on a non-local host or address, creates a normal session and role, reuses an existing user, and leaves the Google routes unchanged.
- The slides and README say plainly that the demo uses the test login.
- Once a Google client exists, set `DEV_LOGIN` off. The code can stay; it cannot run outside local development.
- Run the `security-reviewer` skill on it before the demo.
