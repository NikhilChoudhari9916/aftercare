# ADR-0033: The backend owns Google sign-in and the session

- **Status:** Accepted
- **Date:** 2026-11-01
- **Deciders:** team
- **Supersedes:** none (settles how ADR-0021 and ADR-0032 are built)

## Context

The NiceGUI UI and the FastAPI backend are two separate processes (ADR-0003, ADR-0010). Something has to run the Google login, remember who is signed in, and be the single place that decides what each user may do (ADR-0032). If both processes handled auth, they would drift apart and one of them could be bypassed.

## Decision

**The backend owns sign-in and the session. The UI holds no auth logic and no auth state of its own.**

Flow:
1. The UI's "Sign in" button sends the browser to the backend's `GET /auth/login`.
2. The backend starts Google's authorization-code flow with **PKCE** and a random **`state`** value, and checks both on `GET /auth/callback`.
3. It verifies Google's ID token, requires a verified email, and keys the account on Google's stable **subject ID**, never on the email address. Scopes are `openid`, `email`, `profile` only.
4. It creates a **server-side session** (a row in a `Session` table) and sets a cookie holding a random token. Only a **hash** of the token is stored. The cookie is `HttpOnly`, `Secure` (everywhere except local development over `http://localhost`), and `SameSite=Lax`.
5. The backend redirects the browser back to the UI.
6. On every page, the UI reads the cookie from the incoming request and forwards it to the backend through `ui/api_client.py` (for example `GET /me`). A 401 means the UI sends the user to sign in. The UI never decodes or stores the token itself.

**Session rules:** a session ends after 12 hours of inactivity or 7 days in total, whichever comes first; both limits live in `app/config.py`. Logout deletes the row, so it takes effect at once. Sessions are server-side rather than self-contained tokens so that logout and a patient revoking an aide (ADR-0032) cannot be outlived by a copied token.

**Extra protection against forged requests:** `SameSite=Lax` plus a check of the `Origin` header on every state-changing request.

**One origin:** a browser sends cookies by host, not by port, so on `localhost` the UI (port 8080) and the backend (port 8000) share the cookie during development. A hosted demo must serve both behind one domain, with a reverse proxy sending `/api` to the backend (ADR-0020).

The auth library (for example Authlib) is chosen in the auth pull request, and it needs team approval first.

## Alternatives considered

- **The UI owns sign-in** — NiceGUI could do it, but then the backend would trust the UI, and any other client could skip the checks.
- **Both processes check the user** — duplicated logic that drifts.
- **Stateless signed tokens (JWT)** — simpler to run, but a copied token stays valid until it expires, which fails the instant-revoke requirement.

## Consequences

- New table `Session`; auth endpoints stay as in `CLAUDE.md` section 11.
- Every backend request goes through one dependency, `current_user`, then the role check (ADR-0032). Tests must show that a request with no cookie, an expired session, or a deleted session gets a 401.
- Each developer needs their own Google OAuth test client with `http://localhost:8000/auth/callback` as the redirect address; the client secret lives only in `.env`.
- Run the `security-reviewer` skill on the sign-in pull request.
