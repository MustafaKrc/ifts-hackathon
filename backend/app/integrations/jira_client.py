"""
Read-only Jira REST client for SprintPilot AI.

Reuses the auth pattern from jira_create_tasks_test.py (bearer or basic auth,
optional SSL verification skip for corporate proxy with self-signed certs).

This module makes ONLY GET requests. No POST/PUT/DELETE to Jira ever.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import requests
import urllib3
from requests.auth import HTTPBasicAuth

from ..models import HistoricalIssue, JiraIssue

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger("sprintpilot.jira")


_PRIORITY_MAP = {
    "highest": "Critical",
    "critical": "Critical",
    "blocker": "Critical",
    "high": "High",
    "major": "High",
    "medium": "Medium",
    "minor": "Low",
    "low": "Low",
    "lowest": "Low",
    "trivial": "Low",
}

_STATUS_MAP = {
    "to do": "Backlog",
    "open": "Backlog",
    "backlog": "Backlog",
    "selected for development": "Selected",
    "ready for development": "Selected",
    "ready": "Selected",
    "in progress": "In Progress",
    "in development": "In Progress",
    "in review": "In Progress",
    "code review": "In Progress",
    "done": "Done",
    "closed": "Done",
    "resolved": "Done",
    "blocked": "Blocked",
}


def _map_priority(name: str) -> str:
    return _PRIORITY_MAP.get((name or "").strip().lower(), "Medium")


def _map_status(name: str) -> str:
    return _STATUS_MAP.get((name or "").strip().lower(), "Backlog")


def _parse_date(value) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _parse_datetime(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        # Jira: 2025-05-20T10:34:12.000+0300
        s = str(value).replace("Z", "+0000")
        return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
    except Exception:
        return None


def _extract_dependencies(issuelinks: list) -> list[str]:
    deps = []
    for link in issuelinks or []:
        link_type = (link.get("type") or {}).get("inward", "").lower()
        if "block" in link_type or "depend" in link_type:
            inward = link.get("inwardIssue") or {}
            if inward.get("key"):
                deps.append(inward["key"])
    return deps


def _extract_blocker_reason(issuelinks: list, labels: list[str]) -> Optional[str]:
    for link in issuelinks or []:
        link_type = (link.get("type") or {}).get("inward", "").lower()
        if "block" in link_type and link.get("inwardIssue"):
            blocker_key = link["inwardIssue"].get("key", "?")
            summary = (link["inwardIssue"].get("fields") or {}).get("summary")
            if summary:
                return f"Blocked by {blocker_key}: {summary}"
            return f"Blocked by {blocker_key}"
    if any(l.lower() in ("blocked", "blocker") for l in labels or []):
        return "Marked as blocked via label"
    return None


def _parse_acceptance_criteria(description: str) -> Optional[str]:
    if not description:
        return None
    lower = description.lower()
    for marker in ("acceptance criteria", "acceptance criteria:", "ac:"):
        idx = lower.find(marker)
        if idx != -1:
            return description[idx:].split("\n\n")[0].strip()
    return None


@dataclass
class JiraStatus:
    connected: bool
    reason: Optional[str] = None


class JiraClient:
    def __init__(self):
        self.url = os.environ.get("JIRA_URL", "").rstrip("/")
        self.email = os.environ.get("JIRA_EMAIL", "")
        self.token = os.environ.get("JIRA_API_TOKEN", "")
        self.mode = os.environ.get("JIRA_AUTH_MODE", "bearer").lower()
        self.verify = os.environ.get("JIRA_VERIFY_SSL", "false").lower() == "true"
        self.sp_field = os.environ.get("JIRA_SP_FIELD", "customfield_10028")
        self._cache: dict[str, object] = {}

        if self.mode == "bearer":
            self.auth = None
            self.headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {self.token}",
            }
        else:
            self.auth = HTTPBasicAuth(self.email, self.token)
            self.headers = {"Accept": "application/json"}

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.token)

    def _get(self, path: str, params: dict | None = None) -> dict:
        full_url = f"{self.url}{path}"
        log.info(
            "Jira GET %s params=%s auth_mode=%s verify_ssl=%s",
            full_url, params, self.mode, self.verify,
        )
        try:
            r = requests.get(
                full_url,
                params=params,
                auth=self.auth,
                headers=self.headers,
                verify=self.verify,
                timeout=20,
            )
        except requests.RequestException as e:
            log.error("Jira request failed: %s: %s", type(e).__name__, e)
            raise
        log.info("Jira response %d %s", r.status_code, r.reason)
        if r.status_code >= 400:
            log.error("Jira error body (first 500 chars): %s", r.text[:500])
        r.raise_for_status()
        return r.json()

    def ping(self) -> JiraStatus:
        if not self.is_configured:
            log.warning(
                "Jira not configured: url=%s token_len=%d email=%s",
                bool(self.url), len(self.token), bool(self.email),
            )
            return JiraStatus(connected=False, reason="JIRA_URL or JIRA_API_TOKEN missing")
        try:
            data = self._get("/rest/api/2/myself")
            log.info("Jira ping OK as user=%s", data.get("name") or data.get("displayName"))
            return JiraStatus(connected=True)
        except Exception as e:
            log.error("Jira ping failed: %s", e)
            return JiraStatus(connected=False, reason=str(e)[:140])

    def _search(self, jql: str, fields: str, max_results: int = 50) -> list[dict]:
        cache_key = f"search::{jql}::{fields}::{max_results}"
        if cache_key in self._cache:
            log.info("Jira search cache hit (jql=%s)", jql[:120])
            return self._cache[cache_key]  # type: ignore[return-value]
        log.info("Jira search JQL: %s (fields=%s, maxResults=%d)", jql, fields, max_results)
        data = self._get(
            "/rest/api/2/search",
            params={"jql": jql, "fields": fields, "maxResults": max_results},
        )
        issues = data.get("issues", [])
        log.info("Jira search returned %d issue(s); total=%s", len(issues), data.get("total"))
        self._cache[cache_key] = issues
        return issues

    def fetch_backlog(self, project_key: str) -> list[JiraIssue]:
        fields = (
            "summary,description,priority,status,labels,components,"
            "issuelinks,duedate,assignee," + self.sp_field
        )
        jql = (
            f'project = "{project_key}" AND statusCategory != Done '
            f"ORDER BY priority DESC, duedate ASC"
        )
        log.info("fetch_backlog start project_key=%s", project_key)
        raw_issues = self._search(jql, fields, max_results=50)
        mapped = [self._map_jira_issue(r) for r in raw_issues]
        log.info("fetch_backlog returning %d mapped issues", len(mapped))
        return mapped

    def fetch_historical(
        self, project_key: str, sprint_names: list[str]
    ) -> list[HistoricalIssue]:
        if not sprint_names:
            log.warning("fetch_historical called with empty sprint_names list")
            return []
        fields = (
            "summary,description,priority,status,labels,components,"
            "issuelinks,resolutiondate,created,assignee," + self.sp_field
        )
        sprint_list = ", ".join(f'"{s.strip()}"' for s in sprint_names if s.strip())
        jql = (
            f'project = "{project_key}" AND sprint in ({sprint_list}) '
            f"AND statusCategory = Done"
        )
        log.info(
            "fetch_historical start project_key=%s sprints=%d",
            project_key, len(sprint_names),
        )
        raw_issues = self._search(jql, fields, max_results=100)
        mapped: list[HistoricalIssue] = []
        skipped_no_sp = 0
        for r in raw_issues:
            h = self._map_historical(r)
            if h:
                mapped.append(h)
            else:
                skipped_no_sp += 1
        log.info(
            "fetch_historical mapped %d issues (skipped %d without story points)",
            len(mapped), skipped_no_sp,
        )
        return mapped

    def get_issue(self, key: str) -> Optional[JiraIssue]:
        try:
            data = self._get(f"/rest/api/2/issue/{key}")
            return self._map_jira_issue(data)
        except Exception as e:
            log.error("get_issue(%s) failed: %s", key, e)
            return None

    # ─── Mapping helpers ──────────────────────────────────────────────────

    def _map_jira_issue(self, raw: dict) -> JiraIssue:
        f = raw.get("fields", {}) or {}
        sp_value = f.get(self.sp_field)
        try:
            current_size = int(sp_value) if sp_value is not None else None
        except (TypeError, ValueError):
            current_size = None

        assignee = f.get("assignee") or {}
        labels = list(f.get("labels") or [])
        components = [c.get("name", "") for c in (f.get("components") or [])]
        issuelinks = f.get("issuelinks") or []
        description = f.get("description") or ""

        return JiraIssue(
            id=raw.get("id", raw.get("key", "")),
            key=raw.get("key", ""),
            title=f.get("summary", "") or "",
            description=description,
            current_size=current_size,
            priority=_map_priority((f.get("priority") or {}).get("name", "")),
            status=_map_status((f.get("status") or {}).get("name", "")),
            labels=labels,
            components=components,
            dependencies=_extract_dependencies(issuelinks),
            blocker_reason=_extract_blocker_reason(issuelinks, labels),
            acceptance_criteria=_parse_acceptance_criteria(description),
            deadline=_parse_date(f.get("duedate")),
            assignee_id=assignee.get("name") or assignee.get("accountId"),
            assignee_name=assignee.get("displayName"),
        )

    def _map_historical(self, raw: dict) -> Optional[HistoricalIssue]:
        f = raw.get("fields", {}) or {}
        sp_value = f.get(self.sp_field)
        try:
            actual = int(sp_value) if sp_value is not None else None
        except (TypeError, ValueError):
            actual = None
        if actual is None:
            return None  # skip issues without story points (useless for sizing)

        resolved = _parse_datetime(f.get("resolutiondate"))
        created = _parse_datetime(f.get("created"))
        if resolved and created:
            cycle = max(1, (resolved - created).days)
        else:
            cycle = 7

        labels = list(f.get("labels") or [])
        components = [c.get("name", "") for c in (f.get("components") or [])]
        had_blocker = any(l.lower() in ("blocked", "blocker") for l in labels) or bool(
            _extract_blocker_reason(f.get("issuelinks") or [], labels)
        )
        description = (f.get("description") or "")[:600]

        return HistoricalIssue(
            id=raw.get("id", raw.get("key", "")),
            key=raw.get("key", ""),
            title=f.get("summary", "") or "",
            description=description,
            labels=labels,
            components=components,
            original_size=actual,
            actual_size=actual,
            cycle_time_days=cycle,
            had_blocker=had_blocker,
            carried_over=False,
            priority=_map_priority((f.get("priority") or {}).get("name", "")),
        )


_client_singleton: JiraClient | None = None


def get_client() -> JiraClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = JiraClient()
    return _client_singleton
