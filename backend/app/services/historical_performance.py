"""
Per-assignee performance derived from historical Jira issues.

For each team member we compute:
  - Total SP delivered across the observed sprint window.
  - Average SP per sprint.
  - How many of their issues carried over (slipped to a later sprint).
  - A simple completion rate (delivered / attempted).
  - SP broken down by inferred area (Backend/Frontend/Test/etc.).

Falls back gracefully when the Jira history is empty or when an assignee has
no record yet — the curated `skill_matrix.historical_sp` baseline is used.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from ..data.mock_team import find_by_id, get_team
from ..models import (
    HistoricalIssue,
    SkillProficiency,
    TeamMember,
    TeamPerformance,
)

log = logging.getLogger("sprintpilot.perf")


_AREA_KEYWORDS: dict[str, list[str]] = {
    "Frontend": ["frontend", "ui", "react", "ux", "view", "screen"],
    "Backend": ["backend", "api", "service", "engine"],
    "DB": ["db", "database", "schema", "migration", "data"],
    "Test": ["test", "qa", "regression", "automation"],
    "Analysis": ["analysis", "requirement", "spec", "discovery"],
    "Performance": ["performance", "latency", "optimize", "scale"],
}


def _infer_area(hist: HistoricalIssue) -> str:
    hay = " ".join([
        hist.title or "",
        hist.description or "",
        " ".join(hist.labels or []),
        " ".join(hist.components or []),
    ]).lower()
    best_area = "Backend"
    best_hits = 0
    for area, keywords in _AREA_KEYWORDS.items():
        hits = sum(1 for k in keywords if k in hay)
        if hits > best_hits:
            best_hits = hits
            best_area = area
    return best_area


def compute_team_performance(
    history: list[HistoricalIssue], sprint_window: int = 10,
) -> list[TeamPerformance]:
    """Aggregate per-member stats from the historical issue pool.

    Members without any historical issues still appear, using their curated
    skill_matrix.historical_sp baseline so the assignment engine has signal.
    """
    by_id: dict[str, list[HistoricalIssue]] = defaultdict(list)
    for h in history:
        if h.assignee_id:
            by_id[h.assignee_id].append(h)

    results: list[TeamPerformance] = []
    for member in get_team():
        items = by_id.get(member.id, [])
        sprints_seen = {h.sprint_name for h in items if h.sprint_name}
        by_area_sp: dict[str, int] = defaultdict(int)
        carry = 0
        delivered_sp = 0
        for h in items:
            delivered_sp += h.actual_size
            area = _infer_area(h)
            by_area_sp[area] += h.actual_size
            if h.carried_over:
                carry += 1

        sprint_count = max(len(sprints_seen), 1) if items else 0
        avg_per_sprint = (delivered_sp / sprint_count) if sprint_count else 0.0
        completion_rate = (
            (len(items) - carry) / len(items) if items else 1.0
        )

        # Refresh proficiency.historical_sp from real data when we have any
        proficiency: list[SkillProficiency] = []
        for sp in member.skill_matrix:
            observed = by_area_sp.get(sp.area, 0)
            proficiency.append(
                SkillProficiency(
                    area=sp.area,
                    level=sp.level,
                    historical_sp=observed if items else sp.historical_sp,
                )
            )

        results.append(
            TeamPerformance(
                member_id=member.id,
                member_name=member.name,
                title=member.title,
                role=member.role,
                years_experience=member.years_experience,
                total_historical_sp=delivered_sp,
                sprints_observed=sprint_count,
                avg_sp_per_sprint=round(avg_per_sprint, 1),
                carried_over_count=carry,
                completion_rate=round(completion_rate, 2),
                by_area=dict(by_area_sp),
                proficiency=proficiency,
            )
        )

    log.info(
        "compute_team_performance: %d members, history pool=%d, assignees_with_data=%d",
        len(results), len(history), len(by_id),
    )
    return results


def lookup_proficiency_for_area(
    member: TeamMember, area: str, performance: list[TeamPerformance] | None = None
) -> SkillProficiency | None:
    """Return the member's skill row for the given area, using live historical
    SP from performance if provided, otherwise the curated baseline."""
    if performance:
        for p in performance:
            if p.member_id == member.id:
                for sp in p.proficiency:
                    if sp.area == area:
                        return sp
    for sp in member.skill_matrix:
        if sp.area == area:
            return sp
    return None


def get_performance_for_member(
    member_id: str, performance: list[TeamPerformance]
) -> TeamPerformance | None:
    for p in performance:
        if p.member_id == member_id:
            return p
    return None
