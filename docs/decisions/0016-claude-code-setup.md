# ADR-0016: Coding principles in `CLAUDE.md`; two official Claude Code plugins

- **Status:** Accepted
- **Date:** 2026-10-31
- **Deciders:** team
- **Supersedes:** none

## Context

All three teammates use Claude Code and should get the same behavior from it. Every extra plugin is one more thing to keep in sync and can run commands on our machines.

## Decision

- The four coding principles (think first, keep it simple, surgical changes, prove it's done) are written directly into `CLAUDE.md` section 16, instead of installing the Karpathy-guidelines plugin, which is not in Anthropic's official marketplace.
- `.claude/settings.json` enables two plugins from Anthropic's official marketplace: **code-review** and **superpowers**. It also denies reading `.env` and `data/real/`, and blocks force-pushes.
- Two project skills in `.claude/skills/`: `aftercare-safety-review` and `aftercare-prompt-change`. Python style and git workflow live in `CLAUDE.md` and `CONTRIBUTING.md`, which are always loaded.

## Alternatives considered

- **Four skills, including style and git workflow** — duplicated rules already in always-loaded files.
- **More plugins** (memory, design, large skill collections) — no benefit for a Python backend, more to sync.

## Consequences

- One source of truth for rules, versioned with the code.
- Plugins may need manual install (see `TEAM_SETUP.md`). Adding a plugin needs team agreement.
