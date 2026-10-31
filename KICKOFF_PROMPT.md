# First message to paste into Claude Code

One person does this, after everyone has finished `TEAM_SETUP.md`. Start on a branch: `git switch -c feat/foundation`. Then open Claude Code in the repo root and paste:

---

I'm starting the AfterCare project. Read `CLAUDE.md` fully. It has our scope, architecture, tech stack, safety rules, storage plan, coding rules, and build order. Also look at `prompts/`, `data/synthetic/`, `tests/eval/eval_cases.json`, `CONTRIBUTING.md`, and `pyproject.toml`.

Then do **build step 1 only**:
1. Create the folder structure from `CLAUDE.md` section 10 (empty `__init__.py` files where needed).
2. Add a `requirements.txt` with the MVP stack from section 3, with exact pinned versions you know are stable. Don't overwrite `pyproject.toml`; it already holds the ruff and pytest settings.
3. Add `app/config.py` (model IDs read from environment variables, plus limits and paths), `.env.example`, and update `README.md` with how to run things.
4. Add `app/storage.py` (local-folder version from section 15).
5. Create the SQLModel tables from section 9 and a script that loads the synthetic patient data.
6. Add a pytest smoke test that creates the database and loads Patient 1.

Before writing code, give me a short plan in plain language and wait for my OK. After each step, tell me how to run and check it. Follow the coding rules in section 16. When it's done, stop before committing so I can review the diff.
