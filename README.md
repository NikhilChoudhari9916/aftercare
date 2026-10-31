# AfterCare

A Python web app that helps adults (18+) and their caregivers understand their own hospital discharge papers during the first 30 days at home. It **explains** what the papers, official FDA drug labels, and MedlinePlus plain-language definitions say, with short cited answers. It never diagnoses or tells anyone to change a medicine.

Graduate course project (INFO 7375, Building AI Applications). **Synthetic data only. Not medical advice.**

## Status

Rules, architecture, and team setup are in place. Code starts with build step 1 (`KICKOFF_PROMPT.md`).

## Start here

| File | What it is |
|------|------------|
| [`TEAM_SETUP.md`](TEAM_SETUP.md) | Get your machine ready (about 15 minutes) |
| [`CLAUDE.md`](CLAUDE.md) | Scope, architecture, safety design, storage, coding rules (sections 1–19) |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Branches, commits, pull requests, reviews, who owns what |
| [`docs/architecture.md`](docs/architecture.md) | The two pipelines in detail |
| [`docs/decisions/`](docs/decisions/README.md) | Every project decision, why it was made, and its history (ADRs) |
| [`KICKOFF_PROMPT.md`](KICKOFF_PROMPT.md) | The first message to give Claude Code for build step 1 |

## Architecture at a glance

```mermaid
flowchart TD
    user["Patient or aide"] --> ui["NiceGUI web app<br/>calls FastAPI over HTTP"]
    ui <-->|"sign-in, identity only"| google["Google"]
    ui --> upload
    ui --> qa

    subgraph upload["Upload pipeline (runs once)"]
        direction TB
        u1["Upload and text check"] --> u2["AI extraction<br/>with source quotes"]
        u2 --> u3["Quote check and cleanup"]
        u3 --> u4["Patient confirms"]
        u4 --> u5["Profile saved<br/>versioned, per patient"]
        u5 --> u6["Enrich and index<br/>RxNorm, FDA, MedlinePlus, BM25"]
    end

    subgraph qa["Question pipeline (each question)"]
        direction TB
        q1["Safety gate<br/>Tier 1 gets fixed 911 text"] --> q2["Load memory<br/>profile, preferences, session chat"]
        q2 --> q3["Orchestrator agent"]
        q3 --> q4["Medicine agent"]
        q3 --> q5["Schedule agent"]
        q3 --> q6["Summary agent"]
        q4 --> q7["Validators<br/>citations, doses, no advice"]
        q5 --> q7
        q6 --> q7
        q7 --> q8["Short cited answer<br/>with follow-up buttons"]
    end

    upload --> files[("PDF files<br/>storage/patients/")]
    upload --> db[("SQLite<br/>users, profile, chunks, logs")]
    qa --> db
    upload --> ext["External APIs<br/>Claude, FDA, MedlinePlus"]
    qa --> ext
    db --> summary["Summary screen"]
    db --> sched["Schedule and .ics download"]
    sched -.-> gcal["Google Calendar sync<br/>later, optional"]

    classDef safe fill:#faece7,stroke:#993c1d,color:#4a1b0c
    classDef ai fill:#e1f5ee,stroke:#0f6e56,color:#04342c
    classDef code fill:#f1efe8,stroke:#5f5e5a,color:#2c2c2a
    classDef later fill:#ffffff,stroke:#888780,color:#444441,stroke-dasharray:4 4
    class q1,q7 safe
    class u2,q3,q4,q5,q6,summary ai
    class user,ui,google,u1,u3,u4,u5,u6,q2,q8,files,db,ext,sched code
    class gcal later
```

Red = fixed safety code. Green = uses AI. Gray = plain code or data. Dashed = planned later.

Agents decide *how* to answer; fixed code decides *whether* safety checks run. Diet and physiotherapy agents will plug in under the orchestrator later.

Stack: Python 3.12, FastAPI, NiceGUI, Google sign-in, PyMuPDF, pdfplumber, Anthropic SDK (Claude), Pydantic, SQLite + SQLModel, rank_bm25, RxNorm, openFDA, MedlinePlus, icalendar, textstat, pytest, ruff.
