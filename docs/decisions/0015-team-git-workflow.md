# ADR-0015: Protected `main`, reviewed PRs, pre-commit, and CI

- **Status:** Accepted
- **Date:** 2026-10-31
- **Deciders:** team
- **Supersedes:** none

## Context

Three people (and Claude Code) will change the same repo. Instructions alone get forgotten; tools don't forget.

## Decision

- `main` is protected: no direct pushes; changes arrive by pull request with one approval from another teammate and green CI. Squash-merge only.
- Branches `<type>/<short-description>`; Conventional Commit messages; PRs under about 400 changed lines; a shared PR template.
- **pre-commit** on every commit: ruff lint and format, gitleaks secret scan, private-key detection, large-file block, and no commits to `main`.
- **GitHub Actions CI** on every PR: ruff and pytest (unit tests only, no API key).
- Changes to shared rules need approval from both other teammates.

Details in `CONTRIBUTING.md` and `TEAM_SETUP.md`.

## Consequences

- `main` always works, and every change has a reviewer and a visible history (useful for a public portfolio repo).
- A little friction on every change; small PRs keep it low.
