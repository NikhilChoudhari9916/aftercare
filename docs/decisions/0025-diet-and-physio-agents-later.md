# ADR-0025: Diet and physiotherapy agents are planned as later specialists

- **Status:** Accepted
- **Date:** 2026-10-31
- **Deciders:** team
- **Supersedes:** none

## Context

After the MVP, patients will want help with what to eat and with physical recovery. These are riskier than explaining a medicine list: food can interact with medicines, and exercise advice can cause harm.

## Decision

- A **diet agent** and a **physiotherapy agent** are planned as additional specialists under the orchestrator (ADR-0008). They are **not built in the MVP**.
- Each must follow the same rules as the existing agents: read-only tools, cited sources, no diagnosis, no start/stop/change advice, and the same safety gate and validators in front and behind (ADR-0004).
- Each needs its **own ADR before work starts**, covering its sources (for example, the patient's own diet and activity instructions and official guidance), its extra safety rules (for example, food-medicine interaction checks, activity limits from the papers), and new eval cases.

## Consequences

- The orchestrator is designed so adding a specialist means adding one agent and its tools, with no pipeline redesign.
- Nothing about diet or physio is built, mocked, or promised in the MVP UI.
