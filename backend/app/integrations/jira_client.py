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

from ..models import HistoricalIssue, JiraIssue, Sprint, SprintRef

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


def _parse_sprint_list(field_value) -> list[SprintRef]:
    """Return the FULL sprint membership list for an issue (history).

    Handles two Jira representations:
      - Newer: list of dicts with id/name/state.
      - Older: list of strings like
        "com.atlassian.greenhopper.service.sprint.Sprint@xxxx[id=12345,name=Sprint 214,state=ACTIVE,...]"
    """
    if not field_value:
        return []

    out: list[SprintRef] = []
    seen: set[int] = set()
    items = field_value if isinstance(field_value, list) else [field_value]
    for item in items:
        if isinstance(item, dict):
            sid = item.get("id")
            name = item.get("name")
            state = (item.get("state") or "closed").lower()
            if sid is None or not name:
                continue
            try:
                sid_int = int(sid)
            except (TypeError, ValueError):
                continue
            if sid_int in seen:
                continue
            seen.add(sid_int)
            out.append(SprintRef(id=sid_int, name=str(name), state=state))
        elif isinstance(item, str):
            try:
                bracket = item[item.index("[") + 1 : item.rindex("]")]
                parts = dict(p.split("=", 1) for p in bracket.split(",") if "=" in p)
                sid_raw = parts.get("id")
                name = parts.get("name")
                state = (parts.get("state") or "closed").lower()
                if sid_raw and name:
                    sid_int = int(sid_raw)
                    if sid_int in seen:
                        continue
                    seen.add(sid_int)
                    out.append(SprintRef(id=sid_int, name=name, state=state))
            except (ValueError, IndexError):
                continue
    # Sort: active first, then by id desc (newest closed first)
    out.sort(key=lambda s: (0 if s.state == "active" else 1, -s.id))
    return out


def _pick_primary_sprint(
    history: list[SprintRef],
) -> tuple[Optional[int], Optional[str], Optional[str]]:
    if not history:
        return None, None, None
    primary = history[0]
    return primary.id, primary.name, primary.state


