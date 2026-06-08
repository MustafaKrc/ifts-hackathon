from fastapi import APIRouter


router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """Return a lightweight API status response for smoke tests."""
    return {
        "status": "ok",
        "service": "Turkcell Customer Experience API",
        "database": "sqlite",
    }
