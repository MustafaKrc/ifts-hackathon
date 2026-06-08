from fastapi import APIRouter

from ..data.mock_team import get_team
from ..models import AutoSprintRequest
from ..services.auto_sprint_engine import auto_build_sprint
from ..services.data_provider import fetch_backlog, fetch_history
from ..services.historical_performance import compute_team_performance

router = APIRouter(prefix="/api", tags=["auto-sprint"])


@router.post("/auto-sprint")
def post_auto_sprint(req: AutoSprintRequest | None = None):
    req = req or AutoSprintRequest()
    backlog_snapshot = fetch_backlog()
    history_snapshot = fetch_history()
    performance = compute_team_performance(history_snapshot.issues)
    team = get_team()
    result = auto_build_sprint(
        backlog=backlog_snapshot.issues,
        history=history_snapshot.issues,
        team=team,
        performance=performance,
        target_capacity=req.target_capacity,
        max_tasks=req.max_tasks,
    )
    payload = result.model_dump(mode="json")
    payload["backlog_source"] = backlog_snapshot.source
    payload["history_source"] = history_snapshot.source
    return payload
