# ADR-0002: Scope — explain only, adults, first 30 days, synthetic data

- **Status:** Accepted
- **Date:** 2026-10 (recorded 2026-10-31)
- **Deciders:** team
- **Supersedes:** none

## Context

Discharge papers are hard to read, and the first 30 days at home are when misunderstandings cause harm. An app that gives medical advice would be unsafe and out of reach for a course project.

## Decision

AfterCare **explains** a patient's own discharge papers and official FDA labels. It never diagnoses, prescribes, or tells anyone to start, stop, skip, double, or change a medicine; it points people to 911, the care team, or the pharmacist. Users are adults (18+) and their caregivers, during the first 30 days at home. Only synthetic data is used.

MVP features and deferred features are listed in `CLAUDE.md` section 2.

## Alternatives considered

- **Symptom checking or advice** — unsafe, and regulated.
- **Pediatric use** — different dosing and safety rules; deferred.
- **Real patient data** — would bring HIPAA and other privacy obligations a course project can't meet.

## Consequences

- Every answer must be grounded in the patient's papers or a label, with a citation.
- Many questions get "your papers don't answer this, ask your pharmacist" — by design.
- The test suite checks for forbidden advice patterns on every change.
