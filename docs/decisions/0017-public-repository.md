# ADR-0017: Public GitHub repository from the start

- **Status:** Accepted
- **Date:** 2026-10-31
- **Deciders:** team
- **Supersedes:** none

## Context

The team wants to show this project on resumes. A private repository is invisible to recruiters.

## Decision

Host AfterCare as a **public** GitHub repository from the first commit.

## Consequences

- Anyone can read every commit, so secrets must never be committed, even once. Enforced by `.gitignore`, the gitleaks pre-commit hook, and review. API keys live only in each person's `.env`.
- Only synthetic data, ever. The README states "synthetic data only, not medical advice".
- Before creating the repo: confirm the course (INFO 7375) allows public code, and add a `LICENSE` file.
- The team's PR history, reviews, and CI become part of the portfolio.
