"""
Sprint health scoring based on the spec section 9.5 formula.

Score starts at 100 and is deducted for overcommitment, high-risk issues,
blockers, low confidence, carry-over risk, overloaded members, long critical
paths, deadline risk, and squeezed test windows. Result is normalised to
[1, 100] and mapped to a verdict (Healthy / Risky / Overcommitted).
"""

from __future__ import annotations

import logging
from datetime import date

from ..data.mock_team import find_by_id, get_team
from ..models import (
    CapacityInfo,
    CarryOverItem,
    JiraIssue,
    PlanningResult,
    SprintHealth,
    TaskSequenceResult,
)

log = logging.getLogger("sprintpilot.health")


def _team_capacity() -> int:
    return sum(m.capacity - m.current_load for m in get_team())


def _capacity_breakdown(
    sequences: list[TaskSequenceResult],
) -> list[CapacityInfo]:
    allocations: dict[str, int] = {}
    for seq in sequences:
        for st in seq.ordered_subtasks:
            allocations[st.suggested_assignee_id] = (
                allocations.get(st.suggested_assignee_id, 0) + st.estimated_size
            )
    infos: list[CapacityInfo] = []
    for m in get_team():
        allocated = allocations.get(m.id, 0)
        total_load = m.current_load + allocated
        utilization = int(round((total_load / max(m.capacity, 1)) * 100))
        infos.append(
            CapacityInfo(
                member_id=m.id,
                member_name=m.name,
                role=m.role,
                capacity=m.capacity,
                current_load=m.current_load,
                allocated_in_sprint=allocated,
                utilization_percent=utilization,
            )
        )
    return infos


def _generate_review_summary(
    issues: list[JiraIssue],
    plannings: list[PlanningResult],
    verdict: str,
    score: int,
) -> str:
    total_planned = sum((p.original_size or 0) for p in plannings)
    total_predicted = sum(p.predicted_size for p in plannings)
    high_risk = [p for p in plannings if p.risk_level == "High"]
    lines = [
        f"This sprint contains {len(issues)} selected issue(s) totalling "
        f"{total_planned} planned points and {total_predicted} predicted points.",
        f"Sprint health: {score}/100 — verdict: {verdict}.",
    ]
    if high_risk:
        keys = ", ".join(p.issue_key for p in high_risk)
        lines.append(f"High-risk issues identified: {keys}.")
    if total_predicted > total_planned + 3:
        lines.append(
            f"Predicted effort exceeds planned by {total_predicted - total_planned} SP "
            "— overcommitment likely without scope changes."
        )
    return " ".join(lines)


def _generate_decision_receipt(
    issues: list[JiraIssue],
    plannings: list[PlanningResult],
    score: int,
    verdict: str,
    risks: list[str],
    actions: list[str],
) -> str:
    bullets = [
        "SPRINT DECISION RECEIPT",
        f"Verdict: {verdict} | Health: {score}/100",
        f"Issues: {', '.join(i.key for i in issues)}",
        f"Total predicted: {sum(p.predicted_size for p in plannings)} SP",
        "Key risks:",
    ]
    bullets += [f"  - {r}" for r in (risks or ["None"])][:5]
    bullets.append("Recommended actions:")
    bullets += [f"  - {a}" for a in (actions or ["Proceed as planned"])][:5]
    return "\n".join(bullets)


