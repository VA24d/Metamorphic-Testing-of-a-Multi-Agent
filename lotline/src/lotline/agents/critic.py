"""Critic Agent — coverage/confidence gate with Pass or Revise."""

from __future__ import annotations

import json

from lotline.llm import ollama_generate
from lotline.models import Critique, CritiqueAction, CritiqueStatus, QueryPlan, TrendOutput
from lotline.tools import score_coverage


def run_critic_mock(
    plan: QueryPlan,
    trend: TrendOutput,
    min_coverage: float = 0.72,
    min_per_month: int = 4,
) -> Critique:
    sc = score_coverage(trend, min_per_month=min_per_month)
    coverage = float(sc["coverage_score"])
    weak = sc["weak_months"]
    confidence = min(1.0, coverage * (0.85 + 0.15 * (plan.revision_round == 0)))

    # Stop if good enough OR we already revised enough (orchestrator also caps)
    if coverage >= min_coverage and not trend.empty_months:
        return Critique(
            status=CritiqueStatus.PASS,
            coverage_score=coverage,
            confidence=confidence,
            actions=[],
            summary=f"Coverage {coverage:.2f} acceptable across 12 months.",
        )

    actions: list[CritiqueAction] = []
    if weak or trend.empty_months:
        actions.append(
            CritiqueAction(
                action="widen_price_max",
                value=1.18,
                reason=f"Weak months: {', '.join((weak or trend.empty_months)[:4])}",
            )
        )
        actions.append(
            CritiqueAction(
                action="expand_zips",
                value=4,
                reason="Increase geographic coverage for thin months",
            )
        )
    if sc["mean_count"] < min_per_month:
        actions.append(
            CritiqueAction(
                action="relax_beds",
                value=1,
                reason="Mean monthly count below threshold",
            )
        )

    if not actions:
        actions.append(
            CritiqueAction(
                action="widen_sqft",
                value=1.1,
                reason="General coverage below threshold",
            )
        )

    return Critique(
        status=CritiqueStatus.REVISE,
        coverage_score=coverage,
        confidence=confidence,
        actions=actions,
        summary=f"Coverage {coverage:.2f} below {min_coverage}; requesting plan revision.",
    )


def run_critic_ollama(plan: QueryPlan, trend: TrendOutput) -> Critique:
    base = run_critic_mock(plan, trend)
    prompt = {
        "task": "Decide pass or revise for housing trend coverage.",
        "plan": plan.model_dump(),
        "trend_summary": {
            "coverage_score": trend.coverage_score,
            "total_listings": trend.total_listings,
            "empty_months": trend.empty_months,
            "monthly_counts": [m.active_count for m in trend.months],
        },
        "suggested": base.model_dump(),
        "allowed_actions": [
            "widen_price_max",
            "widen_price_min",
            "expand_zips",
            "relax_beds",
            "widen_sqft",
        ],
    }
    try:
        raw = ollama_generate(
            "You are the Critic Agent. Return JSON with keys status, coverage_score, "
            "confidence, actions, summary.\n" + json.dumps(prompt)
        )
        data = json.loads(raw)
        status = CritiqueStatus(data.get("status", base.status.value))
        actions = [CritiqueAction(**a) for a in data.get("actions", [])] or base.actions
        return Critique(
            status=status,
            coverage_score=float(data.get("coverage_score", base.coverage_score)),
            confidence=float(data.get("confidence", base.confidence)),
            actions=actions if status == CritiqueStatus.REVISE else [],
            summary=str(data.get("summary", base.summary)),
        )
    except Exception:
        return base
