# Assignment 4 submission package

Based on the supplied guidelines, pages 15–16, and the Assignment 4 requirements pasted in chat.
Verified locally on `vinayarekha`; no commit, push, main merge or course submission is implied.

| Rubric criterion (1 point each) | Implementation / explanation | Evidence |
|---|---|---|
| Workflow design | Upload and question LangGraphs; confirmation, emergency, ambiguity, tool, retry and fallback branches | workflow-diagram.md; app/agents/ |
| Tool identification and usage | Confirmed-profile search plus direct original-row lookup; patient scope is server-bound | workflow-diagram.md; app/tools/; live-evidence.json |
| Agent / ReAct logic | General questions choose act/tool vs draft; fixed code owns the gate and release | workflow-diagram.md; graph tests; live alias/memory/diet scenarios |
| MCP-style architecture | Tool names/descriptions, Pydantic input schemas, typed results; reasoning separated from execution | platform and workflow slides; ToolRegistry |
| Platform implementation | LangGraph implemented; n8n evaluated as the second option | platform-comparison.md; both graph modules |
| UI design and usability | Upload/Review/Summary, cited Ask, Schedule/calendar | use-case-map.md; live HTTP checks and browser smoke test |

## Results actually obtained

- Complete offline suite: **1,177 passed**, five existing SWIG deprecation warnings.
- Fresh live extraction from the real synthetic PDF: **24 items** (6 medicines, 3 follow-ups,
  9 warning signs, 3 diet/care instructions and 3 contacts).
- Seven live questions: five document questions answered, one emergency handled and one
  out-of-scope request declined. The alias→“it” sequence was executed, not a design target.
- Summary, Schedule and calendar endpoints returned HTTP 200 with content.
- Browser: development sign-in, Summary, Schedule, and both reported Ask questions verified.
  The browser run used a scripted classifier to avoid further costs; live-model API evidence
  is recorded separately.
- Live sample: **32 calls**, estimated **$0.089158**, within the **$0.75** reserved-cost cap.

This evidence supports the six rubric areas; grading remains the instructor's assessment.
It does not establish clinical correctness or replace the later external-user/security work.

## Files

- `workflow-diagram.md` — current diagram and context flow.
- `platform-comparison.md` — two-platform evaluation and selection rationale.
- `use-case-map.md` — three core scenarios tied to code and executed checks.
- `challenges-and-limits.md` — observed problems, fixes and honest boundaries.
- `demo-runbook.md` — local demo sequence and reproducible offline commands.
- `live-evidence.json` — measured synthetic outputs and token usage.
- `sources.md` — data, framework, model and development-tool references.
- Final slides are in `output/assignment4/` at the repository root.

## Slide coverage

The five-slide deck follows the supplied Assignment 2 reference: original cover artwork,
team names, Cambria/Calibri fonts, dark green headings, orange section labels and mint tables.
The reference file was left unchanged. The current deck is `output/assignment4/AfterCare_Assignment4.pptx`.
An easy-to-find copy is also in Downloads as `AfterCare_Assignment4_Tools_Workflow.pptx`.

| Rubric area | Slide |
|---|---|
| End-to-end workflow and conditional branches | 2 |
| Tool identification and use | 3 |
| Agent action vs. response / ReAct-style loop | 3 |
| MCP-style interfaces and context passing | 3 |
| Two-platform comparison and implemented selection | 4 |
| UI supporting three core journeys and executed evidence | 2 and 5 |

Slides 4–5 describe observed challenges and remaining limitations. Speaker notes contain
supporting implementation and evidence details. This is a local preparation package, not
a course submission or a guarantee of a particular grade.
