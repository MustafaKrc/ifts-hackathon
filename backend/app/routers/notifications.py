from fastapi import APIRouter

from ..models import MarkReadRequest
from ..services.task_state_store import store

router = APIRouter(prefix="/api", tags=["notifications"])


@router.get("/notifications")
def list_notifications():
    return [n.model_dump(mode="json") for n in store.list_notifications()]


@router.post("/notifications/read")
def mark_read(req: MarkReadRequest):
    store.mark_read(req.notification_id)
    return {"ok": True, "notification_id": req.notification_id}
