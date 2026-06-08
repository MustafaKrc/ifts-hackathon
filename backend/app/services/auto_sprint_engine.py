"""
Auto-build the next sprint from the Jira backlog with zero manual selection.

Pipeline (one HTTP request → coherent sprint plan):

  1. Rank every backlog item by an inclusion score:
       - Priority (Critical/High/Medium/Low)
       - Carry-over count (slipped items get priority attention)
       - Deadline urgency
       - Blockers penalised
       - Smaller items rewarded for fit
  2. Cap consideration to the top 30 candidates so we don't size 1400 issues.
  3. Predict size for each candidate using the kNN similarity engine (history).
  4. Greedy-select items into the sprint until either:
       - We hit ~85% of total team free capacity, or
       - We reach the max_tasks safety cap (default 15).
  5. Decompose each selected item via the LLM-aware engine (deterministic fall-back).
  6. Return everything the frontend needs to skip straight to /planning.

OpenAI cost is bounded: at most `max_tasks` decomposition calls. With the shared
circuit breaker, a single 429 short-circuits the rest of the run instantly.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from ..data.mock_team import get_team
from ..models import (
    AutoSprintItem,
    AutoSprintResult,
    JiraIssue,
    PlanningResult,
    TeamMember,
    TeamPerformance,
    HistoricalIssue,
)
from .decomposition_engine import decompose
from .predictive_sizing import predict_size

log = logging.getLogger("sprintpilot.auto")

_PRIORITY_WEIGHT = {"Critical": 45, "High": 30, "Medium": 14, "Low": 4}


def _free_capacity(team: list[TeamMember]) -> int:
    return sum(max(0, m.capacity - m.current_load) for m in team)


def _inclusion_score(
    issue: JiraIssue, planning: Optional[PlanningResult] = None
) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0

    # Priority
    pw = _PRIORITY_WEIGHT.get(issue.priority, 5)
    score += pw
    if issue.priority in ("Critical", "High"):
        reasons.append(f"{issue.priority} priority (+{pw})")

    # Carryover — slipped items deserve attention
    if issue.carry_over_count > 0:
        carry_bonus = min(40, 14 * issue.carry_over_count)
        score += carry_bonus
        reasons.append(
            f"slipped {issue.carry_over_count} sprint(s) (+{carry_bonus})"
        )

    # Deadline urgency
    if issue.deadline:
        days_left = (issue.deadline - date.today()).days
        if days_left <= 3:
            score += 28
            reasons.append("deadline ≤3 days (+28)")
        elif days_left <= 7:
            score += 18
            reasons.append("deadline ≤7 days (+18)")
        elif days_left <= 14:
            score += 8
            reasons.append("deadline ≤14 days (+8)")

    # Blocker penalty — don't pile up blocked work
    if issue.blocker_reason:
        score -= 18
        reasons.append("blocked (-18)")

    # AC missing isn't a blocker but adds uncertainty
    if not issue.acceptance_criteria:
        score -= 4

    # Size fit
    if planning is not None:
        if planning.predicted_size <= 3:
            score += 4
            reasons.append("small (+4)")
        elif planning.predicted_size >= 13:
            score -= 8
            reasons.append("very large (-8)")
        if planning.risk_level == "High":
            score -= 6
        if planning.confidence < 50:
            score -= 4

    return score, reasons


def auto_build_sprint(
    backlog: list[JiraIssue],
    history: list[HistoricalIssue],
    team: list[TeamMember],
    performance: list[TeamPerformance] | None = None,
    target_capacity: int | None = None,
    max_tasks: int = 15,
) -> AutoSprintResult:
    if target_capacity is None or target_capacity <= 0:
        target_capacity = _free_capacity(team) or 56
    fill_target = max(8, int(target_capacity * 0.85))

    # Rank candidates by a quick first-pass score (no sizing yet)
    pre_ranked = sorted(
        backlog,
        key=lambda i: -_inclusion_score(i)[0],
    )
    candidates = pre_ranked[:30]
    log.info(
        "auto_sprint backlog=%d pre_ranked candidates=%d target_capacity=%d fill_target=%d max_tasks=%d",
        len(backlog), len(candidates), target_capacity, fill_target, max_tasks,
    )

    # Size them (kNN only for the candidate scan — LLM calibration is
    # applied only to the items that actually make the sprint, below).
    plan_by_key: dict[str, PlanningResult] = {}
    for issue in candidates:
        plan_by_key[issue.key] = predict_size(issue, history, use_llm=False)

    # Re-rank now that sizes are known
    ranked = sorted(
        candidates,
        key=lambda i: -_inclusion_score(i, plan_by_key[i.key])[0],
    )

    selected: list[AutoSprintItem] = []
    plannings: list[PlanningResult] = []
    used = 0
    for issue in ranked:
        plan = plan_by_key[issue.key]
        score, reasons = _inclusion_score(issue, plan)
        if len(selected) >= max_tasks:
            break
        # Allow slight overshoot for the last item if its score is exceptional
        if used + plan.predicted_size > fill_target:
            # Skip large items late in the loop; small ones may still fit
            if plan.predicted_size > max(1, fill_target - used) + 1:
                continue
        selected.append(
            AutoSprintItem(
                issue_key=issue.key,
                title=issue.title,
                predicted_size=plan.predicted_size,
                confidence=plan.confidence,
                risk_level=plan.risk_level,
                carry_over_count=issue.carry_over_count,
                priority=issue.priority,
                inclusion_score=score,
                inclusion_reasons=reasons,
            )
        )
        plannings.append(plan)
        used += plan.predicted_size

    log.info(
        "auto_sprint selected %d task(s) totalling %d/%d SP",
        len(selected), used, target_capacity,
    )

    # Re-size the SELECTED items with the LLM calibration layer so the user
    # sees genuinely varied confidence / carry-over numbers per task.
    issue_by_key = {i.key: i for i in candidates}
    for item in selected:
        plan_by_key[item.issue_key] = predict_size(
            issue_by_key[item.issue_key], history, use_llm=True,
        )
    plannings = [plan_by_key[s.issue_key] for s in selected]
    # Re-sync the AutoSprintItem confidence/risk fields with the calibrated values
    for s, p in zip(selected, plannings):
        s.predicted_size = p.predicted_size
        s.confidence = p.confidence
        s.risk_level = p.risk_level

    # Decompose every selected item
    decompositions = []
    used_llm = False
    for item in selected:
        issue = issue_by_key[item.issue_key]
        plan = plan_by_key[item.issue_key]
        d = decompose(issue, plan, team, performance)
        if any(
            "chosen by AI" in (st.assignment_reason or "")
            for st in d.subtasks
        ):
            used_llm = True
        decompositions.append(d)

    if selected:
        summary = (
            f"Auto-built next sprint with {len(selected)} task(s) "
            f"using {used}/{target_capacity} SP "
            f"({int(used / max(target_capacity, 1) * 100)}% utilisation). "
            f"{sum(1 for s in selected if s.carry_over_count > 0)} carry-over(s) included."
        )
    else:
        summary = "No backlog items met the inclusion criteria."

    return AutoSprintResult(
        selected=selected,
        issue_keys=[s.issue_key for s in selected],
        plannings=plannings,
        decompositions=decompositions,
        used_capacity=used,
        target_capacity=target_capacity,
        candidate_pool_size=len(candidates),
        backlog_size=len(backlog),
        summary=summary,
        used_openai_decomposition=used_llm,
    )
