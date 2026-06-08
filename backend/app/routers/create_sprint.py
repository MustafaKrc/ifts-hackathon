"""Mock 'Create Sprint' endpoint.

This endpoint NEVER calls the Jira write API. It accepts a set of issue keys,
synthesises what the next sprint would look like (name derived from the most
recent real sprint + 1), and returns a confirmation payload that the frontend
displays to the user. The whole point is to make the demo feel like a real
sprint commit without touching Jira state.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime

from fastapi import APIRouter, HTTPException

from ..models import CreateSprintRequest, CreateSprintResponse
from ..services.data_provider import fetch_backlog, fetch_sprints

log = logging.getLogger("sprintpilot.create_sprint")

router = APIRouter(prefix="/api", tags=["create-sprint"])


def _next_sprint_name(default_seed: int = 225) -> str:
    """Pick a plausible 'next sprint' name without ever creating one in Jira."""
    try:
        sprints = fetch_sprints().sprints
        if sprints:
            top_id = max(s.id for s in sprints)
            # Find the active sprint to derive number
            active = next((s for s in sprints if s.state == "active"), None)
            if active and active.name:
                # If name ends with a number, increment it
                tail = active.name.strip().split()[-1]
                if tail.isdigit():
                    return f"Sprint {int(tail) + 1}"
            return f"Sprint {default_seed}"
    except Exception as e:
        log.warning("Failed to derive next sprint name: %s", e)
    return f"Sprint {default_seed}"


@router.post("/create-sprint", response_model=CreateSprintResponse)
def post_create_sprint(req: CreateSprintRequest) -> CreateSprintResponse:
    if not req.issue_keys:
        raise HTTPException(status_code=400, detail="issue_keys is empty")

    # Look up the backlog to sum up planned points for the selected issues
    backlog = fetch_backlog().issues
    by_key = {i.key: i for i in backlog}
    matched = [by_key[k] for k in req.issue_keys if k in by_key]
    total_points = sum((i.current_size or 0) for i in matched)

    sprint_name = req.sprint_name or _next_sprint_name()
    # Synthetic id with a clear MOCK marker (timestamp seconds + tag)
    sprint_id = -int(datetime.utcnow().strftime("%y%m%d%H%M%S")) - random.randint(0, 99)

    message = (
        f"{sprint_name} created with {len(req.issue_keys)} task(s) totalling "
        f"{total_points} SP. (Mock — Jira state is unchanged.)"
    )
    log.info(
        "create-sprint MOCK sprint_name=%s sprint_id=%s issue_count=%d total_points=%d goal=%r",
        sprint_name, sprint_id, len(req.issue_keys), total_points, req.goal,
    )

    return CreateSprintResponse(
        ok=True,
        mock=True,
        sprint_id=sprint_id,
        sprint_name=sprint_name,
        issue_count=len(req.issue_keys),
        total_points=total_points,
        issue_keys=req.issue_keys,
        message=message,
    )
