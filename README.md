# SprintPilot AI

**AI Agile Control Tower + Sprint Decision Simulator.** A read-only Scrum/Kanban assistant that turns a Jira backlog into a sprint plan you can defend in front of your team: predictive sizing, task decomposition, smart assignment, dependency-aware sequencing, deadline-aware prioritization, ready-to-start notifications, sprint health scoring, and a what-if simulator that recommends the safest scope.

> This MVP uses Jira's REST API in **read-only** mode. It never writes, updates, or transitions issues. If the Jira API is unreachable, the app falls back to local sample data so the demo never breaks.

## What makes SprintPilot AI different

Most agile tools tell you *that* the sprint is risky. SprintPilot AI tells you **what to do about it**:

- **Which task to remove** (Remove Highest Risk scenario)
- **Which task to split** (Split Large Risky Task scenario)
- **Who to notify and when** (Ready-to-Start notifications when a predecessor is marked Done)
- **Which task to start first** (recommended_first_action surfaced on every sequence)
- **Why each estimate, assignment, and order makes sense** (every AI output has a one-sentence rationale)

## Main features

1. **Predictive Planning** — similarity-based (kNN-style) sizing against the last 10 sprints. Returns predicted size, confidence (1–100), risk level, carry-over risk, "why this estimate?" reasoning, and the 3 most similar past issues as evidence.
2. **Task Decomposition** — splits an issue into Analysis / DB / Backend / Frontend / Test subtasks based on labels, components, and acceptance-criteria signals.
3. **Smart Assignment** — picks an assignee per subtask using skill match + remaining capacity, surfaces an overload risk badge.
4. **Dependency-Aware + Deadline-Aware Sequencing** — orders subtasks so QA never starts before development, but earlier deadlines and critical-path position tie-break inside the same technical stage.
5. **OpenAI Priority Advisor** — when `OPENAI_API_KEY` is set, the sequencer asks OpenAI for a structured dependency-aware order. If the key is missing or the call fails, the deterministic engine takes over. The UI surfaces a "used_openai: true/false" badge.
6. **Ready-to-Start Notification System** — marking a subtask Done propagates through the dependency graph: successor tasks become Ready, and the assigned team member gets an in-app notification with a copyable Teams/Slack message preview.
7. **Sprint Review Dashboard** — sprint health score (1–100), Healthy / Risky / Overcommitted verdict, capacity utilization per team member, top risks, recommended actions, an AI-generated review summary, and a printable **Sprint Decision Receipt**.
8. **What-if Sprint Simulator** — three side-by-side scenarios: *Keep All Tasks*, *Remove Highest Risk Task*, *Split Large Risky Task*. Each card shows sprint health, capacity utilization, carry-over risk, the trade-off and a recommendation. One scenario is marked **Recommended**.

## Stack

- **Backend** — FastAPI · Pydantic · Python 3.10+
- **Frontend** — React 18 + Vite + JavaScript (no TypeScript) + Ant Design 6
- **Storage** — In-memory only (no PostgreSQL, no Redis, no SQLite for state). Sprint state is lost on backend restart. This is intentional for the hackathon MVP.
- **Integrations**
  - **Jira REST API (read-only)** — uses the same auth pattern (PAT bearer or Atlassian Cloud basic) as the existing `jira_create_tasks_test.py` script.
  - **OpenAI** — optional. Used for dependency-aware sequencing only. Deterministic fallback always available.

## How to run locally

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
# Copy and edit the env file:
cp ../.env.example ../.env
# Fill in JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN (read-only PAT works).
# OPENAI_API_KEY is optional.
uvicorn app.main:app --reload --port 8000
```

Backend at `http://localhost:8000`. OpenAPI docs at `http://localhost:8000/docs`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend at `http://localhost:5173`.

### Without Jira credentials

The app still runs. `/api/backlog` returns the local fallback backlog (6 POS-2401…POS-2456 issues) and `/api/planning` uses the local fallback historical dataset (12 issues with varied sizes). The UI shows a yellow "fallback" pill in the header.

### Without an OpenAI key

The app still runs. The sequencer uses the deterministic fallback (Analysis → DB → Backend → Frontend → Test with deadline tie-break). The UI shows "OpenAI: fallback" in the header and "Deterministic fallback" on every sequence card.

## Architecture

