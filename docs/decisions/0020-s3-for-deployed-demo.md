# ADR-0020: S3 storage only for the final demo; local storage for all development

- **Status:** Accepted (deferred until the demo phase)
- **Date:** 2026-10-31
- **Deciders:** team
- **Supersedes:** none

## Context

A live demo link strengthens the portfolio, but most hosting platforms wipe the local disk on redeploy, so local storage (ADR-0013) would lose uploaded PDFs in a hosted demo. During development, teammates and CI should not need AWS accounts or keys.

## Decision

- **All development, testing, and CI use local storage only.** Nothing S3-related is built until the last phase.
- At the end, if the team deploys a demo, add an **AWS S3** backend to `app/storage.py`, chosen by `STORAGE_BACKEND=local|s3` in `.env`. Local stays the default.
- S3 setup then: a private bucket with Block Public Access on, server-side encryption, one prefix per patient, and an IAM user limited to that bucket. AWS keys live only in `.env` and the host's secret settings, never in git (the repo is public, ADR-0017).

## Alternatives considered

- **S3 from the start** — real cloud experience early, but credentials and setup for everyone during development.
- **No deployed demo** — local storage is enough for the course.

## Consequences

- Zero cloud setup during development.
- Adds `boto3` and an AWS account only in the demo phase, with a new dependency approval at that point.
