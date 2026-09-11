"""Report Agent — package trend into user-facing narrative."""

from __future__ import annotations

import json

from lotline.llm import ollama_generate
from lotline.models import AgentReport, QueryPlan, TrendOutput


def run_report_mock(
    trend: TrendOutput,
    plan: QueryPlan,
    iterations: int,
    mode: str,
    trace: list[str],
) -> AgentReport:
    first = trend.months[0]
    last = trend.months[-1]
    yoy = trend.yoy_pct_change
    direction = "rose" if (yoy or 0) >= 0 else "softened"
    yoy_txt = f"{yoy:+.1f}%" if yoy is not None else "n/a"

    headline = (
        f"DFW median list price {direction} {yoy_txt} over the selected 12 months"
    )
    narrative = (
        f"Across {trend.total_listings:,} matching listings from {first.month} to "
        f"{last.month}, median price moved from "
        f"${first.median_price:,.0f} to ${last.median_price:,.0f} "
        f"({plan.currency_display}). Median $/sqft ended at "
        f"${last.median_price_per_sqft:,.0f}. Coverage score {trend.coverage_score:.2f} "
        f"after {iterations} agent iteration(s). "
        f"Active filters: ${plan.price_min:,.0f}–${plan.price_max:,.0f}, "
        f"{plan.beds_min}–{plan.beds_max} beds, {len(plan.zips)} ZIP codes."
    )
    return AgentReport(
        headline=headline,
        narrative=narrative,
        trend=trend,
        query_plan=plan,
        iterations=iterations,
        mode=mode,
        trace=trace,
    )


def run_report_ollama(
    trend: TrendOutput,
    plan: QueryPlan,
    iterations: int,
    mode: str,
    trace: list[str],
) -> AgentReport:
    base = run_report_mock(trend, plan, iterations, mode, trace)
    prompt = {
        "task": "Write a concise housing-trend headline and 2-3 sentence narrative.",
        "trend": trend.model_dump(),
        "plan": plan.model_dump(),
    }
    try:
        raw = ollama_generate(
            "You are the Report Agent for MetroMorph. Return JSON with headline and narrative.\n"
            + json.dumps(prompt)
        )
        data = json.loads(raw)
        return AgentReport(
            headline=str(data.get("headline", base.headline)),
            narrative=str(data.get("narrative", base.narrative)),
            trend=trend,
            query_plan=plan,
            iterations=iterations,
            mode=mode,
            trace=trace,
        )
    except Exception:
        return base
