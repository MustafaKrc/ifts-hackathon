"""
Generates in-app notifications for sprint events.

- Ready-to-Start: when a subtask becomes Ready after its dependencies complete.
- Dependency-Completed: when a predecessor task is marked Done.
- Deadline-Risk: when a subtask is within 2 days of deadline but Not Ready.

There is no real email/Slack/Teams send. The TaskNotification carries the
target assignee contact so the UI can render a "Copy message" preview.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from ..data.mock_team import find_by_id
from ..models import (
    NotificationType,
    SequencedSubTask,
    TaskNotification,
)


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


def _contact(assignee_id: str) -> str | None:
    m = find_by_id(assignee_id)
    if not m:
        return None
    parts: list[str] = []
    if m.email:
        parts.append(m.email)
    if m.teams_handle:
        parts.append(m.teams_handle)
    return " · ".join(parts) if parts else None


def ready_to_start_notification(
    successor: SequencedSubTask, completed_id: str
) -> TaskNotification:
    msg = (
        f"{successor.suggested_assignee_name}, {successor.id} is ready to start. "
        f"{completed_id} has just been completed."
    )
    return TaskNotification(
        id=_new_id(),
        type="ReadyToStart",
        target_assignee_id=successor.suggested_assignee_id,
        target_assignee_name=successor.suggested_assignee_name,
        target_contact=_contact(successor.suggested_assignee_id),
        task_id=successor.id,
        task_title=successor.title,
        message=msg,
        created_at=datetime.utcnow(),
    )


def dependency_completed_notification(
    successor: SequencedSubTask, completed_id: str
) -> TaskNotification:
    msg = (
        f"Upstream dependency {completed_id} completed; "
        f"{successor.id} can move forward once remaining predecessors are done."
    )
    return TaskNotification(
        id=_new_id(),
        type="DependencyCompleted",
        target_assignee_id=successor.suggested_assignee_id,
        target_assignee_name=successor.suggested_assignee_name,
        target_contact=_contact(successor.suggested_assignee_id),
        task_id=successor.id,
        task_title=successor.title,
        message=msg,
        created_at=datetime.utcnow(),
    )


def deadline_risk_notification(task: SequencedSubTask) -> TaskNotification:
    if not task.deadline:
        days_left = "?"
    else:
        days_left = max(0, (task.deadline - date.today()).days)
    msg = (
        f"Deadline risk on {task.id}: {days_left} day(s) remaining but task is "
        f"{task.status}. Consider expediting predecessor work."
    )
    return TaskNotification(
        id=_new_id(),
        type="DeadlineRisk",
        target_assignee_id=task.suggested_assignee_id,
        target_assignee_name=task.suggested_assignee_name,
        target_contact=_contact(task.suggested_assignee_id),
        task_id=task.id,
        task_title=task.title,
        message=msg,
        created_at=datetime.utcnow(),
    )
