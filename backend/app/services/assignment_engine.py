"""
Smart assignment for a subtask.

Score components (per candidate member):
  1. Role match — does the member's role cover this subtask type?
  2. Skill-matrix proficiency — Beginner/Intermediate/Expert for the area.
  3. Historical SP delivered in the area — real Jira track record when
     available, curated baseline otherwise.
  4. Seniority — Junior / Mid / Senior / Lead / Principal.
  5. Years of experience.
  6. Remaining capacity — does the subtask fit?
  7. Load penalty — discourage piling onto already-overloaded members.

Returns the best candidate with an `AssignmentSuggestion` that includes a
"Why this assignee?" rationale combining the most salient signals so the UI
can render it verbatim.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..models import RiskLevel, SkillProficiency, TeamMember, TeamPerformance

log = logging.getLogger("sprintpilot.assign")

# Which roles are acceptable for each subtask type, in preference order.
_ROLE_PREFERENCE: dict[str, list[str]] = {
    "Frontend": ["Frontend", "Fullstack"],
    "Backend": ["Backend", "Fullstack"],
    "DB": ["Backend", "Fullstack"],
    "Test": ["QA", "Fullstack"],
    "Analysis": ["Analyst", "Fullstack"],
}

# Which skill-matrix areas count as primary evidence for each subtask type.
_AREA_FOR_TYPE: dict[str, list[str]] = {
    "Frontend": ["Frontend", "UX"],
    "Backend": ["Backend", "API", "Architecture"],
    "DB": ["DB", "Backend"],
    "Test": ["Test", "QA", "Automation"],
    "Analysis": ["Analysis", "BA", "Requirements"],
}

_TITLE_SCORE: dict[str, int] = {
    "Junior": 2,
    "Mid": 5,
    "Senior": 9,
    "Lead": 11,
    "Principal": 13,
}

_LEVEL_LABEL: dict[int, str] = {
    1: "Beginner",
    2: "Working",
    3: "Working",
    4: "Advanced",
    5: "Expert",
}


@dataclass
class AssignmentSuggestion:
    assignee_id: str
    assignee_name: str
    reason: str
    overload_risk: RiskLevel


def _best_proficiency(
    member: TeamMember, type_: str
) -> SkillProficiency | None:
    """Return the proficiency row whose area best matches the subtask type."""
    target_areas = _AREA_FOR_TYPE.get(type_, [type_])
    rows_by_area = {sp.area: sp for sp in member.skill_matrix}
    # Walk target areas in preference order; first hit wins.
    for area in target_areas:
        if area in rows_by_area:
            return rows_by_area[area]
    # Fallback: highest level row in any area
    if member.skill_matrix:
        return max(member.skill_matrix, key=lambda sp: sp.level)
    return None


def _historical_sp_for(
    member: TeamMember,
    type_: str,
    performance: list[TeamPerformance] | None,
) -> int:
    """Real Jira-derived SP delivered in this area if we have data, else baseline."""
    target_areas = _AREA_FOR_TYPE.get(type_, [type_])
    if performance:
        for p in performance:
            if p.member_id == member.id:
                live = sum(p.by_area.get(a, 0) for a in target_areas)
                if live > 0:
                    return live
    # Curated baseline
    baseline = 0
    for sp in member.skill_matrix:
        if sp.area in target_areas:
            baseline += sp.historical_sp
    return baseline


def _score_member(
    member: TeamMember,
    type_: str,
    size: int,
    performance: list[TeamPerformance] | None,
) -> tuple[float, str, SkillProficiency | None, int]:
    role_pref = _ROLE_PREFERENCE.get(type_, [])

    # 1. Role match
    if role_pref and member.role == role_pref[0]:
        role_score = 35
    elif role_pref and member.role in role_pref:
        role_score = 22
    else:
        role_score = 0

    # 2. Skill-matrix proficiency
    skill = _best_proficiency(member, type_)
    proficiency_score = (skill.level * 8) if skill else 0  # 0..40

    # 3. Historical SP delivered in the area
    historical_sp = _historical_sp_for(member, type_, performance)
    # Log-ish scaling: every 8 SP delivered → +2, capped at 18
    historical_score = min(18, int(historical_sp / 8) * 2)

    # 4. Seniority
    title_score = _TITLE_SCORE.get(member.title, 5)

    # 5. Years of experience (capped 0..6)
    exp_score = min(6.0, member.years_experience * 0.6)

    # 6. Capacity remaining
    remaining = max(0, member.capacity - member.current_load)
    fits = remaining >= size
    capacity_score = 0 if not fits else 8 + min(remaining - size, 10)

    # 7. Load penalty (current utilisation)
    load_ratio = member.current_load / max(member.capacity, 1)
    load_penalty = int(load_ratio * 18)

    total = (
        role_score
        + proficiency_score
        + historical_score
        + title_score
        + exp_score
        + capacity_score
        - load_penalty
    )

    reason_parts: list[str] = []
    if role_score >= 35:
        reason_parts.append(f"role {member.role} is a primary match for {type_}")
    elif role_score > 0:
        reason_parts.append(f"role {member.role} can cover {type_}")
    else:
        reason_parts.append(f"{member.role} is a stretch fit for {type_}")

    reason_parts.append(f"{member.title} · {member.years_experience}y exp")

    if skill:
        reason_parts.append(
            f"{skill.area} proficiency: {_LEVEL_LABEL.get(skill.level, 'Working')} "
            f"(level {skill.level}/5)"
        )
    if historical_sp > 0:
        reason_parts.append(f"delivered {historical_sp} SP in {type_} area historically")

    if fits:
        reason_parts.append(f"has {remaining} SP capacity left for this sprint")
    else:
        reason_parts.append(
            f"only {remaining} SP free vs {size} needed — risky overload"
        )

    return total, "; ".join(reason_parts), skill, historical_sp


def _overload_risk(member: TeamMember, size: int) -> RiskLevel:
    projected_load = member.current_load + size
    ratio = projected_load / max(member.capacity, 1)
    if ratio > 1.0:
        return "High"
    if ratio > 0.85:
        return "Medium"
    return "Low"


def assign_subtask(
    type_: str,
    size: int,
    team: list[TeamMember],
    performance: list[TeamPerformance] | None = None,
) -> AssignmentSuggestion:
    if not team:
        return AssignmentSuggestion(
            assignee_id="UNASSIGNED",
            assignee_name="Unassigned",
            reason="No team members available.",
            overload_risk="High",
        )

    scored = [
        (*(_score_member(m, type_, size, performance)), m)
        for m in team
    ]
    # _score_member returns 4 values; pack to (score, reason, skill, historical, member)
    scored.sort(key=lambda x: -x[0])
    best_score, best_reason, best_skill, best_history, best_member = scored[0]
    risk = _overload_risk(best_member, size)

    if risk == "High":
        best_reason += "; assignment is risky — consider redistributing load"

    runners_up = [(s_[4].id, round(s_[0], 1)) for s_ in scored[1:3]]
    log.info(
        "assign type=%s size=%d -> %s (%s) score=%.1f overload=%s skill=%s history=%dSP; runners-up=%s",
        type_, size,
        best_member.id, best_member.name, best_score, risk,
        f"{best_skill.area}={best_skill.level}" if best_skill else "none",
        best_history, runners_up,
    )

    return AssignmentSuggestion(
        assignee_id=best_member.id,
        assignee_name=best_member.name,
        reason=best_reason,
        overload_risk=risk,
    )
