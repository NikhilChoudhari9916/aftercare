# Assignment 4 use cases and evidence

The assignment slice implements three core use cases, as selected in ADR-0036.

| Use case | UI and API | Workflow and tools | Executed evidence |
|---|---|---|---|
| Upload, review and summary | Upload → Review → Summary; POST /documents; PUT /patients/{id}/profile; GET summary | Upload LangGraph, extraction, quote check, confirmation; deterministic summary | Fresh real-model extraction: 24 items, including 6 medicines and 3 follow-ups; summary returned HTTP 200; browser view checked |
| Cited document questions | Ask; POST /patients/{id}/ask | Gate → direct original-row lookup or router/ReAct tools → checks → original evidence | Both reported list questions answered; alias, pronoun follow-up and sodium scenarios answered; browser showed both list answers with page citations |
| Schedule and reminders | Schedule; GET schedule and schedule.ics | Code groups confirmed instructions; owner choices are separate from paper facts | Both endpoints returned HTTP 200 with content; planning/schedule screen checked in browser |

Additional branches executed: emergency → exact 911 response; out-of-scope → fixed boundary reply.
With no medicine identity, a dosing pronoun asks for clarification. With a preceding explicit
furosemide question, “it” resolved to furosemide and the answer still used original paper evidence.
An edit displays a retained comparison and prevents the disputed value entering instructions.

Diet and follow-up questions can use the ordinary document path; no separate diet specialist is
claimed. Visit-prep logs, long-term memory and external clinical enrichment remain outside this
Assignment 4 slice. Assignment 5's five external test users and later deployment are not claimed
complete by these checks.
