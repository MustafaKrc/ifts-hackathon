"""
Single entry point for fetching backlog + history.

Tries Jira first (read-only). Falls back to local fallback data on any error.
Reports the data source (`jira` or `fallback`) so the UI can display a badge.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from ..data.fallback_history import get_fallback_history
from ..data.fallback_jira import get_fallback_backlog
from ..integrations.jira_client import get_client
from ..models import HistoricalIssue, JiraIssue

log = logging.getLogger("sprintpilot.data")


@dataclass
class BacklogSnapshot:
    issues: list[JiraIssue]
    source: str  # "jira" or "fallback"
    reason: str | None = None


@dataclass
class HistorySnapshot:
    issues: list[HistoricalIssue]
    source: str
    reason: str | None = None


def _project_key() -> str:
    return os.environ.get("JIRA_PROJECT_KEY", "POS")


def _historical_sprints() -> list[str]:
    raw = os.environ.get("JIRA_HISTORICAL_SPRINTS", "")
    return [s.strip() for s in raw.split(",") if s.strip()]


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
        issues = client.fetch_backlog(_project_key())
        if not issues:
            log.warning("Backlog falling back: Jira returned 0 issues for project %s", _project_key())
            return BacklogSnapshot(
                issues=get_fallback_backlog(),
                source="fallback",
                reason="Jira returned 0 issues for the configured project",
            )
        log.info("Backlog from Jira: %d issues for project %s", len(issues), _project_key())
        return BacklogSnapshot(issues=issues, source="jira")
    except Exception as e:
        log.exception("Backlog falling back: Jira fetch raised %s: %s", type(e).__name__, e)
        return BacklogSnapshot(
            issues=get_fallback_backlog(),
            source="fallback",
            reason=f"Jira request failed: {type(e).__name__}: {str(e)[:140]}",
        )


def fetch_history() -> HistorySnapshot:
    client = get_client()
    sprints = _historical_sprints()
    if not client.is_configured or not sprints:
        log.warning(
            "History falling back: configured=%s sprints=%d",
            client.is_configured, len(sprints),
        )
        return HistorySnapshot(
            issues=get_fallback_history(),
            source="fallback",
            reason="JIRA credentials or sprint list missing",
        )
    try:
        issues = client.fetch_historical(_project_key(), sprints)
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
        log.info("History from Jira: %d issues across %d sprint(s)", len(issues), len(sprints))
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
