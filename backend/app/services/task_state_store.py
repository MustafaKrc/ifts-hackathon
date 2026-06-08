"""
In-memory store for sprint state (sequences, task status, notifications).

This is intentionally a single module-level instance. State is lost on
backend restart — fine for hackathon demo. No persistence layer.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from ..models import (
    SequencedSubTask,
    TaskNotification,
    TaskSequenceResult,
    TaskStatus,
)

log = logging.getLogger("sprintpilot.state")


class TaskStateStore:
    def __init__(self) -> None:
        self.sequences: dict[str, TaskSequenceResult] = {}
        self.task_status: dict[str, TaskStatus] = {}
        self.notifications: list[TaskNotification] = []

    def save_sequence(self, sequence: TaskSequenceResult) -> None:
        self.sequences[sequence.issue_key] = sequence
        for st in sequence.ordered_subtasks:
            self.task_status.setdefault(st.id, st.status)
        log.info(
            "store.save_sequence %s subtasks=%d total_sequences=%d total_tasks=%d",
            sequence.issue_key, len(sequence.ordered_subtasks),
            len(self.sequences), len(self.task_status),
        )

    def get_subtask(self, task_id: str) -> Optional[SequencedSubTask]:
        for seq in self.sequences.values():
            for st in seq.ordered_subtasks:
                if st.id == task_id:
                    return st
        return None

    def get_status(self, task_id: str) -> TaskStatus:
        return self.task_status.get(task_id, "Not Ready")

    def set_status(self, task_id: str, status: TaskStatus) -> None:
        previous = self.task_status.get(task_id, "Not Ready")
        self.task_status[task_id] = status
        if previous != status:
            log.info("store.set_status %s: %s -> %s", task_id, previous, status)

    def successors(self, task_id: str) -> list[SequencedSubTask]:
        out: list[SequencedSubTask] = []
        for seq in self.sequences.values():
            for st in seq.ordered_subtasks:
                if task_id in st.can_start_after:
                    out.append(st)
        return out

    def all_predecessors_done(self, task: SequencedSubTask) -> bool:
        return all(self.get_status(dep) == "Done" for dep in task.can_start_after)

    def add_notification(self, notification: TaskNotification) -> None:
        self.notifications.insert(0, notification)
        log.info(
            "store.add_notification id=%s type=%s task=%s -> %s",
            notification.id, notification.type, notification.task_id,
            notification.target_assignee_name,
        )

    def list_notifications(self) -> list[TaskNotification]:
        return list(self.notifications)

    def mark_read(self, notification_id: str) -> None:
        for n in self.notifications:
            if n.id == notification_id:
                n.read = True
                return

    def reset(self) -> None:
        self.sequences.clear()
        self.task_status.clear()
        self.notifications.clear()


store = TaskStateStore()
