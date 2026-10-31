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
pip install pre-commit ruff pytest
pip install -r requirements.txt   # once build step 1 has created it
pre-commit install
```

`pre-commit install` is the important one. It makes the formatting, lint, and secret checks run on every commit.

### 3. Your own API key

```bash
cp .env.example .env              # once build step 1 has created it
```
Put your own `ANTHROPIC_API_KEY` in `.env`. Never share it, never commit it. `.gitignore` and the secret scanner both guard this, but don't rely on them.

### 4. Claude Code plugins

The project's `.claude/settings.json` turns on two plugins from Anthropic's official marketplace. Claude Code may not prompt you to install them automatically, so install them by hand inside Claude Code:

```
/plugin install code-review@claude-plugins-official
/plugin install superpowers@claude-plugins-official
```

- **code-review**: an automated review of your branch before a teammate reviews it.
- **superpowers**: plan-first, test-first workflows for bigger features.

The coding principles (think first, keep it simple, surgical changes, prove it's done) are written directly into `CLAUDE.md` section 16, so they need no plugin.

### 5. Check it works

```bash
git switch -c chore/setup-check-<yourname>
pre-commit run --all-files
pytest
git switch main
git branch -D chore/setup-check-<yourname>
```

Both should pass (pytest may report "no tests ran" until build step 1 lands).

## Then read

1. `CLAUDE.md`: what we're building, the architecture, and the coding rules.
2. `CONTRIBUTING.md`: how work moves through branches, PRs, and reviews.
