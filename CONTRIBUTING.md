# Contributing to AfterCare

Three people, one repo. These rules keep `main` working and keep the three of us from stepping on each other. Coding rules are in `CLAUDE.md` section 16; this file is about how work moves.

## Who owns what

| Area | Owner | Folders |
|------|-------|---------|
| A: Documents | _name_ | `app/ingestion/`, `app/extraction/`, `app/enrichment/`, `app/storage.py` |
| B: Safety and answers | _name_ | `app/safety/`, `app/qa/`, `app/agents/`, `app/tools/`, `data/red_flags.yaml` |
| C: Experience and testing | _name_ | `ui/`, `app/summary/`, `tests/eval/` |
| Shared (anyone, review by the other two) | all | `CLAUDE.md`, `.claude/`, `app/config.py`, `app/models.py`, `app/db.py`, `app/llm.py`, `pyproject.toml`, `requirements.txt` |

Owning an area means you decide its design and review changes to it. Anyone can open a PR anywhere.

## The loop for every task

1. **Pick or open an issue** on GitHub. One issue = one task, small enough to finish in a day or two. Assign yourself.
2. **Branch from fresh `main`:**
   ```bash
   git switch main
   git pull
   git switch -c feat/safety-gate-rules
   ```
   Branch name: `<type>/<short-description>`. Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`, `prompt`.
3. **Work in small commits** using Conventional Commits:
   ```
   feat(safety): add red-flag keyword rules
   fix(extraction): handle unicode dashes in dose ranges
   test(schedule): cover every-6-hours as-needed case
   ```
   Scope is the folder under `app/` (or `ui`, `eval`, `prompts`, `repo`).
4. **Before pushing:** `pytest` passes and pre-commit ran (it runs automatically on commit).
5. **Push and open a pull request:**
   ```bash
   git push -u origin feat/safety-gate-rules
   gh pr create --fill
   ```
   Fill in the template checklist. Link the issue with `Closes #N`.
6. **Review:** one approval from one of the other two teammates, plus green CI. The area owner reviews when the PR touches their area.
7. **Merge with "Squash and merge"** and delete the branch. The squash title must follow the commit format.

## Pull request rules

- Small: aim for under ~400 changed lines. Split bigger work into a stack of PRs.
- One task per PR. No unrelated cleanups.
- Review within one working day. If you are blocked waiting, say so in the team chat.
- The author merges, after approval.
- Changes to shared files (table above) need approval from **both** other teammates.

## Review checklist (for the reviewer)

- Does it do what the issue says, and only that?
- Is there a test that would fail without this change?
- Safety-relevant change? The `aftercare-safety-review` table is in the PR and every row is PASS or N/A.
- Any patient text in logs, secrets, model IDs outside `config.py`, or SDK calls outside `llm.py`?
- Would a teammate understand this code in a month?

## Working with Claude Code

- Claude Code reads `CLAUDE.md` and the skills in `.claude/skills/` automatically. Everyone gets the same rules.
- Treat Claude's output like a teammate's PR: read the diff before you commit it. You are the author of record.
- Ask Claude for a plan before code on anything bigger than a small fix.
- Personal preferences go in your own `~/.claude/CLAUDE.md`, not the shared one.
- Do not install a new Claude Code plugin for the project without team agreement. Plugins can run commands on your machine.

## Changing the rules or a decision

The rules themselves (this file, `CLAUDE.md`, `.claude/`, `pyproject.toml`, `.pre-commit-config.yaml`, `.github/`) change only by a pull request approved by both other teammates.

Project decisions live in [`docs/decisions/`](docs/decisions/README.md). To change one, add a new ADR that supersedes the old one (never rewrite an accepted ADR), and update `CLAUDE.md` in the same PR.
