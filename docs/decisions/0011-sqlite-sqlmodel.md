# ADR-0011: SQLite + SQLModel for the MVP database

- **Status:** Accepted
- **Date:** 2026-10 (recorded 2026-10-31)
- **Deciders:** team
- **Supersedes:** none

## Context

The MVP needs a small relational store (profiles, versions, chunks, logs) that every teammate can run with zero setup.

## Decision

Use **SQLite** with **SQLModel** (tables that are also Pydantic models). Every patient-data table has `patient_id`, and every query filters by it first. Tables are listed in `CLAUDE.md` section 9.

## Alternatives considered

- **Postgres now** — production-grade, but needs a server on every laptop and in CI.

## Consequences

- No database server to install; the database is a file (gitignored).
- Moving to Postgres later is a connection-string change plus a migration.
- SQLite isn't suited to many concurrent users — fine for the MVP.
