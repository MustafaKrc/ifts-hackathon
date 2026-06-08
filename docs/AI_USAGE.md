# AI Usage in SprintPilot AI

How AI was used during development of this hackathon MVP, and how AI shows up in the product itself.

## Vibe coding strategy

Built top-down from the spec: pick the demo-critical happy path, scaffold the contracts (Pydantic models + API client), then fill the engines, then bind the UI. Each engine is small, focused, and independently testable via `curl`. Where the spec offered multiple options (e.g. carry-over derivation from Jira changelog vs. a flat default), we picked the option that protects the demo flow and documented the trade-off in the README. No premature abstractions: every helper was added at the second use, never at the first.

## Prompting approach

The user provided an extremely detailed Turkish-language spec covering product goals, technical constraints, model schemas, mock data, scoring formulas, and a 27-step build sequence. The plan was scoped to a 3-hour window with explicit time budgets per phase, and one major mid-flight decision (replace mock Jira with live read-only Jira) was negotiated via a focused 3-question clarification (project key, historical scope, team-member sourcing). The user picked POS · last 10 sprints (Sprint 214-224) · USER_MAP + mock metadata.

## Why we chose a deterministic AI engine over LLMs

The predictive sizing engine, decomposition engine, assignment engine, sequencing engine (fallback), sprint health engine, and simulation engine are all **deterministic**. We chose this over LLM-based generation because:

- A live demo must produce identical results on identical inputs.
- Every output has to be explainable in one sentence — easier with rule-based reasoning than with LLM hallucinations.
- Predictive sizing benefits from a clean similarity score that the user can verify by clicking the "similar historical issues" panel.
- The 3-hour window left no room to debug intermittent LLM failures.

LLMs are reserved for the one place where structured-but-creative reasoning genuinely outperforms rules: dependency-aware execution sequencing across heterogeneous subtasks. Even there, the LLM is one component behind a structured JSON contract with a deterministic fallback.

## Why similarity-based predictive sizing

Story-point estimation is a classic kNN problem: human estimators do exactly this in planning poker (recall similar past stories, weight by similarity, adjust for risk). A trained ML model would have required labeled training data, a feature pipeline, retraining over time, and serialization — none of which fits a 3-hour build. The similarity-based approach:

- Reuses the historical Jira data that already exists (no labeling).
- Produces evidence the user can verify in one click.
- Stays fast (top-3 search against ~50 historical issues).
- Improves naturally as the team logs more sprints.

## Why an OpenAI Priority Advisor

Dependency-aware sequencing is a place where LLMs genuinely help: combining technical dependency rules + deadline urgency + assignee capacity + critical-path position is exactly the kind of multi-constraint reasoning where rules need many special cases. The advisor takes a structured JSON contract from the model and falls back to the deterministic engine if anything goes wrong, so it's a strict improvement over rules-only — never a regression.

## Why the What-if Sprint Simulator is the signature feature

Every Agile dashboard out there can tell you the sprint is at risk. None of them tell you **what to remove** or **what to split** to make it healthy. The simulator is the answer to "OK, now what?" and it's the moment in the demo where the jury sees SprintPilot AI doing something they've never seen before: a side-by-side comparison of three sprint scopes with a clear, scored recommendation.

## Fallback strategy

Every external dependency has a fallback path:

- **Jira down / no credentials** → local fallback backlog (6 POS issues) + local fallback history (12 historical issues). UI shows a "fallback" pill.
- **Too few historical issues** (<3) from Jira → also falls back to local history so similarity scoring stays meaningful.
- **OpenAI key missing or call fails** → deterministic sequencing engine. UI shows "Deterministic fallback" on the sequence card.
- **Unparseable OpenAI JSON** → caught by try/except, same fallback path. App never raises.
- **Browser clipboard API unavailable** → graceful Antd `message.warning` instead of crash.

The point: the demo never breaks, even in an air-gapped conference room.
