# Assignment 3 deck: where each decision lives

The Assignment 3 deck ("RAG: What AfterCare Retrieves", "Memory: What AfterCare Remembers", the end-to-end flow, and the data and risk slide) is adopted as the design of this project. The one change: **input is the digital PDF only for now.** Photo upload, OCR, and voice input are not built (ADR-0030).

HW2 (the v4 prompt) was built and tested with ChatGPT. This project uses Claude and prompt v7, and re-tests on our own eval suite.

## Knowledge sources

| Deck source | Where it lives |
|---|---|
| Patient's discharge paperwork, per-patient index | Chunked by section, one chunk per medicine row (`CLAUDE.md` section 15); per-patient filter in code (ADR-0028) |
| RxNorm (brand and generic names) | Enrichment, at upload and when a medicine is named |
| openFDA labels, purpose and warnings only, never dosing | ADR-0027 |
| MedlinePlus health topics for terms in the paperwork | ADR-0023; needs prompt v8 and a `[T#]` tag first |
| Abbreviation glossary, always in context | `data/abbreviations.yaml` (ADR-0030); code also normalizes abbreviations at upload |

## Retrieval

| Deck decision | Where it lives |
|---|---|
| Hybrid search (keywords plus embeddings) over a per-patient FAISS index, top 4, score threshold | ADR-0028 (supersedes ADR-0012) |
| "That is not in your paperwork" below the threshold | ADR-0028 |
| External sources only when the paperwork has a gap | ADR-0028 |
| Paperwork always wins; two kinds of citation | ADR-0030 |
| No retrieval and no memory on the urgent path | ADR-0005, ADR-0030 |

## Memory

| Deck decision | Where it lives |
|---|---|
| Short-term memory: last 10 turns plus a summary, focus medicine, pending question, who is speaking | ADR-0029 |
| Long-term memory as structured records: confirmed list, symptom log, taken/missed log, visit date, saved questions, discharge date | ADR-0029 (supersedes ADR-0024) |
| Lifecycle: write only confirmed facts, store encrypted, retrieve by task and recency, replace and flag conflicts, delete 30 days after discharge | ADR-0029 |
| Ignore memory on urgent symptoms, archive on a new upload, paperwork wins on conflict | ADR-0029 |

## Use cases

| Deck use case | Where it lives |
|---|---|
| 1 Summary | MVP |
| 2 Medicine schedule | MVP, built by code (ADR-0006) |
| 3 Medicine question | MVP |
| 4 Diet question, from the paperwork's diet lines and the confirmed medicine list | ADR-0030 |
| 5 Visit prep, from the paperwork, symptom log, and dose log | ADR-0030; needs ADR-0029 |

The diet agent with food–medicine interaction checks and the physiotherapy agent stay later (ADR-0025).

## Data, privacy, and risks

| Deck decision | Where it lives |
|---|---|
| Chat transcripts session-only; audio never stored | ADR-0031 (so `QALog` stores no patient text by default) |
| 30-day retention; weekly refresh of public references | ADR-0031 |
| No ad or analytics trackers; send the model only what it needs | ADR-0031 |
| Per-patient namespace enforced in code; two-patient leak test | ADR-0028, ADR-0031 |
| Hidden instructions in paperwork (HW2 case C8c) | ADR-0031; also the validators and prompt rule 7 |
| MedlinePlus and openFDA licensing | ADR-0031 |
| Caregiver access only if invited | ADR-0032: the patient invites the aide by email, and the aide gets a limited role |

## Eval cases from the deck

Synthetic Patient 3 and eval cases `P3-C7` and `P3-L1` reproduce HW2's contradictory-paperwork case ("Prinivil" in the hospital course, "lisinopril discontinued", and no lisinopril on the discharge list). The deck's own with-RAG and with-memory example outputs are design targets that were never run; once retrieval and memory are built, run them against this eval set.

## Prompt: what v4 had that v7 does not

HW2's v4 prompt had three rules that v7 does not state: flag when the paperwork contradicts itself, flag a time with no exact date, and flag an unexplained abbreviation or unit. The `P3` cases test the first. If they fail, the fix is prompt v8 through the `aftercare-prompt-change` skill, not an edit to v7.
