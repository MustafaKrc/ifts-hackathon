from fastapi import APIRouter, HTTPException, Query

from ..services.manager_dashboard_service import build_manager_dashboard

router = APIRouter(prefix="/api", tags=["manager-dashboard"])


@router.get("/manager-dashboard")
def get_manager_dashboard(sprint_id: int = Query(..., gt=0)):
    result = build_manager_dashboard(sprint_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Sprint {sprint_id} not found or could not be loaded",
        )
    return result.model_dump(mode="json")
