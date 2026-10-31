## What and why

<!-- One or two sentences. Link the issue: Closes #N -->

## How I tested it

<!-- Commands you ran and what you saw. -->

## Checklist

- [ ] Small and focused: one task, no unrelated changes
- [ ] Tests added or updated, and `pytest` passes locally
- [ ] `ruff check .` and `ruff format --check .` pass (pre-commit ran)
- [ ] No real patient data, no `.env`, no `storage/` or database files
- [ ] No patient text written to logs
- [ ] Only `app/llm.py` calls the Anthropic SDK; no model IDs outside `app/config.py`
- [ ] No new dependency, or the team agreed and it is pinned in `requirements.txt`
- [ ] Changes a project decision? New ADR in `docs/decisions/` and `CLAUDE.md` updated

**If this touches safety, agents, extraction, schedule, validators, or prompts:**

- [ ] Ran the `aftercare-safety-review` checklist and pasted the result below
- [ ] Prompt changes: new version file, eval before/after, entry in `prompts/PROMPT_LOG.md`
- [ ] Tier 1 (911) recall is still 100% on the eval set

## Reviewer

<!-- One of the other two teammates. -->
