# Hackathon App Guidelines

## Objective

Build a jury-ready Turkcell-themed AI demo fast. Optimize for visible user value, stable end-to-end flows, and simple code that can be extended safely by agents.

## Product Lens

- Keep features grounded in telecom/Turkcell scenarios such as churn, retention, campaign targeting, customer experience, network quality, CRM/BSS/OSS, or field operations.
- Prefer one strong demo story over multiple incomplete features.
- If the user asks for hackathon planning and has not shared an idea yet, ask exactly:

	> What is your hackathon idea? Give me a short description — one or two sentences is enough. I'll turn it into a full execution plan.

- After an idea is provided, respond with a compact implementation plan focused on: enhanced idea, problem, MVP scope, architecture, data, AI approach, UI direction, demo flow, one-minute pitch, and the immediate next action. Expand only when the user explicitly asks for more detail.

## Delivery Rules

- Default stack: FastAPI backend on port 8000 and React + Vite frontend on port 5173.
- Favor deterministic demo logic: seeded SQLite, mock JSON, or hard-coded fixtures before real integrations.
- Avoid real authentication, RBAC, queues, background jobs, microservices, complex migrations, or heavy ML training unless explicitly requested.
- If a task is likely to take more than 30 minutes and is not clearly visible in the demo, propose a simpler alternative.
- Build vertical slices: complete one visible feature across backend and frontend before starting the next.
- Prefer runnable code over pseudocode.

## Backend Conventions

- Keep FastAPI route handlers in `backend/routers` thin and focused on HTTP concerns.
- Put scoring, transformation, and business rules in small helper functions or modules instead of burying them in route handlers.
- Use `schemas.py` for request and response contracts when adding or changing endpoints.
- Prefer predictable, explainable AI outputs over opaque behavior.
- Keep CORS aligned with the Vite dev server.
- Reuse the existing persistence approach before introducing a new database or service.

## Frontend Conventions

- Keep route-level screens in `frontend/src/pages`.
- Keep API access centralized in `frontend/src/services/api.js`.
- Use Ant Design as the default React component library for layout, forms, tables, modals, tabs, and feedback states.
- Prefer Ant Design components and theme tokens over custom-building common UI primitives.
- Use Redux only for truly shared application state. Prefer local state for page-specific behavior.
- Keep data fetching close to the page boundary and pass simple props into presentational components.
- Do not mix multiple UI libraries unless explicitly required; extend Ant Design with the existing CSS and class patterns for brand-specific polish.
- If charts are needed, prefer `recharts`.

## UI Style

- Always use the Turkcell palette:
	- Yellow `#FFD100`
	- Navy `#003087`
	- White `#FFFFFF`
	- Light Grey `#F5F5F5`
	- Dark Text `#1A1A2E`
	- Success `#28A745`
	- Warning `#FF6B35`
	- Risk `#DC3545`
- Map the Turkcell palette into Ant Design theme tokens so buttons, cards, badges, and alerts stay visually consistent.
- Follow the bright, high-contrast visual direction already started in `frontend/src/styles/theme.css`.
- Prefer card-based layouts, KPI summaries, recommendation panels, risk badges, and visible AI labels.
- Avoid heavy animation or decorative complexity that does not help the demo.

## AI Guidance

- Prefer this effort-to-impact order:
	1. Rule-based scoring
	2. Precomputed scores in mock data
	3. Lightweight LLM-generated summaries if an API is available
	4. Small sklearn models only if they are fast and stable
- Every AI output shown in the UI should be explainable in one sentence.
- Surface confidence, score, or recommendation labels in the UI when possible.

## Working Style For Agents

- Start from the nearest relevant file or route instead of redesigning the whole app.
- Make the smallest useful change first, then run the narrowest validation available.
- Preserve existing naming and structure unless a clear simplification is needed.
- Keep docs and instructions short. Do not add large prompt files or duplicate guidance unless the user asks for them.

## Useful Commands

```bash
cd backend && uvicorn main:app --reload
cd frontend && npm run dev
cd frontend && npm run build
```
