from fastapi import APIRouter, HTTPException

from ..data.mock_team import get_team
from ..models import ReviewRequest
from ..services.data_provider import fetch_backlog, fetch_history
from ..services.decomposition_engine import decompose
from ..services.planning_engine import plan_sprint
from ..services.predictive_sizing import predict_size
from ..services.sequencing_engine import sequence_decomposition
from ..services.sprint_health_engine import compute_sprint_health
from ..services.task_state_store import store

router = APIRouter(prefix="/api", tags=["review"])


@router.post("/review")
def post_review(req: ReviewRequest):
    if not req.issue_keys:
        raise HTTPException(status_code=400, detail="issue_keys is empty")

    backlog = fetch_backlog().issues
    history = fetch_history().issues
    by_key = {i.key: i for i in backlog}
    selected = [by_key[k] for k in req.issue_keys if k in by_key]
    if not selected:
        raise HTTPException(status_code=404, detail="No matching issues")

    plannings = plan_sprint(selected, history)
    team = get_team()
    sequences = []
    for issue, planning in zip(selected, plannings):
        existing = store.sequences.get(issue.key)
        if existing:
            sequences.append(existing)
        else:
            decomposition = decompose(issue, planning, team)
            seq = sequence_decomposition(decomposition, issue, team)
            store.save_sequence(seq)
            sequences.append(seq)

    health = compute_sprint_health(selected, plannings, sequences)
    return health.model_dump(mode="json")
