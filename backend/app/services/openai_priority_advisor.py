"""
OpenAI Priority Advisor.

When OPENAI_API_KEY is set, sends a structured prompt to OpenAI and asks for
dependency-aware + deadline-aware sequencing. Returns parsed JSON dict or None
on any failure. The caller is responsible for the deterministic fallback.

No exception ever bubbles out of this module. The app must keep running even
if OpenAI is misconfigured, unreachable, or rate-limited.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from ..models import JiraIssue, SubTask, TeamMember

_SYSTEM_PROMPT = (
    "You are an expert Agile delivery manager and technical lead. "
    "You receive a Jira issue, its generated subtasks, the team roster, and the "
    "issue deadline. You must produce a dependency-aware and deadline-aware "
    "execution order.\n\n"
    "Rules:\n"
    "- Testing cannot be completed before development is implemented.\n"
    "- Frontend integration may depend on backend API contract.\n"
    "- Backend may depend on analysis or DB schema.\n"
    "- DB schema changes should happen before backend implementation when relevant.\n"
    "- Analysis should happen before implementation if business rules are unclear.\n"
    "- Earlier deadlines increase priority, but do NOT override technical dependencies.\n"
    "- A task with incomplete dependencies must be marked Not Ready.\n"
    "- When a dependency is completed, successor tasks may become Ready.\n"
    "- Respect assignee capacity. Flag risky overload.\n\n"
    "Return ONLY valid JSON in this shape:\n"
    "{\n"
    '  "ordered_subtasks": [\n'
    '    {"id": "POS-XXX-BE", "priority_order": 1, "priority_score": 78, '
    '"status": "Ready", "sequencing_reason": "...", "deadline_reason": "...", '
    '"risk_if_delayed": "..."}\n'
    "  ],\n"
    '  "critical_path": ["POS-XXX-BE", "POS-XXX-FE"],\n'
    '  "sequencing_summary": "...",\n'
    '  "schedule_risks": ["..."],\n'
    '  "recommended_first_action": "..."\n'
    "}"
)


def _build_prompt(
    subtasks: list[SubTask], team: list[TeamMember], issue: JiraIssue
) -> str:
    issue_block = (
        f"Issue: {issue.key}\n"
        f"Title: {issue.title}\n"
        f"Priority: {issue.priority}\n"
        f"Deadline: {issue.deadline.isoformat() if issue.deadline else 'none'}\n"
        f"Acceptance criteria present: {bool(issue.acceptance_criteria)}\n"
        f"Has blocker: {bool(issue.blocker_reason)}\n"
        f"Dependencies: {', '.join(issue.dependencies) or 'none'}\n"
    )
    subtasks_block = "\n".join(
        f"- {s.id} ({s.type}, {s.estimated_size}SP) assigned to "
        f"{s.suggested_assignee_name}, overload={s.overload_risk}, "
        f"deadline={s.deadline.isoformat() if s.deadline else 'none'}"
        for s in subtasks
    )
    team_block = "\n".join(
        f"- {m.id} {m.name} ({m.role}, skills={','.join(m.skills)}, "
        f"capacity={m.capacity}, current_load={m.current_load})"
        for m in team
    )
    return (
        f"{issue_block}\n"
        f"Subtasks:\n{subtasks_block}\n\n"
        f"Team:\n{team_block}\n\n"
        "Return only valid JSON."
    )


def get_openai_sequence(
    subtasks: list[SubTask], team: list[TeamMember], issue: JiraIssue
) -> Optional[dict]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            temperature=0.2,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_prompt(subtasks, team, issue)},
            ],
            timeout=20,
        )
        content = response.choices[0].message.content or ""
        return json.loads(content)
    except Exception:
        return None
