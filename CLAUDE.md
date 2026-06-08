# SprintPilot AI — Agent Rules

Local-only AI Agile Manager MVP. FastAPI backend + React/Vite JS frontend. Reads Jira (read-only). No write to Jira ever.

## Hard Rules

- Backend: Python + FastAPI in `backend/app/`. Entry: `uvicorn app.main:app --reload --port 8000`.
- Frontend: React + JavaScript (no TypeScript) + Vite + Ant Design. Entry: `cd frontend && npm run dev` (port 5173).
- Local only. No Docker, no cloud, no PostgreSQL/Redis/queue/worker/microservice.
- Pydantic models in `models.py`. No SQLAlchemy. In-memory state store only.
- Jira integration is READ-ONLY. No POST/PUT/DELETE to Jira REST API, ever.
- OpenAI integration is optional. If `OPENAI_API_KEY` missing or call fails, fall back to deterministic engine. App must never crash from OpenAI issues.
- Predictive sizing: similarity-based (kNN style), deterministic. Not a trained model.
- Dependency-aware sequencing: technical dependency order (Analysis → DB → Backend → Frontend → Test). Deadline tie-breaks but never overrides dependencies.
- Ready-to-start notifications via in-app Notification Center only. No real email/Slack/Teams.

## Style Rules

- Keep files small and focused.
- Prefer working demo over perfect architecture.
- Do not add unnecessary dependencies.
- Do not refactor unrelated files.
- Surface "Why?" reasoning in every AI output shown in UI.

## Out of Scope

- Jira write operations
- Real auth/RBAC
- ML model training
- E2E test coverage
- i18n, dark mode, mobile responsive
