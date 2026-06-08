from fastapi import APIRouter

from ..services.data_provider import fetch_sprints

router = APIRouter(prefix="/api", tags=["sprints"])


@router.get("/sprints")
def list_sprints():
    snapshot = fetch_sprints()
    return {
        "sprints": [s.model_dump(mode="json") for s in snapshot.sprints],
        "source": snapshot.source,
        "reason": snapshot.reason,
    }
