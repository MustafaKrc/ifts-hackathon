from fastapi import APIRouter, HTTPException

from ..models import PlanningRequest
from ..services.data_provider import fetch_backlog, fetch_history
from ..services.planning_engine import plan_sprint

router = APIRouter(prefix="/api", tags=["planning"])


@router.post("/planning")
def post_planning(req: PlanningRequest):
    if not req.issue_keys:
        raise HTTPException(status_code=400, detail="issue_keys is empty")

    backlog_snapshot = fetch_backlog()
    history_snapshot = fetch_history()

    by_key = {i.key: i for i in backlog_snapshot.issues}
    selected = [by_key[k] for k in req.issue_keys if k in by_key]

    if not selected:
        raise HTTPException(
            status_code=404,
            detail=f"None of the requested issues were found in the backlog: {req.issue_keys}",
        )

    results = plan_sprint(selected, history_snapshot.issues)
    return {
        "results": [r.model_dump(mode="json") for r in results],
        "backlog_source": backlog_snapshot.source,
        "history_source": history_snapshot.source,
        "history_count": len(history_snapshot.issues),
    }
