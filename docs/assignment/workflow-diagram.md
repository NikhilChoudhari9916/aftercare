# The question workflow as built

This is the graph in `app/agents/question_graph.py`, step for step. Red = fixed safety code,
green = uses a model, gray = plain code.

```mermaid
flowchart TD
    q["Patient or aide asks a question<br/>POST /patients/{id}/ask"] --> gate{"safety_gate<br/>rules + Haiku x3, most severe wins"}
    gate -->|"Tier 1"| em["emergency<br/>fixed 911 text, no model"]
    gate -->|"Tier 2 or 3"| ctx["load_context<br/>short-term memory"]
    ctx --> rt{"router (Haiku)<br/>route + rewrite 'it'"}
    rt -->|"SCHEDULE"| sch["fixed reply<br/>see the Schedule page"]
    rt -->|"OUT_OF_SCOPE"| oos["fixed reply<br/>what AfterCare can help with"]
    rt -->|"MEDICINE (and every Tier 2)"| ag["agent (Sonnet, prompt v7)"]
    ag -->|"asks for a tool"| tl["tools<br/>4 tools, max 6 calls"]
    tl --> ag
    ag -->|"limit or model error"| fb["fallback<br/>ask your pharmacist"]
    tl -->|"over 6 calls"| fb
    ag -->|"answer"| val{"validators<br/>citations, doses, advice, length"}
    val -->|"pass"| fin["finalize<br/>strip analysis, parse follow-ups"]
    val -->|"fail once"| rty["retry with the reasons"]
    rty --> ag
    val -->|"fail twice"| fb
    em --> out["Answer card on the Ask page"]
    sch --> out
    oos --> out
    fin --> out
    fb --> out

    classDef safe fill:#faece7,stroke:#993c1d,color:#4a1b0c
    classDef ai fill:#e1f5ee,stroke:#0f6e56,color:#04342c
    classDef code fill:#f1efe8,stroke:#5f5e5a,color:#2c2c2a
    class gate,em,val,fb safe
    class rt,ag ai
    class q,ctx,sch,oos,tl,rty,fin,out code
```

## Step by step

| Step | What happens | Kind of decision |
|---|---|---|
| safety_gate | Keyword rules and the patient's own warning signs, plus a small model run 3 times; the most severe tier wins. Tier 1 stops here | Fixed code: whether to continue |
| load_context | Starts a clean run; the endpoint already loaded the last turns and the medicine in focus | Plain code |
| router | A small model picks one of three routes and rewrites the question using the recent turns | Model: where to go (a response or an action) |
| fixed replies | Schedule and out-of-scope questions get a code-written reply | Response, no agent |
| agent and tools | ReAct: the model reasons, asks for a tool, we run it and hand back the result, repeat | Model: act (call a tool) or respond |
| validators | Cited IDs were retrieved; doses, times and names match; no advice or diagnosis; short and plain; care-team line on Tier 2 | Fixed code: may the answer be shown |
| retry and fallback | One retry with the reasons; then a fixed safe message | Fixed code |

## Context flow

- **Prompt:** the confirmed profile written as text (`app/qa/profile_text.py`) fills `{patient_profile}`.
- **RAG:** the agent calls `search_patient_document`; the retriever filters by the patient in code.
- **Tools:** drug labels (openFDA) and names (RxNorm) come back as tool results; labels get `L#` IDs.
- **Memory:** short-term memory feeds the router; nothing is saved to long-term memory yet.

## Use cases it serves

| Use case | Path |
|---|---|
| Cited medicine, diet or follow-up question | gate -> router MEDICINE -> agent with tools -> validators |
| A symptom | gate Tier 1: fixed 911 text. Tier 2: agent, and the answer must lead with the care team |
| Schedule question | router SCHEDULE -> pointer to the Schedule page (the schedule is built by code) |
| Upload to summary | the separate upload graph (`app/agents/upload_graph.py`) |
