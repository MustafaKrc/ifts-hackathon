from fastapi import APIRouter

from ..data.mock_team import get_team

router = APIRouter(prefix="/api", tags=["team"])


@router.get("/team")
def list_team():
    return [m.model_dump(mode="json") for m in get_team()]