def compute_sprint_health(
    issues: list[JiraIssue],
    plannings: list[PlanningResult],
    sequences: list[TaskSequenceResult],
    penalty_scale: float = 1.0,
) -> SprintHealth:
    """Compute a sprint-plan health score.

    `penalty_scale` multiplies every deduction. The What-if simulator passes
    0.1 (10% of normal) so its three scenarios produce gentler, more readable
    differences. The Sprint Review page keeps the full penalty weight.
    """
    planned_total = sum((p.original_size or 0) for p in plannings)
    predicted_total = sum(p.predicted_size for p in plannings)
    capacity = _team_capacity()
    log.info(
        "compute_sprint_health start issues=%d planned=%d predicted=%d free_capacity=%d sequences=%d penalty_scale=%.2f",
        len(issues), planned_total, predicted_total, capacity, len(sequences), penalty_scale,
    )

    def _scaled(p: int) -> int:
        """Apply penalty_scale, round to nearest int, ensure at least 1 if scale>0."""
        if p <= 0:
            return 0
        scaled = p * penalty_scale
        rounded = int(round(scaled))
        # Keep at least a 1-point bite at any positive scale so the deduction
        # actually shows up in the verdict math.
        return max(1, rounded) if scaled > 0 else 0

    risks: list[str] = []
    actions: list[str] = []
    deductions: list[str] = []
    score = 100

    if predicted_total > capacity and capacity > 0:
        d = _scaled(25)
        score -= d
        deductions.append(f"overcommit -{d}")
        risks.append(
            f"Predicted effort {predicted_total} SP exceeds remaining team "
            f"capacity {capacity} SP."
        )
        actions.append("Reduce scope or split the largest risky issue.")

    high_risk = [p for p in plannings if p.risk_level == "High"]
    d = _scaled(8 * len(high_risk))
    score -= d
    if high_risk:
        deductions.append(f"high_risk -{d}")
        risks.append(
            f"{len(high_risk)} high-risk issue(s): {', '.join(p.issue_key for p in high_risk)}"
        )

    blocked_issues = [i for i in issues if i.blocker_reason or i.status == "Blocked"]
    d = _scaled(10 * len(blocked_issues))
    score -= d
    if blocked_issues:
        deductions.append(f"blocked -{d}")
    if blocked_issues:
        risks.append(
            f"{len(blocked_issues)} issue(s) blocked: "
            f"{', '.join(i.key for i in blocked_issues)}"
        )
        actions.append("Unblock or de-scope blocked issues before sprint starts.")

    low_confidence = [p for p in plannings if p.confidence < 55]
    d = _scaled(6 * len(low_confidence))
    score -= d
    if low_confidence:
        deductions.append(f"low_conf -{d}")
    if low_confidence:
        risks.append(
            f"{len(low_confidence)} issue(s) sized with low confidence."
        )
        actions.append("Run a brief analysis spike on low-confidence issues.")

    avg_carry_over = (
        sum(p.carry_over_risk for p in plannings) / max(len(plannings), 1)
    )
    if avg_carry_over >= 50:
        d = _scaled(10)
        score -= d
        deductions.append(f"carry_over -{d}")
        risks.append(f"Average carry-over risk is {int(avg_carry_over)}%.")
        actions.append("Plan smaller vertical slices to reduce carry-over risk.")

    capacity_info = _capacity_breakdown(sequences)
    overloaded = [c for c in capacity_info if c.utilization_percent >= 90]
    d = _scaled(8 * len(overloaded))
    score -= d
    if overloaded:
        deductions.append(f"overloaded -{d}")
    for c in overloaded:
        risks.append(
            f"{c.member_name} is at {c.utilization_percent}% utilization."
        )
        actions.append(f"Reassign work away from {c.member_name}.")

    longest_path = 0
    for seq in sequences:
        longest_path = max(longest_path, len(seq.critical_path))
    if longest_path >= 4:
        d = _scaled(8)
        score -= d
        deductions.append(f"critical_path -{d}")
        risks.append(
            f"Critical path is {longest_path} tasks deep — long serial chain."
        )
        actions.append("Parallelise non-blocking tasks where possible.")

    near_deadline_not_ready = 0
    for seq in sequences:
        for st in seq.ordered_subtasks:
            if (
                st.deadline
                and (st.deadline - date.today()).days <= 2
                and st.status == "Not Ready"
            ):
                near_deadline_not_ready += 1
    if near_deadline_not_ready:
        d = _scaled(10)
        score -= d
        deductions.append(f"near_deadline_not_ready -{d}")
        risks.append(
            f"{near_deadline_not_ready} task(s) have a deadline within 2 days but are Not Ready."
        )

    test_squeeze = False
    for seq in sequences:
        if any("Test is at risk" in r for r in seq.schedule_risks):
            test_squeeze = True
            break
    if test_squeeze:
        d = _scaled(10)
        score -= d
        deductions.append(f"test_squeeze -{d}")
        risks.append("Test window is squeezed by remaining development workload.")
        actions.append("Move part of a large task to next sprint to free QA time.")

    raw_score = score
    score = max(1, min(100, score))
    if score >= 75:
        verdict = "Healthy"
    elif score >= 50:
        verdict = "Risky"
    else:
        verdict = "Overcommitted"

    log.info(
        "compute_sprint_health result score=%d (raw=%d, clamped) verdict=%s deductions=[%s] risks=%d actions=%d",
        score, raw_score, verdict, ", ".join(deductions) or "none",
        len(risks), len(actions),
    )

    if not actions:
        actions.append("Proceed with this sprint plan as scoped.")

    # Build carry-over watch list from selected issues' sprint_history
    plan_by_key = {p.issue_key: p for p in plannings}
    carry_items: list[CarryOverItem] = []
    for i in issues:
        if i.carry_over_count <= 0:
            continue
        past = [s.name for s in i.sprint_history if s.state == "closed"]
        plan = plan_by_key.get(i.key)
        carry_items.append(
            CarryOverItem(
                issue_key=i.key,
                title=i.title,
                carry_over_count=i.carry_over_count,
                assignee_name=i.assignee_name,
                current_sprint=i.sprint_name,
                past_sprints=past,
                predicted_size=plan.predicted_size if plan else None,
                risk_level=plan.risk_level if plan else None,
                blocker_reason=i.blocker_reason,
            )
        )
    carry_items.sort(key=lambda c: -c.carry_over_count)

    if carry_items:
        worst = carry_items[0]
        risks.append(
            f"{len(carry_items)} carryover issue(s) selected; worst: "
            f"{worst.issue_key} has slipped {worst.carry_over_count} sprint(s)."
        )
        if worst.carry_over_count >= 2:
            actions.append(
                f"Investigate {worst.issue_key} — slipped {worst.carry_over_count} "
                "sprints; consider splitting or de-scoping."
            )

    log.info(
        "compute_sprint_health carry_over_items=%d (max slipped=%d)",
        len(carry_items),
        carry_items[0].carry_over_count if carry_items else 0,
    )

    summary = _generate_review_summary(issues, plannings, verdict, score)
    receipt = _generate_decision_receipt(issues, plannings, score, verdict, risks, actions)

    return SprintHealth(
        score=score,
        verdict=verdict,  # type: ignore[arg-type]
        planned_points=planned_total,
        predicted_points=predicted_total,
        capacity=capacity,
        capacity_by_member=capacity_info,
        carry_over_risk=int(avg_carry_over),
        carry_over_items=carry_items,
        risks=risks,
        recommended_actions=actions,
        review_summary=summary,
        decision_receipt=receipt,
    )
