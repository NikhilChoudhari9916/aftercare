# Sources and attribution for Assignment 4

- Supplied course document: `Project Guidelines_AIApps.pdf`, pages 15–16 (Assignment 4 and its
  six-point rubric); requirements also pasted by the student in chat.
- Synthetic example: `data/synthetic/patient1_discharge_summary.pdf`. Every displayed medicine
  fact is drawn from this sample, not a real patient or external drug reference.
- Implementation: this repository's upload/question graphs, typed ToolRegistry, original-text
  retriever, session-reference resolver, deterministic summary/schedule and NiceGUI pages.
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) and
  [n8n flow logic](https://docs.n8n.io/build/flow-logic.md), reviewed 2026-11-21 for the platform
  comparison. n8n was assessed on paper, not implemented or benchmarked.
- [CrewAI Flows](https://docs.crewai.com/en/concepts/flows), reviewed to correct the older
  overly broad statement about agent-controlled routing; not a project implementation.
- [Anthropic model pricing](https://platform.claude.com/docs/en/about-claude/pricing), reviewed
  2026-11-21. Live execution used Claude Sonnet 5.5 and Haiku 5.5 via the existing application
  wrapper. Cost is estimated from reported usage, with no cache discount assumed.
- Development and documentation assistance: Codex. The student should review the code, tests,
  evidence and slides and follow the course's tool-disclosure rules. Git author/coauthor
  metadata is separate from academic attribution; no commit or PR is created by this task.

No live FDA, RxNorm or MedlinePlus source was used for these answers. Older design documents
mention those services; the current document-only source policy supersedes that answer behavior.
