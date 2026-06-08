"""
Similarity-based predictive sizing (kNN-style).

Compares a Jira issue with the historical sprint dataset using label overlap,
component overlap, title/description keyword overlap, dependency similarity,
blocker similarity and priority similarity. Picks the top 3 most similar
historical issues, takes a weighted average of their actual sizes, applies
risk-based adjustments, and normalises to a planning-poker value.

Returns a PlanningResult with confidence score, risk level, carry-over risk,
"why this estimate" reasoning, blocker suggestions and similar-issue evidence.
"""

from __future__ import annotations

import logging
import re
from typing import Iterable

from ..models import (
    HistoricalIssue,
    JiraIssue,
    PlanningResult,
    SimilarIssueEvidence,
)

log = logging.getLogger("sprintpilot.sizing")

_FIBONACCI = [1, 2, 3, 5, 8, 13]
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "is", "are", "be", "as", "this", "that", "from",
    "we", "i", "it", "should", "will", "can", "add", "need", "new",
}


def _tokens(text: str) -> set[str]:
    if not text:
        return set()
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def _jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = {x.lower() for x in a if x}, {x.lower() for x in b if x}
    if not sa and not sb:
        return 0.0
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


def _similarity(issue: JiraIssue, hist: HistoricalIssue) -> float:
    label = _jaccard(issue.labels, hist.labels) * 0.25
    component = _jaccard(issue.components, hist.components) * 0.25

    issue_kw = _tokens(f"{issue.title} {issue.description}")
    hist_kw = _tokens(f"{hist.title} {hist.description}")
    keyword = _jaccard(issue_kw, hist_kw) * 0.25

    dep_match = bool(issue.dependencies) == bool(False)  # historical doesn't track deps
    dep_sim = 0.10 if dep_match else 0.05

    blocker_match = bool(issue.blocker_reason) == hist.had_blocker
    blocker_sim = 0.10 if blocker_match else 0.0

    priority_sim = 0.05 if issue.priority == hist.priority else 0.0

    return label + component + keyword + dep_sim + blocker_sim + priority_sim


def _normalize_to_fibonacci(value: float) -> int:
    if value <= 0:
        return 1
    best = _FIBONACCI[0]
    best_diff = abs(value - best)
    for fib in _FIBONACCI:
        d = abs(value - fib)
        if d < best_diff:
            best = fib
            best_diff = d
    return best


def _classify_risk(predicted: int, confidence: int, issue: JiraIssue) -> str:
    risk_score = 0
    if predicted >= 8:
        risk_score += 1
    if predicted >= 13:
        risk_score += 1
    if confidence < 55:
        risk_score += 1
    if issue.blocker_reason:
        risk_score += 1
    if issue.dependencies:
        risk_score += 1
    if not issue.acceptance_criteria:
        risk_score += 1
    if issue.priority == "Critical":
        risk_score += 1
    if risk_score >= 4:
        return "High"
    if risk_score >= 2:
        return "Medium"
    return "Low"


def _carry_over_risk(
    top_matches: list[tuple[float, HistoricalIssue]],
    issue: JiraIssue,
    predicted: int,
    confidence: int,
) -> int:
    score = 0
    if top_matches:
        carried_ratio = sum(1 for _, h in top_matches if h.carried_over) / len(top_matches)
        score += int(carried_ratio * 40)
    if issue.dependencies:
        score += 15
    if issue.blocker_reason:
        score += 20
    if confidence < 50:
        score += 15
    if predicted >= 8:
        score += 10
    if predicted >= 13:
        score += 10
    return max(0, min(100, score))


def _confidence(
    top_matches: list[tuple[float, HistoricalIssue]], issue: JiraIssue
) -> int:
    if not top_matches:
        return 20
    avg_sim = sum(s for s, _ in top_matches) / len(top_matches)
    base = int(avg_sim * 100)
    base += len(top_matches) * 3
    if issue.acceptance_criteria:
        base += 8
    if len(issue.description) > 120:
        base += 5
    if issue.dependencies:
        base -= 10
    if issue.blocker_reason:
        base -= 12
    return max(10, min(99, base))


def _reasoning(
    issue: JiraIssue,
    top_matches: list[tuple[float, HistoricalIssue]],
    predicted: int,
    adjustments: list[str],
    confidence: int,
) -> list[str]:
    bullets: list[str] = []
    if top_matches:
        keys = ", ".join(h.key for _, h in top_matches)
        sizes = ", ".join(str(h.actual_size) for _, h in top_matches)
        bullets.append(
            f"Compared with {len(top_matches)} similar past issues ({keys}) "
            f"whose actual sizes were {sizes}."
        )
    else:
        bullets.append(
            "No closely matching historical issues found; defaulted to a "
            "conservative estimate."
        )
    bullets.append(f"Predicted size {predicted} SP with {confidence}% confidence.")
    for adj in adjustments:
        bullets.append(adj)
    if issue.priority == "Critical":
        bullets.append("Priority is Critical — extra buffer added for risk.")
    if not issue.acceptance_criteria:
        bullets.append(
            "Acceptance criteria are missing; investing in analysis first is recommended."
        )
    if issue.dependencies:
        bullets.append(
            f"Has {len(issue.dependencies)} upstream dependencies that must be ready "
            "before work can complete."
        )
    return bullets


