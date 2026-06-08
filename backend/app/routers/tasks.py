from fastapi import APIRouter, HTTPException

from ..models import CompleteTaskRequest
from ..services.notification_engine import (
    dependency_completed_notification,
    ready_to_start_notification,
)
from ..services.task_state_store import store

router = APIRouter(prefix="/api", tags=["tasks"])


@router.post("/tasks/complete")
def complete_task(req: CompleteTaskRequest):
    subtask = store.get_subtask(req.task_id)
    if not subtask:
        raise HTTPException(
            status_code=404,
            detail=f"Task {req.task_id} not found. Run /api/sequence on its parent issue first.",
        )

    store.set_status(req.task_id, "Done")

    newly_ready = []
    new_notifications = []
    for succ in store.successors(req.task_id):
        if store.get_status(succ.id) == "Done":
            continue
        if store.all_predecessors_done(succ):
            succ_updated = succ.model_copy(update={"status": "Ready"})
            store.set_status(succ.id, "Ready")
            newly_ready.append(succ_updated)
            notif = ready_to_start_notification(succ_updated, req.task_id)
            store.add_notification(notif)
            new_notifications.append(notif)
        else:
            dep_notif = dependency_completed_notification(succ, req.task_id)
            store.add_notification(dep_notif)
            new_notifications.append(dep_notif)

    return {
        "completed_task_id": req.task_id,
        "newly_ready_tasks": [t.model_dump(mode="json") for t in newly_ready],
        "notifications": [n.model_dump(mode="json") for n in new_notifications],
    }
