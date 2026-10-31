# ADR-0018: Claude Sonnet 5.5 for main work, Haiku 5.5 for fast checks, Opus when needed

- **Status:** Accepted
- **Date:** 2026-10-31
- **Deciders:** team
- **Supersedes:** none

## Context

Extraction, summaries, and answers need careful, grounded output. The safety classifier runs 3 times per question and routing runs on every question, so they need speed and low cost. Some tasks may turn out to need a stronger model.

## Decision

- Main model (extraction, summary, medication/schedule/summary agents, orchestrator): **Claude Sonnet 5.5** (`claude-sonnet-5-5`).
- Fast model (safety classifier, routing): **Claude Haiku 5.5** (`claude-haiku-5-5`).
- **Claude Opus 5.5** (`claude-opus-5-5`) is allowed for a specific task only when the eval suite shows Sonnet falling short there (for example, extraction missing items). Switch one task at a time and record the eval before/after in `prompts/PROMPT_LOG.md`.
- Model IDs are read from `.env` into `app/config.py` and nowhere else. Every model change re-runs the eval suite (ADR-0014).

## Alternatives considered

- **Opus for everything** — highest quality, but slower and more expensive; most calls don't need it.

## Consequences

- Cost and speed stay low by default, with a clear, evidence-based path to a stronger model.
- Run the eval suite with these IDs and record the baseline results in `prompts/PROMPT_LOG.md`.
