# Two orchestration platforms evaluated

Documentation assessment: 2026-11-21. LangGraph is implemented and tested. n8n was assessed from
its official documentation; this project does not claim to have benchmarked or deployed it.

| Criterion | LangGraph | n8n |
|---|---|---|
| Sequencing and branches | State, nodes and edges in Python | IF/Switch, merge and loop nodes |
| Safety ownership | Our code wires gate, retries and release checks | Equivalent controls would need explicit workflow configuration and tests |
| Fit with this repository | Runs in the existing Python backend; nodes are directly testable functions | Would require adapting the existing Python functions to a separate workflow runtime |
| Modular tools | Existing typed Python ToolRegistry | Nodes/sub-workflows and service calls |
| Evidence here | Two implemented graphs and API/integration tests | Documentation-based assessment only |

**Selected: LangGraph.** The project already uses FastAPI, Pydantic and Python tests. Keeping the
orchestration beside these functions makes the conditional decisions and access boundaries easy
to inspect. This is a project-fit judgment, not a claim that n8n cannot enforce safety.

The earlier plain-SDK design is historical context, not counted as a second orchestration platform.
CrewAI Flows also supports structured control flow; the earlier description that it necessarily
lets agents choose every path was too broad.

Sources: [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview),
[n8n flow logic](https://docs.n8n.io/build/flow-logic.md),
[CrewAI Flows](https://docs.crewai.com/en/concepts/flows).
Implementation evidence: `app/agents/upload_graph.py`, `app/agents/question_graph.py`.
