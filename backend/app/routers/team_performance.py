from fastapi import APIRouter

from ..services.data_provider import fetch_history
from ..services.historical_performance import compute_team_performance

router = APIRouter(prefix="/api", tags=["team"])


@router.get("/team-performance")
def get_team_performance():
    history_snapshot = fetch_history()
    perf = compute_team_performance(history_snapshot.issues)
    return {
        "performance": [p.model_dump(mode="json") for p in perf],
        "history_source": history_snapshot.source,
        "history_count": len(history_snapshot.issues),
    }
