"""
Manager Dashboard service — sprint-level retrospective for any chosen sprint.

For a given sprint id, queries every issue that was in that sprint and computes:

  - Planned vs Delivered story points + delivery rate
  - Carry-over count and points (issues not finished by sprint close)
  - Cross-sprint transition rate (avg number of follow-on sprints per missed issue)
  - Sprint health score (1-100) tailored for review (not planning)
  - Top achievements (largest delivered items)
  - Top misses (largest items that slipped)
  - Per-assignee planned vs delivered breakdown
  - "What did we achieve" executive narrative (LLM-generated, deterministic fallback)
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from typing import Optional

from ..integrations.jira_client import get_client
from ..models import (
    DashboardAssignee,
    DashboardIssue,
    ManagerDashboardResponse,
    Sprint,
)
from .openai_priority_advisor import _disable, _openai_disabled_reason  # type: ignore[attr-defined]

log = logging.getLogger("sprintpilot.manager")


# ─── Fetching ───────────────────────────────────────────────────

def _project_key() -> str:
    return os.environ.get("JIRA_PROJECT_KEY", "POS")


def _fetch_sprint(sprint_id: int) -> Optional[Sprint]:
    try:
        client = get_client()
        # Use the cached recent-sprints fetcher first
        for s in client.fetch_recent_sprints(_project_key(), 50):
            if s.id == sprint_id:
                return s
    except Exception as e:
        log.warning("fetch_sprint(%s) recent lookup failed: %s", sprint_id, e)
    # Fallback: direct API
    try:
        data = client._get(f"/rest/agile/1.0/sprint/{sprint_id}")
        return Sprint(
            id=data.get("id", sprint_id),
            name=data.get("name", f"Sprint {sprint_id}"),
            state=(data.get("state") or "closed").lower(),
            start_date=None,
            end_date=None,
            board_id=data.get("originBoardId"),
        )
    except Exception as e:
        log.error("fetch_sprint(%s) direct lookup failed: %s", sprint_id, e)
        return None


def _fetch_sprint_issues(sprint_id: int) -> list[dict]:
    client = get_client()
    fields = (
        "summary,description,priority,status,labels,components,"
        f"issuelinks,duedate,resolutiondate,created,assignee,{client.sp_field},{client.sprint_field}"
    )
    jql = f'project = "{_project_key()}" AND sprint = {sprint_id}'
    return client._search(jql, fields, max_results=200)


# ─── Aggregation ───────────────────────────────────────────────

def _build_dashboard_issues_and_stats(sprint_id: int, raw_issues: list[dict]):
    """Map raw Jira issues into dashboard issues + aggregate counters."""
    client = get_client()
    dashboard_issues: list[DashboardIssue] = []
    planned_points = 0
    delivered_points = 0
    carry_over_points = 0
    by_assignee_planned: dict[tuple[str, str], int] = defaultdict(int)
    by_assignee_delivered: dict[tuple[str, str], int] = defaultdict(int)
    by_assignee_planned_count: dict[tuple[str, str], int] = defaultdict(int)
    by_assignee_delivered_count: dict[tuple[str, str], int] = defaultdict(int)
    follow_on_counts: list[int] = []

    for raw in raw_issues:
        ji = client._map_jira_issue(raw)
        sp = ji.current_size or 0
        is_delivered = ji.status == "Done"
        # Count how many sprints AFTER the selected one this issue lives in.
        # A high count means the issue keeps slipping forward.
        follow_on = sum(
            1 for s in (ji.sprint_history or []) if s.id and s.id > sprint_id
        )
        if not is_delivered:
            follow_on_counts.append(follow_on)
        planned_points += sp
        if is_delivered:
            delivered_points += sp
        else:
            carry_over_points += sp

        key = (ji.assignee_id or "UNASSIGNED", ji.assignee_name or "Unassigned")
        by_assignee_planned[key] += sp
        by_assignee_planned_count[key] += 1
        if is_delivered:
            by_assignee_delivered[key] += sp
            by_assignee_delivered_count[key] += 1

        dashboard_issues.append(
            DashboardIssue(
                key=ji.key,
                title=ji.title,
                points=sp,
                status=ji.status,
                assignee_name=ji.assignee_name,
                is_delivered=is_delivered,
                follow_on_sprints=follow_on,
                blocker_reason=ji.blocker_reason,
            )
        )

    per_assignee: list[DashboardAssignee] = []
    for (aid, aname), planned in by_assignee_planned.items():
        delivered = by_assignee_delivered[(aid, aname)]
        ip = by_assignee_planned_count[(aid, aname)]
        idl = by_assignee_delivered_count[(aid, aname)]
        rate = (delivered / planned) if planned else 0.0
        per_assignee.append(
            DashboardAssignee(
                assignee_id=aid,
                assignee_name=aname,
                planned_points=planned,
                delivered_points=delivered,
                issues_planned=ip,
                issues_delivered=idl,
                delivery_rate=round(rate, 2),
            )
        )
    per_assignee.sort(key=lambda a: -a.planned_points)

    return (
        dashboard_issues,
        planned_points,
        delivered_points,
        carry_over_points,
        per_assignee,
        follow_on_counts,
    )


# ─── Health score ──────────────────────────────────────────────

def _compute_health(
    planned_points: int,
    delivered_points: int,
    carry_over_count: int,
    total_issues: int,
    follow_on_counts: list[int],
) -> tuple[int, str]:
    if planned_points <= 0:
        return 50, "Risky"

    delivery_rate = delivered_points / planned_points
    score = int(round(delivery_rate * 100))

    # Carry-over penalty (scaled by sprint size)
    if total_issues > 0:
        carry_ratio = carry_over_count / total_issues
        score -= int(carry_ratio * 30)

    # Cross-sprint transition penalty — items that slipped MULTIPLE sprints forward
    if follow_on_counts:
        avg_follow = sum(follow_on_counts) / len(follow_on_counts)
        if avg_follow >= 2:
            score -= 10
        elif avg_follow >= 1:
            score -= 5

    score = max(1, min(100, score))
    if score >= 80:
        verdict = "Healthy"
    elif score >= 55:
        verdict = "Risky"
    else:
        verdict = "Overcommitted"
    return score, verdict


# ─── Narrative ──────────────────────────────────────────────────

_NARRATIVE_SYSTEM = (
    "You are an Agile delivery manager writing an executive sprint review. "
    "Be concise, professional, and action-oriented. Use Turkish if the issue "
    "titles are predominantly Turkish; otherwise English. Output 2 short "
    "paragraphs: (1) 'What we achieved' celebrating real wins with specific "
    "issue keys + SP; (2) 'Key misses + 1-2 lessons learned' citing real "
    "issues by key. No fluff, no apologies."
)


def _llm_narrative(payload: dict) -> Optional[str]:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key or _openai_disabled_reason:
        return None
    model = os.environ.get("OPENAI_MODEL", "gpt-5.4")
    try:
        from openai import OpenAI

        client = OpenAI(api_key=key, max_retries=0)
        response = client.chat.completions.create(
            model=model,
            temperature=0.4,
            messages=[
                {"role": "system", "content": _NARRATIVE_SYSTEM},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            timeout=20,
        )
        text = response.choices[0].message.content or ""
        log.info("manager narrative LLM tokens=%s", getattr(response.usage, "total_tokens", "?"))
        return text.strip()
    except Exception as e:
        name = type(e).__name__
        log.error("manager narrative LLM failed: %s: %s", name, str(e)[:200])
        if name in {
            "RateLimitError", "AuthenticationError", "NotFoundError",
            "PermissionDeniedError", "BadRequestError",
        }:
            _disable(f"{name}: {str(e)[:120]}")
        return None


def _deterministic_narrative(
    sprint_name: str,
    planned: int,
    delivered: int,
    carry: int,
    rate: float,
    top_ach: list[DashboardIssue],
    top_miss: list[DashboardIssue],
    health_score: int,
    verdict: str,
) -> str:
    rate_pct = int(rate * 100)
    achievements = (
        ", ".join(f"{i.key} ({i.points}SP)" for i in top_ach[:3])
        or "limited delivery this sprint"
    )
    misses = (
        ", ".join(f"{i.key} ({i.points}SP)" for i in top_miss[:3])
        or "no notable misses"
    )
    return (
        f"What we achieved in {sprint_name}: delivered {delivered} of "
        f"{planned} planned SP ({rate_pct}%) with verdict {verdict} "
        f"({health_score}/100). Top wins: {achievements}.\n\n"
        f"Key misses and lessons: {carry} item(s) carried over; biggest "
        f"unfinished: {misses}. Recommendation: re-plan unfinished work "
        f"into next sprint with stricter scope guardrails and unblock the "
        f"oldest carry-overs first."
    )


# ─── Public entry ──────────────────────────────────────────────

def build_manager_dashboard(sprint_id: int) -> Optional[ManagerDashboardResponse]:
    sprint = _fetch_sprint(sprint_id)
    if sprint is None:
        log.warning("build_manager_dashboard: sprint %s not found", sprint_id)
        return None
    try:
        raw_issues = _fetch_sprint_issues(sprint_id)
    except Exception as e:
        log.exception("build_manager_dashboard: fetch issues failed for %s: %s", sprint_id, e)
        return None

    (
        issues,
        planned_points,
        delivered_points,
        carry_over_points,
        per_assignee,
        follow_on_counts,
    ) = _build_dashboard_issues_and_stats(sprint_id, raw_issues)

    total_issues = len(issues)
    delivered_issues = sum(1 for i in issues if i.is_delivered)
    carry_over_count = total_issues - delivered_issues
    delivery_rate = (delivered_points / planned_points) if planned_points else 0.0
    carry_over_rate = (carry_over_count / total_issues) if total_issues else 0.0
    cross_sprint_rate = (
        sum(follow_on_counts) / len(follow_on_counts) if follow_on_counts else 0.0
    )
    health_score, verdict = _compute_health(
        planned_points, delivered_points, carry_over_count, total_issues, follow_on_counts
    )

    top_achievements = sorted(
        (i for i in issues if i.is_delivered), key=lambda i: -i.points
    )[:5]
    top_misses = sorted(
        (i for i in issues if not i.is_delivered), key=lambda i: (-i.follow_on_sprints, -i.points)
    )[:5]

    narrative_payload = {
        "sprint": sprint.name,
        "sprint_state": sprint.state,
        "planned_points": planned_points,
        "delivered_points": delivered_points,
        "delivery_rate": round(delivery_rate, 2),
        "total_issues": total_issues,
        "delivered_issues": delivered_issues,
        "carry_over_count": carry_over_count,
        "cross_sprint_transition_rate": round(cross_sprint_rate, 2),
        "health_score": health_score,
        "verdict": verdict,
        "top_achievements": [
            {"key": i.key, "title": i.title, "points": i.points} for i in top_achievements
        ],
        "top_misses": [
            {
                "key": i.key,
                "title": i.title,
                "points": i.points,
                "follow_on_sprints": i.follow_on_sprints,
                "blocker": i.blocker_reason,
            }
            for i in top_misses
        ],
        "per_assignee": [
            {
                "name": a.assignee_name,
                "planned": a.planned_points,
                "delivered": a.delivered_points,
            }
            for a in per_assignee[:8]
        ],
    }
    narrative = _llm_narrative(narrative_payload)
    used_openai = bool(narrative)
    if not narrative:
        narrative = _deterministic_narrative(
            sprint.name,
            planned_points,
            delivered_points,
            carry_over_count,
            delivery_rate,
            top_achievements,
            top_misses,
            health_score,
            verdict,
        )

    log.info(
        "manager_dashboard sprint=%s state=%s planned=%dSP delivered=%dSP rate=%.0f%% carry=%d health=%d/%s",
        sprint.name, sprint.state, planned_points, delivered_points,
        delivery_rate * 100, carry_over_count, health_score, verdict,
    )

    return ManagerDashboardResponse(
        sprint_id=sprint.id,
        sprint_name=sprint.name,
        sprint_state=sprint.state,
        start_date=sprint.start_date,
        end_date=sprint.end_date,
        planned_points=planned_points,
        delivered_points=delivered_points,
        delivery_rate=round(delivery_rate, 2),
        planned_issues=total_issues,
        delivered_issues=delivered_issues,
        carry_over_count=carry_over_count,
        carry_over_points=carry_over_points,
        carry_over_rate=round(carry_over_rate, 2),
        cross_sprint_transition_rate=round(cross_sprint_rate, 2),
        health_score=health_score,
        health_verdict=verdict,  # type: ignore[arg-type]
        per_assignee=per_assignee[:8],
        top_achievements=top_achievements,
        top_misses=top_misses,
        narrative=narrative,
        used_openai=used_openai,
        source="jira",
    )
