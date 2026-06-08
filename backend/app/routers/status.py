import os

from fastapi import APIRouter

from ..integrations.jira_client import get_client
from ..services.data_provider import fetch_backlog

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status")
def get_status():
    client = get_client()
    ping = client.ping()
    snapshot = fetch_backlog()
    return {
        "jira_connected": ping.connected,
        "jira_project": os.environ.get("JIRA_PROJECT_KEY", "POS"),
        "jira_reason": ping.reason,
        "openai_configured": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
        "openai_model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        "data_source": snapshot.source,
        "fallback_reason": snapshot.reason,
    }
