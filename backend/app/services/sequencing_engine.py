"""
Dependency-aware + deadline-aware execution sequencing for decomposed subtasks.

When OPENAI_API_KEY is configured the OpenAI Priority Advisor is tried first
(returns a structured JSON sequencing recommendation). If it is missing or
fails for any reason, this deterministic fallback runs:

  Analysis → DB → Backend → Frontend → Test

With these refinements:
  - Acceptance criteria missing → Analysis stays at the very front.
  - Earlier deadlines tie-break within the same stage.
  - Tasks whose dependencies have not completed are marked "Not Ready".
  - Critical path is the longest dependency chain through the subtasks.
  - Recommended first action is the highest-priority Ready task.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from ..data.mock_team import find_by_id
from ..models import (
    DecompositionResult,
    JiraIssue,
    SequencedSubTask,
    SubTask,
    TaskDependency,
    TaskSequenceResult,
    TaskStatus,
    TeamMember,
)
from .openai_priority_advisor import get_openai_sequence

log = logging.getLogger("sprintpilot.sequence")

_STAGE_ORDER = ["Analysis", "DB", "Backend", "Frontend", "Test"]


def _build_dependency_graph(subtasks: list[SubTask]) -> list[TaskDependency]:
    """Implicit edges based on technical stage order."""
    by_type: dict[str, list[SubTask]] = {}
    for s in subtasks:
        by_type.setdefault(s.type, []).append(s)

    deps: list[TaskDependency] = []
    stages_present = [t for t in _STAGE_ORDER if t in by_type]

    for i, stage in enumerate(stages_present[1:], start=1):
        upstream_stage = stages_present[i - 1]
        for from_task in by_type[upstream_stage]:
            for to_task in by_type[stage]:
                deps.append(
                    TaskDependency(
                        from_subtask_id=from_task.id,
                        to_subtask_id=to_task.id,
                        reason=f"{stage} cannot start before {upstream_stage} completes",
                    )
                )
    # Test stage depends on all dev stages (FE+BE+DB)
    if "Test" in by_type:
        for to_task in by_type["Test"]:
            for dev_stage in ("DB", "Backend", "Frontend"):
                if dev_stage in by_type:
                    for from_task in by_type[dev_stage]:
                        if not any(
                            d.from_subtask_id == from_task.id
                            and d.to_subtask_id == to_task.id
                            for d in deps
                        ):
                            deps.append(
                                TaskDependency(
                                    from_subtask_id=from_task.id,
                                    to_subtask_id=to_task.id,
                                    reason=f"Test depends on {dev_stage} completion",
                                )
                            )
    return deps


def _critical_path(
    subtasks: list[SubTask], deps: list[TaskDependency]
) -> list[str]:
    # Longest chain by SP. Topological order is implicit via stage order.
    incoming: dict[str, list[str]] = {s.id: [] for s in subtasks}
    sp: dict[str, int] = {s.id: s.estimated_size for s in subtasks}
    for d in deps:
        incoming[d.to_subtask_id].append(d.from_subtask_id)

    # Compute longest path ending at each node
    longest_path: dict[str, list[str]] = {s.id: [s.id] for s in subtasks}
    longest_weight: dict[str, int] = {s.id: sp[s.id] for s in subtasks}

    # Process in stage order
    type_order = {s.id: _STAGE_ORDER.index(s.type) if s.type in _STAGE_ORDER else 99
                  for s in subtasks}
    ordered_ids = sorted([s.id for s in subtasks], key=lambda i: type_order[i])

    for tid in ordered_ids:
        for prev in incoming[tid]:
            candidate_weight = longest_weight[prev] + sp[tid]
            if candidate_weight > longest_weight[tid]:
                longest_weight[tid] = candidate_weight
                longest_path[tid] = longest_path[prev] + [tid]

    if not longest_path:
        return []
    end = max(longest_path, key=lambda k: longest_weight[k])
    return longest_path[end]


def _deadline_urgency_score(deadline: Optional[date]) -> int:
    if not deadline:
        return 5
    days_left = (deadline - date.today()).days
    if days_left <= 0:
        return 25
    if days_left <= 3:
        return 22
    if days_left <= 7:
        return 18
    if days_left <= 14:
        return 12
    return 6


def _priority_score(
    subtask: SubTask,
    deadline: Optional[date],
    on_critical_path: bool,
    deps_ready: bool,
) -> int:
    score = 0
    score += 15 if deps_ready else 0
    score += _deadline_urgency_score(deadline)
    score += 10 if on_critical_path else 0
    if subtask.overload_risk == "High":
        score -= 8
    elif subtask.overload_risk == "Medium":
        score -= 3
    return max(1, score)


def _deterministic_sequence(
    subtasks: list[SubTask],
    deps: list[TaskDependency],
    issue: JiraIssue,
) -> tuple[list[SequencedSubTask], list[str], str, list[str], str]:
    critical_path = _critical_path(subtasks, deps)

    # Build adjacency: task_id -> list of predecessor task_ids
    predecessors: dict[str, list[str]] = {s.id: [] for s in subtasks}
    for d in deps:
        predecessors[d.to_subtask_id].append(d.from_subtask_id)

    # Order by stage, then deadline urgency, then priority
    def sort_key(s: SubTask) -> tuple[int, int]:
        stage_idx = _STAGE_ORDER.index(s.type) if s.type in _STAGE_ORDER else 99
        days_to_deadline = (
            (s.deadline - date.today()).days if s.deadline else 999
        )
        return (stage_idx, days_to_deadline)

    ordered = sorted(subtasks, key=sort_key)

    sequenced: list[SequencedSubTask] = []
    schedule_risks: list[str] = []

    for i, s in enumerate(ordered):
        deps_for_task = predecessors[s.id]
        deps_ready = i == 0 and not deps_for_task  # Only first task starts Ready
        if i == 0:
            status: TaskStatus = "Ready"
        else:
            status = "Not Ready"

        on_critical = s.id in critical_path
        ps = _priority_score(s, s.deadline, on_critical, status == "Ready")

        deadline_reason = _deadline_reason(s, issue)
        sequencing_reason = _sequencing_reason(s, deps_for_task, on_critical, deps_ready)
        risk_if_delayed = _risk_if_delayed(s, on_critical, issue)

        if (
            s.deadline
            and (s.deadline - date.today()).days <= 2
            and status != "Ready"
        ):
            schedule_risks.append(
                f"{s.id}: deadline in <2 days but dependencies are not complete."
            )

        member = find_by_id(s.suggested_assignee_id)
        sequenced.append(
            SequencedSubTask(
                id=s.id,
                parent_issue_key=s.parent_issue_key,
                title=s.title,
                type=s.type,
                estimated_size=s.estimated_size,
                suggested_assignee_id=s.suggested_assignee_id,
                suggested_assignee_name=s.suggested_assignee_name,
                assignee_contact=member.email if member else None,
                assignment_reason=s.assignment_reason,
                overload_risk=s.overload_risk,
                status=status,
                deadline=s.deadline,
                priority_order=i + 1,
                priority_score=ps,
                can_start_after=deps_for_task,
                sequencing_reason=sequencing_reason,
                deadline_reason=deadline_reason,
                risk_if_delayed=risk_if_delayed,
            )
        )

    if "Test" in [s.type for s in subtasks]:
        test_task = next((s for s in ordered if s.type == "Test"), None)
        if test_task and test_task.deadline:
            days_left_for_test = (test_task.deadline - date.today()).days
            dev_sp = sum(
                s.estimated_size for s in subtasks if s.type in ("Backend", "Frontend", "DB")
            )
            if days_left_for_test < dev_sp:
                schedule_risks.append(
                    "Test is at risk of being squeezed: development workload may not "
                    "finish in time to leave a verification window."
                )

    first_ready = next((t for t in sequenced if t.status == "Ready"), sequenced[0] if sequenced else None)
    recommended_first = (
        f"Start {first_ready.id} ({first_ready.title}) — assignee {first_ready.suggested_assignee_name}."
        if first_ready
        else "No tasks to start yet."
    )
    summary = (
        f"Sequenced {len(sequenced)} subtasks across "
        f"{len({s.type for s in subtasks})} stages. "
        f"Critical path covers {len(critical_path)} tasks."
    )

    return sequenced, critical_path, summary, schedule_risks, recommended_first


def _deadline_reason(s: SubTask, issue: JiraIssue) -> str:
    if not s.deadline:
        return "No internal deadline set."
    days = (s.deadline - date.today()).days
    if days <= 0:
        return f"Deadline is today / passed for {s.type} of {issue.key}."
    if days <= 3:
        return f"Deadline is in {days} day(s) — high urgency."
    return f"Deadline is in {days} day(s)."


def _sequencing_reason(
    s: SubTask, deps_for_task: list[str], on_critical: bool, ready: bool
) -> str:
    if ready:
        base = f"{s.type} is the first stage and has no upstream dependencies."
    else:
        base = (
            f"{s.type} cannot start before "
            f"{', '.join(deps_for_task)} complete."
        )
    if on_critical:
        base += " On the critical path."
    return base


def _risk_if_delayed(s: SubTask, on_critical: bool, issue: JiraIssue) -> str:
    if on_critical:
        return (
            f"Delaying this {s.type.lower()} task slips the whole {issue.key} delivery "
            "because it sits on the critical path."
        )
    if s.type == "Test":
        return "Delaying QA leaves no verification window before the sprint ends."
    return f"Delaying this {s.type.lower()} task delays its dependent stages."


def _from_openai_payload(
    payload: dict,
    subtasks: list[SubTask],
    deps: list[TaskDependency],
) -> tuple[list[SequencedSubTask], list[str], str, list[str], str]:
    by_id = {s.id: s for s in subtasks}
    ordered_raw = payload.get("ordered_subtasks") or []

    # Fall back if OpenAI didn't include any of our actual ids
    if not any(r.get("id") in by_id for r in ordered_raw):
        return _deterministic_sequence(subtasks, deps, JiraIssue(id="", key=""))

    predecessors: dict[str, list[str]] = {s.id: [] for s in subtasks}
    for d in deps:
        predecessors[d.to_subtask_id].append(d.from_subtask_id)

    sequenced: list[SequencedSubTask] = []
    for i, r in enumerate(ordered_raw):
        tid = r.get("id")
        if tid not in by_id:
            continue
        s = by_id[tid]
        status_raw = (r.get("status") or "").strip()
        status: TaskStatus = (
            "Ready" if status_raw.lower() == "ready"
            else "Not Ready" if status_raw.lower() in ("not ready", "blocked")
            else ("Ready" if i == 0 else "Not Ready")
        )
        member = find_by_id(s.suggested_assignee_id)
        sequenced.append(
            SequencedSubTask(
                id=s.id,
                parent_issue_key=s.parent_issue_key,
                title=s.title,
                type=s.type,
                estimated_size=s.estimated_size,
                suggested_assignee_id=s.suggested_assignee_id,
                suggested_assignee_name=s.suggested_assignee_name,
                assignee_contact=member.email if member else None,
                assignment_reason=s.assignment_reason,
                overload_risk=s.overload_risk,
                status=status,
                deadline=s.deadline,
                priority_order=i + 1,
                priority_score=int(r.get("priority_score", 50)),
                can_start_after=predecessors[s.id],
                sequencing_reason=r.get("sequencing_reason")
                    or f"{s.type} ordered by AI dependency analysis.",
                deadline_reason=r.get("deadline_reason")
                    or _deadline_reason(s, JiraIssue(id="", key="")),
                risk_if_delayed=r.get("risk_if_delayed")
                    or _risk_if_delayed(s, False, JiraIssue(id="", key="")),
            )
        )
    critical_path = payload.get("critical_path") or [s.id for s in sequenced[:2]]
    summary = payload.get("sequencing_summary") or (
        f"AI-sequenced {len(sequenced)} subtasks with dependency + deadline awareness."
    )
    risks = payload.get("schedule_risks") or []
    recommended = payload.get("recommended_first_action") or (
        f"Start {sequenced[0].id} first."
        if sequenced
        else "No tasks to start."
    )
    return sequenced, critical_path, summary, risks, recommended


def sequence_decomposition(
    decomp: DecompositionResult,
    issue: JiraIssue,
    team: list[TeamMember],
) -> TaskSequenceResult:
    deps = _build_dependency_graph(decomp.subtasks)
    log.info(
        "sequence start %s subtasks=%d edges=%d",
        issue.key, len(decomp.subtasks), len(deps),
    )

    payload = get_openai_sequence(decomp.subtasks, team, issue)
    used_openai = False
    if payload:
        try:
            sequenced, critical_path, summary, risks, recommended = _from_openai_payload(
                payload, decomp.subtasks, deps
            )
            used_openai = True
            log.info("sequence %s using OpenAI Priority Advisor result", issue.key)
        except Exception as e:
            log.exception("sequence %s OpenAI payload parse failed, falling back: %s", issue.key, e)
            sequenced, critical_path, summary, risks, recommended = _deterministic_sequence(
                decomp.subtasks, deps, issue
            )
    else:
        log.info("sequence %s using deterministic fallback (no OpenAI payload)", issue.key)
        sequenced, critical_path, summary, risks, recommended = _deterministic_sequence(
            decomp.subtasks, deps, issue
        )

    log.info(
        "sequence %s done used_openai=%s critical_path=%s schedule_risks=%d first_action=%s",
        issue.key, used_openai, critical_path, len(risks), recommended[:80],
    )
    for st in sequenced:
        log.info(
            "  order=%d %s status=%s priority_score=%d can_start_after=%s",
            st.priority_order, st.id, st.status, st.priority_score, st.can_start_after,
        )

    return TaskSequenceResult(
        issue_key=issue.key,
        ordered_subtasks=sequenced,
        dependencies=deps,
        critical_path=critical_path,
        sequencing_summary=summary,
        schedule_risks=risks,
        recommended_first_action=recommended,
        used_openai=used_openai,
    )
