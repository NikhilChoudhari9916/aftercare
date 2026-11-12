# Team setup (about 15 minutes per person)

## Repo owner, once

Done after the GitHub repo is created:

1. **Add the two teammates:** GitHub → repo → Settings → Collaborators → Add people (their GitHub usernames), role **Write**.
   Or: `gh api -X PUT repos/<owner>/aftercare/collaborators/<username> -f permission=push`
2. **Protect `main`:** Settings → Branches (or Rules → Rulesets) → add a rule for `main`:
   - Require a pull request before merging, with 1 approval
   - Dismiss stale approvals when new commits are pushed
   - Require status checks to pass: **CI / checks**
   - Block force pushes and deletions
3. **Merge settings:** Settings → General → Pull Requests: allow **Squash merging** only, and turn on "Automatically delete head branches".
4. Fill in the owner names in `CONTRIBUTING.md` (via a PR).

## Everyone

### 1. Clone

```bash
git clone https://github.com/<owner>/aftercare.git
cd aftercare
```

### 2. Python environment (Python 3.12, the same for everyone: ADR-0019)

Windows (PowerShell):
```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS / Linux:
```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Then:
```bash
pip install --upgrade pip
pip install pre-commit
pip install -r requirements.txt -r requirements-dev.txt
pre-commit install
```

`pre-commit install` is the important one. It makes the formatting, lint, and secret checks run on every commit.

### 3. Your own `.env` and keys

```bash
cp .env.example .env
```
Never share `.env`, never commit it. `.gitignore` and the secret scanner both guard this, but don't rely on them. Fill in these lines:

| Line | What to put | Needed for |
|---|---|---|
| `DEV_LOGIN` | `1` | The "Test patient Alex / Sam" sign-in buttons (ADR-0037). No Google account needed. The app refuses to start with this on in production or on a non-local address. **Use this to start.** |
| `LOGIN_STATE_SECRET` | any long random string (`python -c "import secrets; print(secrets.token_urlsafe(32))"`) | Real Google sign-in only. Optional while you use `DEV_LOGIN`. |
| `ANTHROPIC_API_KEY` | your own key from the Anthropic Console (add a few dollars of credit) | Real AI: reading a PDF, the safety classifier, answering questions. **Not needed** to run the app with the demo backend (step 5), or to run the tests. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | your own Google OAuth test client (below) | Real Google sign-in. **Optional** now that the test login exists. |

**Google sign-in test client (optional).** In the Google Cloud Console: create a project, set up the OAuth consent screen as *External* in *Testing* mode and add your own Google email as a test user, then create an *OAuth client ID* of type *Web application* with the redirect URI `http://localhost:8000/auth/callback`. Put the client ID and secret in your `.env`. Use your own project and your own keys; never share or commit them.

### 4. Claude Code plugins

The project's `.claude/settings.json` turns on two plugins from Anthropic's official marketplace. Claude Code may not prompt you to install them automatically, so install them by hand inside Claude Code:

```
/plugin install code-review@claude-plugins-official
/plugin install superpowers@claude-plugins-official
```

- **code-review**: an automated review of your branch before a teammate reviews it.
- **superpowers**: plan-first, test-first workflows for bigger features.

The coding principles (think first, keep it simple, surgical changes, prove it's done) are written directly into `CLAUDE.md` section 16, so they need no plugin.

### 5. Check it works, then see it running

```bash
pytest                      # all tests; they never call the internet or the real model
ruff check . && ruff format --check .
```
Both should pass. (CI runs the same checks. Tests marked `eval` call the real model, are run by hand with `pytest -m eval`, and are not part of CI.)

To **see the app** without any API key, start the backend with a scripted fake model, then the web page, in two terminals (with your virtual environment active in each):

```bash
python scripts/demo_backend.py     # terminal 1: http://localhost:8000
python -m ui.main                  # terminal 2: http://localhost:8080
```

Open http://localhost:8080 and click **Test patient Alex**. Upload `data/synthetic/patient1_discharge_summary.pdf`, check each item, confirm, then open **Summary** and **Schedule** and try the calendar download. The fake model answers with the synthetic Patient 1 profile for *any* PDF, so use that sample file. The demo uses a throwaway database, so nothing carries over between runs.

To run the **real** backend (needs `ANTHROPIC_API_KEY`), start it with `uvicorn app.main:app --port 8000` instead of the demo script. Both programs read the same `.env`, so `DEV_LOGIN=1` must be in it for the test buttons to show.

If a page looks wrong after you edit UI code, restart the UI process: it does not reload by itself.

## Then read

1. [`docs/handoff.md`](docs/handoff.md): what is built, what is not, and what to pick up next.
2. `CLAUDE.md`: what we're building, the architecture, and the coding rules.
3. `CONTRIBUTING.md`: how work moves through branches, PRs, and reviews.
4. [`docs/decisions/`](docs/decisions/README.md): why each choice was made (read the ones near your task).
