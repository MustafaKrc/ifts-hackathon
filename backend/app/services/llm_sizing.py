"""
LLM-driven calibration of the kNN sizing result.

The deterministic predictive_sizing engine returns a baseline confidence and
carry-over risk — but on a pile of similar-looking carry-over items those
numbers cluster around the same value because the underlying signals are
identical. The LLM enhancement layer adds genuine variance by reasoning about
each issue's actual context, and it produces real, specific resolution
suggestions for blocked work — none of which a kNN formula can do.

Skips gracefully when OPENAI_API_KEY is missing or the shared circuit breaker
is open. The caller always gets back a valid PlanningResult.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from ..models import JiraIssue, PlanningResult, SimilarIssueEvidence
from .openai_priority_advisor import _disable, _openai_disabled_reason  # type: ignore[attr-defined]

log = logging.getLogger("sprintpilot.llm_sizing")


_SYSTEM_PROMPT = (
    "You are an expert Agile estimator reviewing a sizing produced by a "
    "similarity-based system. Your job: calibrate confidence and carry-over "
    "risk based on the specific issue context, and — if the issue is blocked — "
    "propose concrete, actionable resolution suggestions.\n\n"
    "Rules:\n"
    "- Confidence (1-100) MUST vary across issues. A clearly-scoped small task "
    "should be 70-95%. A vague large migration should be 15-40%. Calibrate "
    "honestly per issue; do NOT cluster every issue around the same value.\n"
    "- Carry-over risk (1-100) reflects: complexity, blocker presence, slip "
    "history of similar items, dependency count, AC clarity, scope size.\n"
    "- Blocker suggestions: ONLY include if the issue is actually blocked. "
    "2-4 short, concrete actions (e.g. 'Reach out to vendor SRE for trace "
    "access', 'Schedule architecture sync with the platform team', 'Escalate "
    "to product owner if SLA confirmation isn't received by Friday'). No "
    "fluff. Empty list if not blocked.\n"
    "- Keep predicted_size unchanged unless you have strong evidence the kNN "
    "result is materially off — your job is calibration, not re-estimation.\n\n"
    "Return ONLY valid JSON:\n"
    "{\n"
    '  "confidence": <int 1-100>,\n'
    '  "carry_over_risk": <int 0-100>,\n'
    '  "predicted_size": <int fibonacci, optional override>,\n'
    '  "reasoning_addendum": ["<one-line calibration reason>", ...],\n'
    '  "blocker_suggestions": ["<actionable step>", ...]\n'
    "}"
)


def _build_prompt(planning: PlanningResult, issue: JiraIssue) -> str:
    similar_lines = "\n".join(
        f"- {ev.key} ({ev.actual_size} SP delivered, "
        f"{ev.cycle_time_days}d cycle, "
        f"{'CARRIED OVER' if ev.carried_over else 'on time'}, sim={ev.similarity:.2f}): "
        f"{ev.title[:80]}"
        for ev in planning.similar_issues
    )
    if not similar_lines:
        similar_lines = "(no similar past issues)"

    return (
        f"Issue: {issue.key}\n"
        f"Title: {issue.title}\n"
        f"Description: {(issue.description or '')[:500]}\n"
        f"Priority: {issue.priority}\n"
        f"Labels: {issue.labels}\n"
        f"Components: {issue.components}\n"
        f"Has acceptance criteria: {bool(issue.acceptance_criteria)}\n"
        f"Dependencies: {issue.dependencies or 'none'}\n"
        f"Blocker reason: {issue.blocker_reason or 'none'}\n"
        f"Carry-over count so far: {issue.carry_over_count}\n"
        f"\nkNN baseline:\n"
        f"  predicted_size = {planning.predicted_size} SP\n"
        f"  confidence = {planning.confidence}%\n"
        f"  carry_over_risk = {planning.carry_over_risk}%\n"
        f"  risk = {planning.risk_level}\n"
        f"\nTop similar historical issues:\n{similar_lines}\n"
    )


def enhance_planning(
    planning: PlanningResult, issue: JiraIssue,
) -> PlanningResult:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return planning
    if _openai_disabled_reason:
        return planning
    model = os.environ.get("OPENAI_MODEL", "gpt-5.4")
    prompt = _build_prompt(planning, issue)
    log.info(
        "LLM sizing calibrate %s baseline conf=%d carry=%d size=%d",
        issue.key, planning.confidence, planning.carry_over_risk, planning.predicted_size,
    )
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, max_retries=0)
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            temperature=0.25,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            timeout=20,
        )
        content = response.choices[0].message.content or ""
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            log.warning("LLM sizing %s unparseable JSON; keeping baseline", issue.key)
            return planning

        # Pull validated fields
        new_conf = planning.confidence
        try:
            new_conf = max(1, min(100, int(payload.get("confidence", planning.confidence))))
        except (TypeError, ValueError):
            pass
        new_carry = planning.carry_over_risk
        try:
            new_carry = max(0, min(100, int(payload.get("carry_over_risk", planning.carry_over_risk))))
        except (TypeError, ValueError):
            pass
        new_size = planning.predicted_size
        try:
            raw = payload.get("predicted_size")
            if raw is not None:
                new_size = max(1, int(raw))
        except (TypeError, ValueError):
            pass

        addendum = [
            str(r).strip()
            for r in (payload.get("reasoning_addendum") or [])
            if str(r).strip()
        ][:4]
        new_blocker_suggestions = [
            str(b).strip()
            for b in (payload.get("blocker_suggestions") or [])
            if str(b).strip()
        ][:5]

        # Keep existing suggestions if issue is blocked but LLM returned none
        if issue.blocker_reason and not new_blocker_suggestions:
            new_blocker_suggestions = planning.blocker_suggestions

        updated = planning.model_copy(
            update={
                "confidence": new_conf,
                "carry_over_risk": new_carry,
                "predicted_size": new_size,
                "blocker_suggestions": new_blocker_suggestions,
                "reasoning": planning.reasoning + [f"AI calibration: {r}" for r in addendum],
            }
        )
        log.info(
            "LLM sizing %s -> conf %d (was %d), carry %d (was %d), size %d (was %d), blocker_sugg=%d",
            issue.key, new_conf, planning.confidence,
            new_carry, planning.carry_over_risk,
            new_size, planning.predicted_size,
            len(new_blocker_suggestions),
        )
        return updated
    except Exception as e:
        name = type(e).__name__
        log.error("LLM sizing %s failed: %s: %s", issue.key, name, str(e)[:200])
        if name in {
            "RateLimitError", "AuthenticationError", "NotFoundError",
            "PermissionDeniedError", "BadRequestError",
        }:
            _disable(f"{name}: {str(e)[:120]}")
        return planning