```
ifts-hackathon/
├── backend/
│   └── app/
│       ├── main.py                     FastAPI app + CORS + router wiring
│       ├── models.py                   Pydantic request/response models
│       ├── integrations/jira_client.py READ-ONLY Jira REST client (auth from .env)
│       ├── data/
│       │   ├── mock_team.py            6 team members (real Turkcell usernames)
│       │   ├── fallback_jira.py        6 POS issues (when Jira is unreachable)
│       │   └── fallback_history.py     12 historical issues for similarity search
│       ├── services/
│       │   ├── predictive_sizing.py    similarity scoring + size adjustment + confidence
│       │   ├── planning_engine.py
│       │   ├── decomposition_engine.py FE/BE/DB/Test/Analysis splits
│       │   ├── assignment_engine.py    skill+capacity match + overload risk
│       │   ├── sequencing_engine.py    dependency-aware order + critical path
│       │   ├── openai_priority_advisor.py OpenAI call with safe fallback
│       │   ├── task_state_store.py     in-memory singleton (sequences, status, notifications)
│       │   ├── notification_engine.py  Ready-to-Start / Dependency-Completed messages
│       │   ├── sprint_health_engine.py health score + decision receipt
│       │   ├── simulation_engine.py    3 scenarios + recommendation
│       │   └── data_provider.py        Jira-first + fallback resilience
│       └── routers/                    9 thin routers (one per UI action)
└── frontend/
    └── src/
        ├── App.jsx                     orchestrates all 8 sections
        ├── api/client.js               fetch wrapper
        └── components/                 12 cards / panels / status board
```

## Predictive sizing approach

Predictive sizing uses a lightweight similarity-based estimation algorithm inspired by **k-nearest neighbors**. It compares a selected Jira issue with the historical sprint dataset using:

- Label overlap (Jaccard) × 0.25
- Component overlap × 0.25
- Title + description keyword overlap × 0.25
- Dependency signal × 0.10
- Blocker history match × 0.10
- Priority match × 0.05

The top 3 historical issues are weighted-averaged by their actual sizes, then adjusted for missing acceptance criteria, dependencies, blockers, short descriptions, critical priority, and many labels/components. The result is normalized to the planning-poker set `[1, 2, 3, 5, 8, 13]`. Confidence (1–100) reflects average similarity, evidence count, and signal quality.

No model is trained. The algorithm is fully deterministic and explainable — every estimate ships with a "why this estimate?" sentence list and links to the historical issues that informed it.

## OpenAI Priority Advisor

When `OPENAI_API_KEY` is configured, SprintPilot AI sends the decomposed subtasks, the team roster, and the issue deadline to OpenAI and asks for a dependency-aware + deadline-aware execution order in structured JSON. The model is instructed to:

- Keep technical dependency order (QA never before development).
- Use deadlines as a tie-breaker, not an override.
- Mark tasks "Not Ready" when their predecessors are open.
- Respect assignee capacity and flag risky overload.
- Return only valid JSON.

The model defaults to `gpt-4o-mini` (overridable via `OPENAI_MODEL`). If the key is missing, the call fails, or the JSON cannot be parsed, the deterministic fallback runs and `used_openai` is set to `false` on the response. The app never crashes on OpenAI errors.

## Ready-to-Start Notifications

When a subtask is marked Done via the Sprint Task Status Board:

1. The successor tasks (downstream in the dependency graph) are looked up.
2. For each successor: if **all** of its predecessors are now Done, it transitions to **Ready** and a `ReadyToStart` notification is generated with the assignee's name, email, and Teams handle.
3. Other successors get a `DependencyCompleted` notification telling them the upstream task is finished.
4. The notification card surfaces a "Copy Teams/Slack message" button that pre-formats the text for paste.

No real email / Slack / Teams API is called. This is intentional — the MVP demonstrates the propagation logic without touching external collaboration tools.

## What-if Sprint Simulator

For a selected set of issues, the simulator re-runs predictive sizing + health scoring under three scopes:

1. **Keep All Tasks** — baseline.
2. **Remove Highest Risk Task** — drops the issue with the worst composite risk score (size + risk level + low confidence + blockers + carry-over).
3. **Split Large Risky Task** — shrinks the largest task to a 50% vertical slice and defers the remainder.

Each scenario reports sprint health, capacity utilization, predicted points, carry-over risk, deadline risk, critical-path risk, the trade-off, recommended actions, and "why this scenario?". One scenario is selected as **Recommended** by ranking on (health score, capacity ≤ 100%, lowest carry-over).

## Mock Jira data (fallback)

This MVP uses local mock Jira-style data as a fallback for the hackathon demo. The system is designed around read-only planning analysis and does not implement any write operation to Jira. The fallback dataset contains 6 backlog issues (POS-2401…POS-2456) with varied priority, deadline, blocker, and AC patterns so the demo highlights all engine behaviors even when Jira is unavailable.

## Known limitations

- Sprint state is in-memory; a backend restart wipes sequences and notifications.
- Historical similarity uses simple Jaccard + keyword overlap, not embeddings.
- The Jira mapping doesn't reconstruct `carried_over` from sprint changelog (always False from Jira; fallback dataset has the flag).
- No mobile responsive polish, no i18n, no dark mode.
- Manual Mark-as-Done propagation (not real-time Jira webhooks).

## Future work

- Embed-based similarity for richer historical matching.
- Webhook-driven status propagation from Jira.
- Persist sprint state across restarts (SQLite or single JSON file).
- Sprint capacity calibration from past velocity per assignee.
- Multi-sprint What-if simulator (next 2-3 sprints).

## License

Hackathon MVP. No license file included.
