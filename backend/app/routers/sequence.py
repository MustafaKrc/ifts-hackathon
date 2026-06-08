from fastapi import APIRouter, HTTPException

from ..data.mock_team import get_team
from ..models import SequenceRequest
from ..services.data_provider import fetch_history, fetch_issue_by_key
from ..services.decomposition_engine import decompose
from ..services.predictive_sizing import predict_size
from ..services.sequencing_engine import sequence_decomposition
from ..services.task_state_store import store

router = APIRouter(prefix="/api", tags=["sequence"])


@router.post("/sequence")
def post_sequence(req: SequenceRequest):
    issue = fetch_issue_by_key(req.issue_key)
    if not issue:
        raise HTTPException(status_code=404, detail=f"Issue {req.issue_key} not found")

    history = fetch_history().issues
    planning = predict_size(issue, history)
    team = get_team()
    decomposition = decompose(issue, planning, team)
    sequence = sequence_decomposition(decomposition, issue, team)
    store.save_sequence(sequence)
    return sequence.model_dump(mode="json")
