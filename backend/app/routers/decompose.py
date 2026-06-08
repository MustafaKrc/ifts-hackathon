from fastapi import APIRouter, HTTPException

from ..data.mock_team import get_team
from ..models import DecomposeRequest
from ..services.data_provider import fetch_history, fetch_issue_by_key
from ..services.decomposition_engine import decompose
from ..services.historical_performance import compute_team_performance
from ..services.predictive_sizing import predict_size

router = APIRouter(prefix="/api", tags=["decompose"])


@router.post("/decompose")
def post_decompose(req: DecomposeRequest):
    issue = fetch_issue_by_key(req.issue_key)
    if not issue:
        raise HTTPException(status_code=404, detail=f"Issue {req.issue_key} not found")

    history = fetch_history().issues
    performance = compute_team_performance(history)
    planning = predict_size(issue, history)
    result = decompose(issue, planning, get_team(), performance)
    return result.model_dump(mode="json")
