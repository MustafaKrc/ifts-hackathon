from fastapi import APIRouter

from ..services.data_provider import fetch_backlog

router = APIRouter(prefix="/api", tags=["backlog"])


@router.get("/backlog")
def get_backlog():
    snapshot = fetch_backlog()
    return {
        "issues": [i.model_dump(mode="json") for i in snapshot.issues],
        "source": snapshot.source,
        "fallback_reason": snapshot.reason,
    }