def _carry_over_count(history: list[SprintRef]) -> int:
    """How many times has this issue slipped from a closed sprint?"""
    return sum(1 for s in history if s.state == "closed")


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
        # Sprint field on issues. Older Jira: customfield_10020. Newer Cloud sometimes 10010.
        self.sprint_field = os.environ.get("JIRA_SPRINT_FIELD", "customfield_10020")
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

    def _backlog_fields(self) -> str:
        return (
            "summary,description,priority,status,labels,components,"
            f"issuelinks,duedate,assignee,{self.sp_field},{self.sprint_field}"
        )

    def fetch_boards(self, project_key: str) -> list[dict]:
        cache_key = f"boards::{project_key}"
        if cache_key in self._cache:
            return self._cache[cache_key]  # type: ignore[return-value]
        data = self._get(
            "/rest/agile/1.0/board",
            params={"projectKeyOrId": project_key, "type": "scrum", "maxResults": 50},
        )
        boards = data.get("values", [])
        log.info("fetch_boards %s -> %d board(s)", project_key, len(boards))
        self._cache[cache_key] = boards
        return boards

    def fetch_recent_sprints(self, project_key: str, limit: int = 10) -> list[Sprint]:
        """Auto-discover the last N sprints (by id desc) for the given project.

        Walks through every Scrum board found for the project, lists their
        sprints (active + closed + future, paginated), and returns the top
        `limit` by id descending. Result is cached for the process lifetime.
        """
        cache_key = f"recent_sprints::{project_key}::{limit}"
        if cache_key in self._cache:
            return self._cache[cache_key]  # type: ignore[return-value]

        boards = self.fetch_boards(project_key)
        if not boards:
            log.warning("fetch_recent_sprints: no boards for project %s", project_key)
            return []

        seen_ids: set[int] = set()
        collected: list[Sprint] = []
        for b in boards:
            board_id = b.get("id")
            if not board_id:
                continue
            start_at = 0
            while True:
                try:
                    data = self._get(
                        f"/rest/agile/1.0/board/{board_id}/sprint",
                        params={
                            "state": "active,closed,future",
                            "startAt": start_at,
                            "maxResults": 50,
                        },
                    )
                except Exception as e:
                    log.warning("Sprint list failed for board %s: %s", board_id, e)
                    break
                values = data.get("values", [])
                for s in values:
                    sid = s.get("id")
                    if sid in seen_ids:
                        continue
                    seen_ids.add(sid)
                    collected.append(
                        Sprint(
                            id=sid,
                            name=s.get("name", f"Sprint {sid}"),
                            state=s.get("state", "closed"),
                            start_date=_parse_date(s.get("startDate")),
                            end_date=_parse_date(s.get("endDate") or s.get("completeDate")),
                            board_id=board_id,
                        )
                    )
                if data.get("isLast", True) or len(values) == 0:
                    break
                start_at += 50

        collected.sort(key=lambda s: s.id, reverse=True)
        top = collected[:limit]
        log.info(
            "fetch_recent_sprints %s collected=%d returning top %d (ids=%s)",
            project_key, len(collected), len(top), [s.id for s in top],
        )
        self._cache[cache_key] = top
        return top

    def fetch_backlog(self, project_key: str) -> list[JiraIssue]:
        """Return the project backlog (items not in any active/closed sprint).

        Strategy:
          1. Try the Agile API `/board/{id}/backlog`. This is what Jira's
             "Backlog" tab shows: unscheduled work + future-sprint items,
             but never the active sprint or closed sprints.
          2. If no Scrum board is found, fall back to a JQL search with
             `sprint is EMPTY`.
        """
        fields = self._backlog_fields()
        log.info("fetch_backlog start project_key=%s", project_key)

        boards = self.fetch_boards(project_key)
        if boards:
            board_id = boards[0].get("id")
            try:
                data = self._get(
                    f"/rest/agile/1.0/board/{board_id}/backlog",
                    params={"fields": fields, "maxResults": 100},
                )
                raw_issues = data.get("issues", [])
                mapped = [self._map_jira_issue(r) for r in raw_issues]
                log.info(
                    "fetch_backlog (agile /backlog) board=%s returning %d issues",
                    board_id, len(mapped),
                )
                return mapped
            except Exception as e:
                log.warning(
                    "Agile /backlog fetch failed for board %s: %s — falling back to JQL",
                    board_id, e,
                )

        jql = (
            f'project = "{project_key}" AND sprint is EMPTY '
            f"AND statusCategory != Done ORDER BY priority DESC, duedate ASC"
        )
        raw_issues = self._search(jql, fields, max_results=100)
        mapped = [self._map_jira_issue(r) for r in raw_issues]
        log.info("fetch_backlog (JQL fallback) returning %d issues", len(mapped))
        return mapped

    def fetch_historical(
        self,
        project_key: str,
        sprint_names: list[str] | None = None,
        sprint_ids: list[int] | None = None,
    ) -> list[HistoricalIssue]:
        if not sprint_names and not sprint_ids:
            log.warning("fetch_historical called with empty sprint filters")
            return []
        fields = (
            "summary,description,priority,status,labels,components,"
            f"issuelinks,resolutiondate,created,assignee,{self.sp_field},{self.sprint_field}"
        )
        if sprint_ids:
            sprint_clause = "(" + ", ".join(str(i) for i in sprint_ids) + ")"
        else:
            sprint_clause = "(" + ", ".join(
                f'"{s.strip()}"' for s in sprint_names or [] if s.strip()
            ) + ")"
        jql = (
            f'project = "{project_key}" AND sprint in {sprint_clause} '
            f"AND statusCategory = Done"
        )
        log.info(
            "fetch_historical start project_key=%s sprints=%s",
            project_key,
            sprint_ids or sprint_names,
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
        sprint_history = _parse_sprint_list(f.get(self.sprint_field))
        sprint_id, sprint_name, sprint_state = _pick_primary_sprint(sprint_history)

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
            sprint_id=sprint_id,
            sprint_name=sprint_name,
            sprint_state=sprint_state,
            sprint_history=sprint_history,
            carry_over_count=_carry_over_count(sprint_history),
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
        assignee = f.get("assignee") or {}
        sprint_history = _parse_sprint_list(f.get(self.sprint_field))
        # If the issue was in more than one closed sprint, it carried over.
        carried_over = sum(1 for s in sprint_history if s.state == "closed") > 1
        sprint_name = sprint_history[0].name if sprint_history else None

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
            carried_over=carried_over,
            priority=_map_priority((f.get("priority") or {}).get("name", "")),
            assignee_id=assignee.get("name") or assignee.get("accountId"),
            assignee_name=assignee.get("displayName"),
            sprint_name=sprint_name,
        )


_client_singleton: JiraClient | None = None


def get_client() -> JiraClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = JiraClient()
    return _client_singleton
