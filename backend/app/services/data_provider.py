"""
Single entry point for fetching backlog + history.

Tries Jira first (read-only). Falls back to local fallback data on any error.
Reports the data source (`jira` or `fallback`) so the UI can display a badge.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from ..data.fallback_history import get_fallback_history
from ..data.fallback_jira import get_fallback_backlog
from ..integrations.jira_client import get_client
from ..models import HistoricalIssue, JiraIssue, Sprint

log = logging.getLogger("sprintpilot.data")


@dataclass
class BacklogSnapshot:
    issues: list[JiraIssue]
    source: str  # "jira" or "fallback"
    reason: str | None = None
    sprints: list[Sprint] = field(default_factory=list)


@dataclass
class HistorySnapshot:
    issues: list[HistoricalIssue]
    source: str
    reason: str | None = None


@dataclass
class SprintsSnapshot:
    sprints: list[Sprint]
    source: str
    reason: str | None = None


def _project_key() -> str:
    return os.environ.get("JIRA_PROJECT_KEY", "POS")


def _sprint_window_size() -> int:
    try:
        return int(os.environ.get("JIRA_SPRINT_WINDOW", "10"))
    except ValueError:
        return 10


def _historical_sprints_env() -> list[str]:
    raw = os.environ.get("JIRA_HISTORICAL_SPRINTS", "")
    return [s.strip() for s in raw.split(",") if s.strip()]


def fetch_sprints() -> SprintsSnapshot:
    """Return the most recent N sprints for the project (dynamic discovery)."""
    client = get_client()
    if not client.is_configured:
        return SprintsSnapshot(sprints=[], source="fallback", reason="Jira not configured")
    try:
        sprints = client.fetch_recent_sprints(_project_key(), _sprint_window_size())
        if not sprints:
            return SprintsSnapshot(
                sprints=[], source="fallback",
                reason=f"No sprints discovered for project {_project_key()}",
            )
        return SprintsSnapshot(sprints=sprints, source="jira")
    except Exception as e:
        log.exception("fetch_sprints failed: %s", e)
        return SprintsSnapshot(
            sprints=[], source="fallback",
            reason=f"Sprint discovery failed: {type(e).__name__}: {str(e)[:120]}",
        )


def fetch_backlog() -> BacklogSnapshot:
    client = get_client()
    if not client.is_configured:
        log.warning("Backlog falling back: Jira not configured")
        return BacklogSnapshot(
            issues=get_fallback_backlog(),
            source="fallback",
            reason="JIRA credentials not configured",
        )
    try:
        sprints_snapshot = fetch_sprints()
        # Backlog = project's actual Jira backlog (items not in active/closed sprints).
        # Past sprints are deliberately excluded from this view; they feed the
        # historical similarity engine instead.
        issues = client.fetch_backlog(_project_key())
        if not issues:
            log.warning(
                "Backlog falling back: Jira returned 0 backlog issues for project %s",
                _project_key(),
            )
            return BacklogSnapshot(
                issues=get_fallback_backlog(),
                source="fallback",
                reason="Jira returned 0 backlog issues for the project",
                sprints=sprints_snapshot.sprints,
            )
        log.info(
            "Backlog from Jira: %d issues for project %s (carryovers=%d)",
            len(issues),
            _project_key(),
            sum(1 for i in issues if i.carry_over_count > 0),
        )
        return BacklogSnapshot(
            issues=issues, source="jira", sprints=sprints_snapshot.sprints,
        )
    except Exception as e:
        log.exception("Backlog falling back: Jira fetch raised %s: %s", type(e).__name__, e)
        return BacklogSnapshot(
            issues=get_fallback_backlog(),
            source="fallback",
            reason=f"Jira request failed: {type(e).__name__}: {str(e)[:140]}",
        )


def fetch_history() -> HistorySnapshot:
    client = get_client()
    if not client.is_configured:
        log.warning("History falling back: Jira not configured")
        return HistorySnapshot(
            issues=get_fallback_history(), source="fallback",
            reason="JIRA credentials missing",
        )

    # Prefer dynamic discovery of last N sprints; fall back to the env var override.
    sprint_ids: list[int] = []
    sprint_names: list[str] = []
    try:
        recent = client.fetch_recent_sprints(_project_key(), _sprint_window_size())
        # Exclude active/future sprints from the historical set so similarity
        # uses only completed work.
        closed = [s for s in recent if s.state.lower() == "closed"]
        sprint_ids = [s.id for s in closed] or [s.id for s in recent]
    except Exception as e:
        log.warning("Sprint discovery failed in fetch_history, will try env override: %s", e)
    if not sprint_ids:
        sprint_names = _historical_sprints_env()

    if not sprint_ids and not sprint_names:
        log.warning("History falling back: no sprint filter resolved")
        return HistorySnapshot(
            issues=get_fallback_history(), source="fallback",
            reason="Could not resolve a sprint window for historical similarity",
        )

    try:
        issues = client.fetch_historical(
            _project_key(),
            sprint_names=sprint_names or None,
            sprint_ids=sprint_ids or None,
        )
        if len(issues) < 3:
            log.warning(
                "History falling back: only %d Jira historical issues (need >= 3)",
                len(issues),
            )
            return HistorySnapshot(
                issues=get_fallback_history(),
                source="fallback",
                reason="Too few historical issues returned from Jira for similarity matching",
            )
        log.info(
            "History from Jira: %d issues across %s sprint(s)",
            len(issues), len(sprint_ids) or len(sprint_names),
        )
        return HistorySnapshot(issues=issues, source="jira")
    except Exception as e:
        log.exception("History falling back: Jira historical raised %s: %s", type(e).__name__, e)
        return HistorySnapshot(
            issues=get_fallback_history(),
            source="fallback",
            reason=f"Jira historical fetch failed: {type(e).__name__}: {str(e)[:140]}",
        )


def fetch_issue_by_key(key: str) -> JiraIssue | None:
    snapshot = fetch_backlog()
    for i in snapshot.issues:
        if i.key == key:
            return i
    # Try direct Jira lookup as a last resort
    client = get_client()
    if client.is_configured:
        try:
            return client.get_issue(key)
        except Exception:
            return None
    return None
