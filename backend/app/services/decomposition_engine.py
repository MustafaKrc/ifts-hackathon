"""
Decomposes a Jira issue into FE/BE/DB/Test/Analysis subtasks.

Subtask selection is signal-driven: a DB subtask is only generated when the
issue's labels or components hint at schema/data work; an Analysis subtask is
generated when acceptance criteria are missing or the description is vague.

Each subtask gets an estimated size that is a fraction of the parent issue's
predicted size, weighted by the subtask type. The sum approximates the parent.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from ..data.mock_team import find_by_id
from ..models import (
    DecompositionResult,
    JiraIssue,
    PlanningResult,
    SubTask,
    TeamMember,
    TeamPerformance,
)
from .assignment_engine import (
    AssignmentSuggestion,
    _overload_risk,
    assign_subtask,
)
from .llm_decomposition import get_llm_decomposition

log = logging.getLogger("sprintpilot.decompose")

_SIZE_WEIGHTS = {
    "Analysis": 0.15,
    "DB": 0.20,
    "Backend": 0.35,
    "Frontend": 0.25,
    "Test": 0.20,
}


def _needs_db(issue: JiraIssue) -> bool:
    text = " ".join(issue.labels + issue.components).lower()
    keywords = ("db", "data", "schema", "migration", "model", "database", "billing")
    return any(k in text for k in keywords)


def _needs_analysis(issue: JiraIssue) -> bool:
    return not issue.acceptance_criteria or len(issue.description or "") < 80


def _needs_frontend(issue: JiraIssue) -> bool:
    text = " ".join(issue.labels + issue.components).lower()
    keywords = ("frontend", "ui", "customer-facing", "screen", "page", "view", "form")
    return any(k in text for k in keywords) or "ui" in (issue.title or "").lower()


def _needs_backend(issue: JiraIssue) -> bool:
    # Backend is the default unless the issue is pure UI polish
    text = " ".join(issue.labels + issue.components).lower()
    return True or "backend" in text  # always include backend


def _choose_types(issue: JiraIssue) -> list[str]:
    types: list[str] = []
    if _needs_analysis(issue):
        types.append("Analysis")
    if _needs_db(issue):
        types.append("DB")
    if _needs_backend(issue):
        types.append("Backend")
    if _needs_frontend(issue):
        types.append("Frontend")
    types.append("Test")
    return types


def _estimate_size(parent_size: int, type_: str, type_count: int) -> int:
    weight = _SIZE_WEIGHTS.get(type_, 1.0 / max(type_count, 1))
    raw = max(1, round(parent_size * weight))
    return min(raw, 8)


def _subtask_title(issue: JiraIssue, type_: str) -> str:
    base = issue.title
    mapping = {
        "Analysis": f"Analysis: clarify requirements for {base}",
        "DB": f"DB schema / data model changes for {base}",
        "Backend": f"Backend implementation for {base}",
        "Frontend": f"Frontend integration for {base}",
        "Test": f"QA verification for {base}",
    }
    return mapping.get(type_, base)


def _staggered_deadline(parent: Optional[date], index: int, total: int) -> Optional[date]:
    if not parent:
        return None
    # Earlier types get earlier internal deadlines so Test ends near parent.
    days_before = (total - index - 1) * 2
    return parent - timedelta(days=days_before) if days_before > 0 else parent


_VALID_TYPES = {"Analysis", "DB", "Backend", "Frontend", "Test"}


def _from_llm_payload(
    payload: dict,
    issue: JiraIssue,
    planning: PlanningResult,
    team: list[TeamMember],
    performance: list[TeamPerformance] | None,
) -> DecompositionResult | None:
    raw_subtasks = payload.get("subtasks") or []
    if not raw_subtasks:
        return None

    used_suffixes: set[str] = set()
    subtasks: list[SubTask] = []
    total_types = len(raw_subtasks)

    for i, raw in enumerate(raw_subtasks):
        raw_type = (raw.get("type") or "").strip()
        if raw_type not in _VALID_TYPES:
            log.warning(
                "decompose %s: LLM returned invalid type=%s — skipping subtask",
                issue.key, raw_type,
            )
            continue
        try:
            size = max(1, int(raw.get("estimated_size") or 1))
        except (TypeError, ValueError):
            size = max(1, planning.predicted_size // max(total_types, 1))

        # Suffix must be unique even if LLM emits two of the same type
        base = _suffix(raw_type)
        suffix = base
        n = 2
        while suffix in used_suffixes:
            suffix = f"{base}{n}"
            n += 1
        used_suffixes.add(suffix)
        subtask_id = f"{issue.key}-{suffix}"

        # Try LLM's suggested assignee. Validate it exists in the team.
        llm_assignee_id = (raw.get("suggested_assignee_id") or "").strip() or None
        llm_member = find_by_id(llm_assignee_id) if llm_assignee_id else None
        if llm_member:
            risk = _overload_risk(llm_member, size)
            reason = (
                f"chosen by AI: {raw.get('reason') or ''}".strip().rstrip(":")
                or f"AI selected {llm_member.name} for this {raw_type} task"
            )
            assignee_id = llm_member.id
            assignee_name = llm_member.name
        else:
            # Defer to deterministic assignment engine
            suggestion: AssignmentSuggestion = assign_subtask(
                raw_type, size, team, performance
            )
            assignee_id = suggestion.assignee_id
            assignee_name = suggestion.assignee_name
            risk = suggestion.overload_risk
            reason = suggestion.reason

        deadline = _staggered_deadline(issue.deadline, i, total_types)
        title = (raw.get("title") or _subtask_title(issue, raw_type)).strip()

        subtasks.append(
            SubTask(
                id=subtask_id,
                parent_issue_key=issue.key,
                title=title,
                type=raw_type,  # type: ignore[arg-type]
                estimated_size=size,
                suggested_assignee_id=assignee_id,
                suggested_assignee_name=assignee_name,
                assignment_reason=reason,
                overload_risk=risk,
                deadline=deadline,
            )
        )
        log.info(
            "decompose %s LLM subtask=%s type=%s size=%d assignee=%s overload=%s",
            issue.key, subtask_id, raw_type, size, assignee_name, risk,
        )

    if not subtasks:
        return None

    if payload.get("should_decompose") is False:
        log.info(
            "decompose %s LLM said atomic: '%s'",
            issue.key, payload.get("rationale") or "(no rationale)",
        )
    else:
        log.info(
            "decompose %s LLM produced %d subtasks: %s",
            issue.key, len(subtasks), payload.get("rationale") or "(no rationale)",
        )
    return DecompositionResult(issue_key=issue.key, subtasks=subtasks)


def decompose(
    issue: JiraIssue,
    planning: PlanningResult,
    team: list[TeamMember],
    performance: list[TeamPerformance] | None = None,
) -> DecompositionResult:
    # 1. Try LLM-driven decomposition first.
    payload = get_llm_decomposition(issue, planning, team)
    if payload:
        llm_result = _from_llm_payload(payload, issue, planning, team, performance)
        if llm_result:
            return llm_result
        log.warning(
            "decompose %s: LLM payload unusable, falling back to deterministic",
            issue.key,
        )

    # 2. Deterministic fallback — signal-driven type selection.
    types = _choose_types(issue)
    log.info(
        "decompose %s parent_size=%d -> deterministic types=%s (signals: needs_ac=%s needs_db=%s needs_fe=%s)",
        issue.key, planning.predicted_size, types,
        _needs_analysis(issue), _needs_db(issue), _needs_frontend(issue),
    )
    subtasks: list[SubTask] = []
    for i, t in enumerate(types):
        size = _estimate_size(planning.predicted_size, t, len(types))
        suggested = assign_subtask(t, size, team, performance)
        deadline = _staggered_deadline(issue.deadline, i, len(types))
        subtask_id = f"{issue.key}-{_suffix(t)}"
        subtasks.append(
            SubTask(
                id=subtask_id,
                parent_issue_key=issue.key,
                title=_subtask_title(issue, t),
                type=t,  # type: ignore[arg-type]
                estimated_size=size,
                suggested_assignee_id=suggested.assignee_id,
                suggested_assignee_name=suggested.assignee_name,
                assignment_reason=suggested.reason,
                overload_risk=suggested.overload_risk,
                deadline=deadline,
            )
        )
        log.info(
            "decompose %s deterministic subtask=%s type=%s size=%d assignee=%s overload=%s",
            issue.key, subtask_id, t, size, suggested.assignee_name, suggested.overload_risk,
        )
    log.info("decompose %s deterministic produced %d subtasks", issue.key, len(subtasks))
    return DecompositionResult(issue_key=issue.key, subtasks=subtasks)


def _suffix(type_: str) -> str:
    return {
        "Analysis": "ANA",
        "DB": "DB",
        "Backend": "BE",
        "Frontend": "FE",
        "Test": "QA",
    }.get(type_, type_[:2].upper())
