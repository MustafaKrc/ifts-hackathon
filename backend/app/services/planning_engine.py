"""Orchestrates predictive planning for a list of selected backlog issues."""

from __future__ import annotations

from ..models import HistoricalIssue, JiraIssue, PlanningResult
from .predictive_sizing import predict_size


def plan_sprint(
    issues: list[JiraIssue], history: list[HistoricalIssue]
) -> list[PlanningResult]:
    return [predict_size(issue, history) for issue in issues]
