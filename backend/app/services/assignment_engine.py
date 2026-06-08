"""
Smart assignment for a subtask.

Scores each team member by skill match (role compatible with subtask type),
remaining capacity, and current load. Returns the best candidate plus an
overload risk and a one-sentence "Why this assignee?" reason.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..models import RiskLevel, TeamMember

log = logging.getLogger("sprintpilot.assign")

# Which roles are acceptable for each subtask type, in preference order.
_ROLE_PREFERENCE: dict[str, list[str]] = {
    "Frontend": ["Frontend", "Fullstack"],
    "Backend": ["Backend", "Fullstack"],
    "DB": ["Backend", "Fullstack"],
    "Test": ["QA", "Fullstack"],
    "Analysis": ["Analyst", "Fullstack"],
}

_SKILL_HINTS: dict[str, list[str]] = {
    "Frontend": ["Frontend", "React", "UX"],
    "Backend": ["Backend", "API", "Java"],
    "DB": ["DB", "Database", "Performance"],
    "Test": ["Test", "QA", "Automation"],
    "Analysis": ["Analysis", "BA", "Requirements"],
}


@dataclass
class AssignmentSuggestion:
    assignee_id: str
    assignee_name: str
    reason: str
    overload_risk: RiskLevel


def _score_member(member: TeamMember, type_: str, size: int) -> tuple[float, str]:
    role_pref = _ROLE_PREFERENCE.get(type_, [])
    skill_hints = _SKILL_HINTS.get(type_, [])

    role_score = 0
    if role_pref:
        if member.role == role_pref[0]:
            role_score = 50
        elif member.role in role_pref:
            role_score = 30

    skill_overlap = sum(
        1 for s in member.skills if s.lower() in [h.lower() for h in skill_hints]
    )
    skill_score = skill_overlap * 8

    remaining = max(0, member.capacity - member.current_load)
    fits = remaining >= size
    capacity_score = 0 if not fits else 15 + min(remaining - size, 10)

    load_ratio = member.current_load / max(member.capacity, 1)
    load_penalty = int(load_ratio * 20)

    reason_parts = []
    if role_score >= 50:
        reason_parts.append(f"role {member.role} is a primary match for {type_}")
    elif role_score >= 30:
        reason_parts.append(f"role {member.role} can cover {type_}")
    if skill_overlap:
        reason_parts.append(f"{skill_overlap} matching skills")
    if fits:
        reason_parts.append(f"has {remaining} SP capacity remaining")
    else:
        reason_parts.append("limited remaining capacity — overload risk")

    return (role_score + skill_score + capacity_score - load_penalty,
            "; ".join(reason_parts))


def _overload_risk(member: TeamMember, size: int) -> RiskLevel:
    projected_load = member.current_load + size
    ratio = projected_load / max(member.capacity, 1)
    if ratio > 1.0:
        return "High"
    if ratio > 0.85:
        return "Medium"
    return "Low"


def assign_subtask(
    type_: str, size: int, team: list[TeamMember]
) -> AssignmentSuggestion:
    if not team:
        return AssignmentSuggestion(
            assignee_id="UNASSIGNED",
            assignee_name="Unassigned",
            reason="No team members available.",
            overload_risk="High",
        )

    scored = sorted(
        ((_score_member(m, type_, size)[0], m, _score_member(m, type_, size)[1]) for m in team),
        key=lambda x: -x[0],
    )
    best_score, best_member, reason = scored[0]
    risk = _overload_risk(best_member, size)

    if risk == "High":
        reason += "; assignment is risky — consider redistributing load"

    log.info(
        "assign type=%s size=%d -> %s (%s) score=%.1f overload=%s; runners-up=%s",
        type_, size, best_member.id, best_member.name, best_score, risk,
        [(m.id, round(s, 1)) for s, m, _ in scored[1:3]],
    )

    return AssignmentSuggestion(
        assignee_id=best_member.id,
        assignee_name=best_member.name,
        reason=reason,
        overload_risk=risk,
    )
