"""
LLM-driven task decomposition.

Asks OpenAI to choose the **right** subtask shape for an issue rather than blindly
emitting 5 generic subtasks. Key behaviours we encode in the system prompt:

  - Decompose only when the issue is large/multi-discipline enough to benefit.
  - Skip subtasks that do not apply (a pure QA issue must NOT have a Test child).
  - Total subtask size must approximate the parent's predicted size.
  - Pick the suggested assignee from the provided team using their skill matrix.

Falls back gracefully when the OpenAI key is missing, quota is exhausted, or
the JSON doesn't parse — the caller then runs the deterministic engine.

The circuit breaker from openai_priority_advisor.py is reused here so a single
429 doesn't cost us 1-2 seconds per task for the rest of the session.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from ..models import JiraIssue, PlanningResult, TeamMember
from .openai_priority_advisor import _disable, _openai_disabled_reason  # type: ignore[attr-defined]

log = logging.getLogger("sprintpilot.llm_decompose")


_SYSTEM_PROMPT = (
    "You are an expert Agile delivery lead decomposing a Jira issue into the "
    "RIGHT shape of subtasks for sprint planning. Avoid noise — only emit "
    "subtasks that genuinely apply to this issue.\n\n"
    "Allowed types: Analysis, DB, Backend, Frontend, Test.\n"
    "\n"
    "Decomposition rules:\n"
    "- If the issue is small / atomic (≤3 SP, single discipline, well-defined), "
    "set should_decompose=false and return ONE 'atomic' subtask (use the type "
    "that best matches the work) at the parent's full size, assigned to the "
    "single best-fit team member.\n"
    "- A pure QA / verification / test execution issue must NOT include a Test "
    "subtask — it already IS the test work. Use type=Test ONCE for the work itself.\n"
    "- A pure documentation / analysis spike must NOT include Backend/Frontend "
    "children — only Analysis.\n"
    "- A UI-polish-only issue does NOT need a Backend subtask.\n"
    "- A backend-only API change does NOT need a Frontend subtask.\n"
    "- Add Analysis ONLY when acceptance criteria are missing or the description "
    "is materially vague.\n"
    "- Add DB ONLY when schema / migration / data model work is actually needed.\n"
    "- Always include Test when there is any code change unless the issue is a "
    "Test issue itself.\n"
    "- Total estimated_size of all subtasks must equal (±1) the parent's "
    "predicted_size.\n"
    "- For each subtask, pick the suggested_assignee_id from the provided team "
    "whose skill matrix and seniority best fits the work.\n\n"
    "Return ONLY valid JSON in this exact shape (no commentary):\n"
    "{\n"
    '  "should_decompose": true|false,\n'
    '  "rationale": "<one sentence>",\n'
    '  "subtasks": [\n'
    "    {\n"
    '      "type": "Analysis|DB|Backend|Frontend|Test",\n'
    '      "title": "<short>",\n'
    '      "estimated_size": <integer SP, fibonacci-ish>,\n'
    '      "suggested_assignee_id": "<member id from team>",\n'
    '      "reason": "<one sentence why this person + this subtask>"\n'
    "    }\n"
    "  ]\n"
    "}"
)


def _build_prompt(
    issue: JiraIssue,
    planning: PlanningResult,
    team: list[TeamMember],
) -> str:
    team_lines = []
    for m in team:
        skills_inline = ", ".join(
            f"{sp.area}={sp.level}/5" for sp in m.skill_matrix
        )
        capacity_left = max(0, m.capacity - m.current_load)
        team_lines.append(
            f"- {m.id} {m.name} ({m.title} {m.role}, {m.years_experience}y exp) "
            f"skills=[{skills_inline}] capacity_left={capacity_left}SP"
        )
    team_block = "\n".join(team_lines)

    return (
        f"Issue: {issue.key}\n"
        f"Title: {issue.title}\n"
        f"Description: {(issue.description or '')[:600]}\n"
        f"Priority: {issue.priority}\n"
        f"Predicted total size: {planning.predicted_size} SP\n"
        f"Sizing confidence: {planning.confidence}%\n"
        f"Risk: {planning.risk_level}\n"
        f"Carry-over count: {issue.carry_over_count}\n"
        f"Acceptance criteria present: {bool(issue.acceptance_criteria)}\n"
        f"Has blocker: {bool(issue.blocker_reason)}\n"
        f"Labels: {issue.labels}\n"
        f"Components: {issue.components}\n"
        f"\nTeam (skill levels 1..5):\n{team_block}\n\n"
        "Return only valid JSON. Do not invent assignee ids — pick from the team list."
    )


def get_llm_decomposition(
    issue: JiraIssue,
    planning: PlanningResult,
    team: list[TeamMember],
) -> Optional[dict]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        log.info("LLM decompose skipped for %s: OPENAI_API_KEY not set", issue.key)
        return None
    if _openai_disabled_reason:
        log.info(
            "LLM decompose skipped for %s (circuit open: %s)",
            issue.key, _openai_disabled_reason,
        )
        return None
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    prompt = _build_prompt(issue, planning, team)
    log.info(
        "LLM decompose calling %s for %s prompt_chars=%d team=%d predicted=%dSP",
        model, issue.key, len(prompt), len(team), planning.predicted_size,
    )
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, max_retries=0)
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            temperature=0.2,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            timeout=20,
        )
        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        if usage:
            log.info(
                "LLM decompose response for %s tokens prompt=%s completion=%s total=%s",
                issue.key,
                getattr(usage, "prompt_tokens", "?"),
                getattr(usage, "completion_tokens", "?"),
                getattr(usage, "total_tokens", "?"),
            )
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as je:
            log.error(
                "LLM decompose %s unparseable JSON: %s; content (first 300): %s",
                issue.key, je, content[:300],
            )
            return None
        # Light sanity checks
        if not isinstance(payload, dict) or "subtasks" not in payload:
            log.warning("LLM decompose %s: payload missing 'subtasks' key", issue.key)
            return None
        log.info(
            "LLM decompose %s should_decompose=%s subtasks=%d types=%s",
            issue.key,
            payload.get("should_decompose"),
            len(payload.get("subtasks", [])),
            [s.get("type") for s in payload.get("subtasks", [])],
        )
        return payload
    except Exception as e:
        name = type(e).__name__
        log.error("LLM decompose %s exception: %s: %s", issue.key, name, str(e)[:200])
        # Trip shared OpenAI circuit so the rest of this auto-sprint run is fast.
        if name in {
            "RateLimitError", "AuthenticationError", "NotFoundError",
            "PermissionDeniedError", "BadRequestError",
        }:
            _disable(f"{name}: {str(e)[:120]}")
            log.warning("OpenAI circuit opened by LLM decompose failure")
        return None
