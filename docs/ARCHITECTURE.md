# SprintPilot AI Architecture

Short reference for navigating the codebase.

## Top-level flow

```
Jira REST (read-only)            User browser
        │                              │
        ▼                              ▼
backend/app/integrations/        frontend/src/api/client.js
    jira_client.py                       │
        │                                ▼
        ▼                       frontend/src/App.jsx (state holder)
backend/app/services/data_provider.py    │
   (Jira-first, fallback)                ▼
        │                       frontend/src/components/*
        ▼
backend/app/services/{predictive_sizing,
                       decomposition_engine,
                       assignment_engine,
                       sequencing_engine,
                       openai_priority_advisor,
                       sprint_health_engine,
                       simulation_engine}
        │
        ▼
backend/app/services/task_state_store.py  (in-memory singleton)
        │
        ▼
backend/app/routers/*  →  FastAPI HTTP layer
```

## Backend modules

- **`integrations/jira_client.py`** — Reuses the bearer-or-basic auth pattern from `jira_create_tasks_test.py`. Functions: `fetch_backlog(project_key)`, `fetch_historical(project_key, sprint_names)`, `get_issue(key)`, `ping()`. SSL verification is configurable via `JIRA_VERIFY_SSL` for corporate proxies.

- **`services/data_provider.py`** — Single source of truth for backlog + history. Tries Jira first, falls back to local data on any error. Returns `(issues, source: 'jira'|'fallback', reason)`.

- **`services/predictive_sizing.py`** — Implements similarity scoring (Jaccard over labels, components, keywords + dependency/blocker/priority signals), top-3 weighted average, fibonacci normalization, and confidence + carry-over risk scoring.

- **`services/decomposition_engine.py`** — Splits an issue into 3-5 subtasks based on signals: Analysis if AC missing, DB if data/schema keywords, Backend always, Frontend if UI signals, Test always. Sizes are proportional to parent's predicted size.

- **`services/assignment_engine.py`** — Scores team members for a subtask by role preference, skill overlap, remaining capacity, and current load ratio. Returns assignee + reason + overload risk.

- **`services/sequencing_engine.py`** — Builds dependency edges via technical stage order (Analysis → DB → Backend → Frontend → Test, Test depends on all dev stages). Computes critical path (longest SP-weighted chain). Priority score combines dependency-readiness, deadline urgency, critical path position, overload penalty. Defers to OpenAI when available.

- **`services/openai_priority_advisor.py`** — One function: `get_openai_sequence(subtasks, team, issue) -> dict | None`. Catches every exception. Returns None if `OPENAI_API_KEY` is missing or anything fails.

- **`services/task_state_store.py`** — Module-level singleton. Holds `sequences: dict[issue_key, TaskSequenceResult]`, `task_status: dict[task_id, TaskStatus]`, `notifications: list[TaskNotification]`. No persistence.

- **`services/notification_engine.py`** — Pure factory functions: `ready_to_start_notification(succ, completed_id)`, `dependency_completed_notification(...)`, `deadline_risk_notification(task)`.

- **`services/sprint_health_engine.py`** — Spec section 9.5 formula: starts at 100, deducts for overcommitment, high-risk issues, blockers, low confidence, carry-over, overloaded members, long critical path, near-deadline-not-ready tasks, test squeeze. Returns SprintHealth with verdict, capacity_by_member, decision_receipt.

- **`services/simulation_engine.py`** — Builds 3 scenarios, re-uses `compute_sprint_health` per scenario, picks recommended on (health desc, capacity ≤ 100, carry-over asc).

## Frontend layout

`App.jsx` is a single state-holding component. Each section is a presentational component that takes data + a callback prop:

| Component | Purpose | API call (via App) |
|---|---|---|
| Header | Status pills (Jira live/fallback, OpenAI ready/active/fallback) | `getStatus()` on mount |
| BacklogPanel | Issue grid + multi-select + Analyze button | `getBacklog()` on mount, `postPlanning(keys)` on Analyze |
| PlanningResults | Per-issue card: predicted SP, confidence, risk, similar issues, reasoning, Decompose button | `postDecompose(key)` on Decompose |
| TaskDecompositionPanel | Subtask grid with assignee + reason + overload + deadline + Sequence button | `postSequence(key)` on Sequence |
| TaskSequencePanel | Vertical Steps timeline + critical path tags + used_openai badge + recommended_first_action alert | (data only) |
| TaskStatusBoard | Per-subtask cards with Mark-as-Done buttons enabled only when status=Ready | `postCompleteTask(taskId)` |
| NotificationCenter | Ready-to-Start / Dependency-Completed message list + Copy button | `getNotifications()` after each completion, `postMarkRead(id)` |
| SprintReviewPanel | Statistic for health, Progress per member, Alerts for risks/actions, Decision Receipt | `postReview(keys)` on demand |
| SprintScenarioSimulator | 3 scenario cards side-by-side, Recommended highlighted | `postSimulate(keys)` on demand |

## State propagation on Mark-as-Done

```
User clicks Mark-as-Done on POS-XXX-BE (status=Ready)
        ▼
postCompleteTask('POS-XXX-BE')
        ▼
backend: store.set_status('POS-XXX-BE', 'Done')
        ▼
backend: for each successor in store.successors('POS-XXX-BE'):
            if store.all_predecessors_done(successor):
              status → Ready
              create ReadyToStart notification
            else:
              create DependencyCompleted notification
        ▼
backend response: { completed_task_id, newly_ready_tasks[], notifications[] }
        ▼
frontend: setSequences() — update statuses in-place
        ▼
frontend: getNotifications() — refresh full list
        ▼
frontend: AntApp message.success('N task(s) became Ready')
```

The store is the only mutable shared state. Routers don't mutate models; they call the store and re-read.

## CORS

`backend/app/main.py` allows `http://localhost:5173` and `http://127.0.0.1:5173`. Vite serves on `localhost:5173` by default. The frontend `client.js` uses `import.meta.env.VITE_API_BASE_URL` with a `http://localhost:8000` default.

## Environment variables

See `.env.example` at the repo root.

- `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_AUTH_MODE` (`bearer` or `basic`) — same as `jira_create_tasks_test.py`.
- `JIRA_PROJECT_KEY` (default `POS`) — which project to read.
- `JIRA_HISTORICAL_SPRINTS` — comma-separated sprint names (e.g. `Sprint 214,Sprint 215,...,Sprint 224`).
- `JIRA_VERIFY_SSL` — `true` or `false`. False for corporate proxies with self-signed certs.
- `JIRA_SP_FIELD` — defaults to `customfield_10028` (same as `jira_create_tasks_test.py`).
- `OPENAI_API_KEY` — optional.
- `OPENAI_MODEL` — defaults to `gpt-4o-mini`.
