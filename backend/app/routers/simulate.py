from fastapi import APIRouter, HTTPException

from ..data.mock_team import get_team
from ..models import SimulateRequest, SimulationResult
from ..services.data_provider import fetch_backlog, fetch_history
from ..services.decomposition_engine import decompose
from ..services.predictive_sizing import predict_size
from ..services.sequencing_engine import sequence_decomposition
from ..services.simulation_engine import simulate
from ..services.task_state_store import store

router = APIRouter(prefix="/api", tags=["simulate"])


@router.post("/simulate")
def post_simulate(req: SimulateRequest):
    if not req.issue_keys:
        raise HTTPException(status_code=400, detail="issue_keys is empty")

    backlog = fetch_backlog().issues
    history = fetch_history().issues
    by_key = {i.key: i for i in backlog}
    selected = [by_key[k] for k in req.issue_keys if k in by_key]
    if not selected:
        raise HTTPException(status_code=404, detail="No matching issues")

    team = get_team()
    sequences_by_issue = {}
    for issue in selected:
        existing = store.sequences.get(issue.key)
        if existing:
            sequences_by_issue[issue.key] = existing
        else:
            planning = predict_size(issue, history)
            decomposition = decompose(issue, planning, team)
            seq = sequence_decomposition(decomposition, issue, team)
            sequences_by_issue[issue.key] = seq

    scenarios = simulate(selected, history, sequences_by_issue)
    recommended = next((s.scenario_name for s in scenarios if s.is_recommended), scenarios[0].scenario_name)
    return SimulationResult(scenarios=scenarios, recommended_scenario=recommended).model_dump(mode="json")