def _blocker_suggestions(issue: JiraIssue) -> list[str]:
    suggestions: list[str] = []
    if issue.blocker_reason:
        suggestions.append(f"Resolve blocker: {issue.blocker_reason}")
        suggestions.append(
            "Escalate to product owner if blocker is unresolved by sprint planning."
        )
    if issue.dependencies:
        suggestions.append(
            f"Confirm completion of: {', '.join(issue.dependencies)} before starting."
        )
    if not issue.acceptance_criteria:
        suggestions.append(
            "Run a 30-min analysis spike to clarify acceptance criteria before estimation is locked."
        )
    return suggestions


def predict_size(
    issue: JiraIssue, history: list[HistoricalIssue]
) -> PlanningResult:
    log.info(
        "predict_size %s priority=%s labels=%s components=%s has_ac=%s has_blocker=%s deps=%d history_pool=%d",
        issue.key, issue.priority, issue.labels, issue.components,
        bool(issue.acceptance_criteria), bool(issue.blocker_reason),
        len(issue.dependencies), len(history),
    )
    if history:
        scored = sorted(
            ((_similarity(issue, h), h) for h in history),
            key=lambda x: -x[0],
        )
        top = scored[:3]
    else:
        top = []

    if top:
        total_weight = sum(max(s, 1e-3) for s, _ in top)
        weighted_avg = sum(max(s, 1e-3) * h.actual_size for s, h in top) / total_weight
        log.info(
            "predict_size %s top3=%s weighted_avg=%.2f",
            issue.key,
            [(h.key, round(s, 3), h.actual_size) for s, h in top],
            weighted_avg,
        )
    else:
        weighted_avg = issue.current_size or 5
        log.warning(
            "predict_size %s no history; using current_size=%s fallback",
            issue.key, issue.current_size,
        )

    adjustments: list[str] = []
    add = 0
    if not issue.acceptance_criteria:
        add += 1
        adjustments.append("+1 SP because acceptance criteria are missing.")
    if issue.dependencies:
        add += 1
        adjustments.append("+1 SP because the issue has upstream dependencies.")
    if issue.blocker_reason:
        add += 2
        adjustments.append("+2 SP because the issue has an active blocker.")
    if len(issue.description) < 60:
        add += 1
        adjustments.append("+1 SP because the description is very short / vague.")
    if len(issue.labels) + len(issue.components) >= 6:
        add += 1
        adjustments.append("+1 SP because the issue spans many components/labels.")
    if issue.priority == "Critical":
        add += 1
        adjustments.append("+1 SP risk buffer because priority is Critical.")

    predicted = _normalize_to_fibonacci(weighted_avg + add)
    confidence = _confidence(top, issue)
    risk = _classify_risk(predicted, confidence, issue)
    carry_over = _carry_over_risk(top, issue, predicted, confidence)
    log.info(
        "predict_size %s -> predicted=%d confidence=%d risk=%s carry_over=%d adjustments=+%d (%s)",
        issue.key, predicted, confidence, risk, carry_over, add,
        " | ".join(adjustments) or "none",
    )

    similar_evidence = [
        SimilarIssueEvidence(
            key=h.key,
            title=h.title,
            similarity=round(s, 3),
            actual_size=h.actual_size,
            cycle_time_days=h.cycle_time_days,
            carried_over=h.carried_over,
            reason=_evidence_reason(issue, h, s),
        )
        for s, h in top
    ]

    return PlanningResult(
        issue_key=issue.key,
        title=issue.title,
        original_size=issue.current_size,
        predicted_size=predicted,
        confidence=confidence,
        risk_level=risk,
        reasoning=_reasoning(issue, top, predicted, adjustments, confidence),
        blocker_suggestions=_blocker_suggestions(issue),
        similar_issues=similar_evidence,
        carry_over_risk=carry_over,
    )


def _evidence_reason(issue: JiraIssue, hist: HistoricalIssue, sim: float) -> str:
    parts: list[str] = []
    shared_labels = set(l.lower() for l in issue.labels) & set(l.lower() for l in hist.labels)
    if shared_labels:
        parts.append(f"shared labels: {', '.join(sorted(shared_labels))}")
    shared_components = set(c.lower() for c in issue.components) & set(
        c.lower() for c in hist.components
    )
    if shared_components:
        parts.append(f"shared components: {', '.join(sorted(shared_components))}")
    if hist.had_blocker and issue.blocker_reason:
        parts.append("both had blockers")
    if hist.carried_over:
        parts.append("note: this past issue carried over")
    if not parts:
        parts.append("title/description keyword overlap")
    return "; ".join(parts) + f" (similarity={sim:.2f})"
