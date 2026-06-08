"""
What-if Sprint Simulator.

Generates three scenarios for a selected sprint scope:

  1. Keep All Tasks         — baseline using the currently selected issues.
  2. Remove Highest Risk    — drop the task with the worst composite risk score.
  3. Split Large Risky Task — shrink the largest task to its safest vertical
                              slice (50%), pretending the remainder slips to
                              the next sprint.

Each scenario re-runs the predictive sizing + health engine, surfaces the
trade-off, and the simulator picks one as `recommended` (highest health score
with capacity <= 100%).
"""

from __future__ import annotations

from copy import deepcopy

from ..models import (
    HistoricalIssue,
    JiraIssue,
    PlanningResult,
    SprintScenario,
    TaskSequenceResult,
)
from .planning_engine import plan_sprint
from .sprint_health_engine import compute_sprint_health


def _risk_score(planning: PlanningResult) -> int:
    s = 0
    s += planning.predicted_size * 2
    s += {"Low": 0, "Medium": 5, "High": 12}[planning.risk_level]
    s += (100 - planning.confidence) // 5
    s += planning.carry_over_risk // 5
    s += 6 * len(planning.blocker_suggestions)
    return s


def _build_scenario_for(
    name: str,
    issues: list[JiraIssue],
    plannings: list[PlanningResult],
    sequences: list[TaskSequenceResult],
    changes_made: list[str],
    trade_off: str,
    why: str,
) -> SprintScenario:
    health = compute_sprint_health(issues, plannings, sequences)
    capacity_utilization = int(
        round((health.predicted_points / max(health.capacity, 1)) * 100)
    )
    deadline_risk = 0
    critical_path_risk = 0
    for seq in sequences:
        deadline_risk += sum(
            1
            for st in seq.ordered_subtasks
            if st.deadline and st.status == "Not Ready"
        )
        critical_path_risk += max(0, len(seq.critical_path) - 2)
    actions = list(health.recommended_actions)
    return SprintScenario(
        scenario_name=name,
        verdict=health.verdict,
        sprint_health_score=health.score,
        predicted_points=health.predicted_points,
        capacity_utilization=capacity_utilization,
        carry_over_risk=health.carry_over_risk,
        deadline_risk=min(100, deadline_risk * 15),
        critical_path_risk=min(100, critical_path_risk * 20),
        changes_made=changes_made,
        trade_off=trade_off,
        recommended_actions=actions[:4],
        why_this_scenario=why,
        is_recommended=False,
    )


def _split_largest(
    issues: list[JiraIssue], plannings: list[PlanningResult]
) -> tuple[list[JiraIssue], list[PlanningResult], str | None]:
    if not plannings:
        return issues, plannings, None
    largest = max(plannings, key=lambda p: p.predicted_size)
    new_size = max(1, largest.predicted_size // 2)
    new_plannings = []
    new_issues = []
    for issue, pl in zip(issues, plannings):
        if pl.issue_key == largest.issue_key:
            shrunk = pl.model_copy(
                update={
                    "predicted_size": new_size,
                    "reasoning": pl.reasoning
                    + [
                        f"Split scenario: original predicted {pl.predicted_size} SP "
                        f"reduced to {new_size} SP as a thin vertical slice."
                    ],
                    "confidence": min(99, pl.confidence + 10),
                    "carry_over_risk": max(0, pl.carry_over_risk - 25),
                }
            )
            new_plannings.append(shrunk)
            new_issues.append(issue)
        else:
            new_plannings.append(pl)
            new_issues.append(issue)
    return new_issues, new_plannings, largest.issue_key


def simulate(
    issues: list[JiraIssue],
    history: list[HistoricalIssue],
    sequences_by_issue: dict[str, TaskSequenceResult] | None = None,
) -> list[SprintScenario]:
    sequences_by_issue = sequences_by_issue or {}
    base_plannings = plan_sprint(issues, history)
    base_sequences = [sequences_by_issue[i.key] for i in issues if i.key in sequences_by_issue]

    # Scenario 1: Keep All
    keep = _build_scenario_for(
        name="Keep All Tasks",
        issues=issues,
        plannings=base_plannings,
        sequences=base_sequences,
        changes_made=["No changes applied to the current sprint scope."],
        trade_off=(
            "Maximum feature delivery if everything ships on time, but the highest "
            "exposure to overcommitment, blockers and carry-over."
        ),
        why=(
            "Preserves the currently selected scope. Useful as the baseline reference "
            "for the other scenarios."
        ),
    )

    # Scenario 2: Remove Highest Risk
    if base_plannings:
        worst = max(base_plannings, key=_risk_score)
        new_issues = [i for i in issues if i.key != worst.issue_key]
        new_plannings = [p for p in base_plannings if p.issue_key != worst.issue_key]
        new_sequences = [s for s in base_sequences if s.issue_key != worst.issue_key]
        remove = _build_scenario_for(
            name="Remove Highest Risk Task",
            issues=new_issues,
            plannings=new_plannings,
            sequences=new_sequences,
            changes_made=[
                f"Removed {worst.issue_key} (risk={worst.risk_level}, "
                f"size={worst.predicted_size}, confidence={worst.confidence}%, "
                f"carry-over={worst.carry_over_risk}%)."
            ],
            trade_off=(
                f"Loses scope on {worst.issue_key} but materially lowers carry-over "
                "and overcommitment risk; team can absorb the saved effort buffer."
            ),
            why=(
                f"{worst.issue_key} has the worst combined risk profile this sprint. "
                "Removing it is the cheapest path to a healthier sprint."
            ),
        )
    else:
        remove = _build_scenario_for(
            name="Remove Highest Risk Task",
            issues=issues,
            plannings=base_plannings,
            sequences=base_sequences,
            changes_made=["No issues selected to remove."],
            trade_off="No-op: nothing to remove.",
            why="No selected issues.",
        )

    # Scenario 3: Split Largest
    split_issues, split_plannings, split_key = _split_largest(
        list(issues), [deepcopy(p) for p in base_plannings]
    )
    split_sequences = base_sequences  # sequencing isn't rerun for simulation speed
    if split_key:
        split = _build_scenario_for(
            name="Split Large Risky Task",
            issues=split_issues,
            plannings=split_plannings,
            sequences=split_sequences,
            changes_made=[
                f"Reduced {split_key} to a thin vertical slice (~50% scope) and "
                "deferred remaining work to the next sprint."
            ],
            trade_off=(
                f"Ships a testable slice of {split_key} this sprint and preserves QA time; "
                "full feature ships next sprint."
            ),
            why=(
                f"{split_key} is the largest item in scope; splitting it protects the "
                "sprint commitment without dropping the feature entirely."
            ),
        )
    else:
        split = _build_scenario_for(
            name="Split Large Risky Task",
            issues=issues,
            plannings=base_plannings,
            sequences=base_sequences,
            changes_made=["No task large enough to split."],
            trade_off="No-op: nothing to split.",
            why="No suitable task to split.",
        )

    scenarios = [keep, remove, split]

    # Pick recommended: highest health, capacity_utilization <= 100 preferred
    def rank(s: SprintScenario) -> tuple[int, int, int]:
        capacity_penalty = 0 if s.capacity_utilization <= 100 else 1
        return (-s.sprint_health_score, capacity_penalty, s.carry_over_risk)

    recommended = sorted(scenarios, key=rank)[0]
    recommended.is_recommended = True
    return scenarios
