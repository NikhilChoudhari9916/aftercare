# Workflow implemented for Assignment 4

Verified locally on `vinayarekha`, 2026-11-21. These changes are not claimed to be merged into main.

```mermaid
flowchart TD
    U[Sign in: owner or aide] --> P[Owner uploads digital PDF]
    P --> X[Upload LangGraph: ingest, extract, quote check, normalize]
    X -->|bad quote, retry once| X
    X --> C[Owner confirms, edits or removes each item]
    C -->|unchanged| I[Index original page passages]
    C -->|edited| E[Retain original / extracted / edited comparison]
    I --> S[Code builds summary, schedule and calendar]
    U --> Q[Ask page sends question to authenticated API]
    Q --> G{Fixed rules and three classifier readings}
    G -->|Tier 1| N[Exact fixed 911 response]
    G -->|Tier 2 or 3| R{Edits need review?}
    R -->|yes| E
    R -->|no| M{Resolve medicine reference from recent user context}
    M -->|ambiguous medicine pronoun| A[Fixed clarification]
    M -->|two recognized list questions| L[Read complete original medicine rows]
    L -->|complete verified table| T[Fixed cited list answer; no inferred purpose]
    L -->|unrecognized or incomplete| O
    M -->|other questions| O[Model router: medicine, schedule or out of scope]
    O -->|schedule / out of scope| F[Fixed response]
    O -->|medicine or routing error| B[Answer agent chooses tool call or draft]
    B --> D[Read-only tools with typed schemas and patient scope]
    D --> B
    B --> V{Draft checks and support review}
    V -->|fail once| B
    V -->|pass| K[Server releases verified original excerpts only]
    V -->|fail twice or limit| H[Fixed safe fallback]
    T --> Z[UI answer with page citations]
    K --> Z
    A --> Z
    F --> Z
    H --> Z
    N --> Z
    E --> Z
    Z --> Y[Metadata-only audit; eligible turns in session memory]
```

## Execution and context

The safety gate is fixed code and precedes both direct lookups and the model agent. Any Tier 2
reply retains a care-team instruction. Neither an agent nor a tool can downgrade the gate.

The common questions “Which medicine is new?” and “What is each of my medicines for?” call
`read_original_medicine_entries` through the same typed ToolRegistry execution mechanism.
The tool reads the current patient's original DocumentPage records, keeps complete table entries,
and checks coverage against explicit status markers. An edited profile cannot supply evidence.
A purpose is quoted only when a positive, explicit purpose phrase is present in that entry;
otherwise the answer says it could not verify one. Partial or unknown layouts use the regular path.

Other document questions use a ReAct-style loop: the model chooses an allowed read-only tool,
code validates its arguments and executes it, and the next model turn receives its result.
The agent receives `get_confirmed_medicines` and `search_patient_document`; external label/name
services are not answer sources. `get_schedule` remains a separate registry utility.

| Component | Context passed | Authority |
|---|---|---|
| Prompt | Confirmed profile, original question, typed tool descriptions | Instructions, not clinical evidence |
| RAG | Current-patient and current-document original passages, with D IDs and pages | Original paper text |
| Session memory | Recent user questions and code-resolved medicine identity | Reference resolution only |
| Tools | Server-bound patient ID, validated arguments; typed results | Read-only execution |
| Final response | Original excerpts or code templates tied to original rows | Model interpretations cannot be released |
| Audit | IDs, tiers, tool names, counts and checks | No patient question/answer text |

Limits remain six agent tool calls, one answer retry and a 30-second check between steps.
An in-flight provider call is not forcibly interrupted. See `challenges-and-limits.md`.
