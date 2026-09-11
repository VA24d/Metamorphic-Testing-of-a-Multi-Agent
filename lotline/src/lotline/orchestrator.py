"""Multi-agent orchestrator with Critic feedback loop."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from lotline.agents.analyst import run_analyst
from lotline.agents.criteria import run_criteria_mock, run_criteria_ollama
from lotline.agents.critic import run_critic_mock, run_critic_ollama
from lotline.agents.report import run_report_mock, run_report_ollama
from lotline.agents.scanner import run_scanner
from lotline.llm import resolve_mode
from lotline.models import AgentStepResult, CritiqueStatus, PipelineResult, UserCriteria
from lotline.tools import load_listings


def run_pipeline(
    criteria: UserCriteria,
    df: pd.DataFrame | None = None,
    mode: str | None = None,
    max_iterations: int = 3,
    data_path: Path | None = None,
) -> PipelineResult:
    mode = resolve_mode(mode)
    listings_df = df if df is not None else load_listings(data_path)

    trace: list[str] = [f"mode={mode}"]
    agent_steps: list[AgentStepResult] = []
    critique = None
    plan = None
    trend = None
    filtered = pd.DataFrame()

    for i in range(1, max_iterations + 1):
        if mode == "ollama":
            plan = run_criteria_ollama(criteria, critique=critique, prior=plan)
        else:
            plan = run_criteria_mock(criteria, critique=critique, prior=plan)

        criteria_summary = (
            f"Built query plan: ${plan.price_min:,.0f}–${plan.price_max:,.0f}, "
            f"{plan.beds_min}–{plan.beds_max} beds, {len(plan.zips)} ZIPs, "
            f"window {plan.window_start}→{plan.window_end} (rev #{plan.revision_round})"
        )
        trace.append(
            f"iter={i} criteria → price {plan.price_min:.0f}-{plan.price_max:.0f}, "
            f"zips={len(plan.zips)}, beds={plan.beds_min}-{plan.beds_max}"
        )
        agent_steps.append(
            AgentStepResult(
                agent="Criteria",
                iteration=i,
                status="ok",
                summary=criteria_summary,
                details={
                    "price_min": plan.price_min,
                    "price_max": plan.price_max,
                    "beds_min": plan.beds_min,
                    "beds_max": plan.beds_max,
                    "sqft_min": plan.sqft_min,
                    "sqft_max": plan.sqft_max,
                    "zips": plan.zips,
                    "window_start": plan.window_start,
                    "window_end": plan.window_end,
                    "notes": plan.notes[-5:],
                    "revision_round": plan.revision_round,
                },
            )
        )

        filtered = run_scanner(listings_df, plan)
        by_month = (
            filtered.groupby("list_month").size().astype(int).to_dict()
            if len(filtered)
            else {}
        )
        scanner_summary = f"Retrieved {len(filtered):,} matching listings from local dataset"
        trace.append(f"iter={i} scanner → {len(filtered)} listings")
        agent_steps.append(
            AgentStepResult(
                agent="Scanner",
                iteration=i,
                status="ok",
                summary=scanner_summary,
                details={
                    "matched_listings": int(len(filtered)),
                    "unique_zips": sorted(filtered["zip"].unique().tolist())[:20]
                    if len(filtered)
                    else [],
                    "counts_by_month": by_month,
                    "sample_ids": filtered["listing_id"].head(8).tolist()
                    if len(filtered)
                    else [],
                },
            )
        )

        trend = run_analyst(filtered, plan)
        first = trend.months[0] if trend.months else None
        last = trend.months[-1] if trend.months else None
        analyst_summary = (
            f"Computed 12-month trend · coverage {trend.coverage_score:.2f} · "
            f"YoY {trend.yoy_pct_change:+.1f}%"
            if trend.yoy_pct_change is not None
            else f"Computed 12-month trend · coverage {trend.coverage_score:.2f}"
        )
        trace.append(
            f"iter={i} analyst → coverage={trend.coverage_score:.2f}, "
            f"total={trend.total_listings}"
        )
        agent_steps.append(
            AgentStepResult(
                agent="Analyst",
                iteration=i,
                status="ok",
                summary=analyst_summary,
                details={
                    "total_listings": trend.total_listings,
                    "coverage_score": trend.coverage_score,
                    "yoy_pct_change": trend.yoy_pct_change,
                    "empty_months": trend.empty_months,
                    "first_month": first.model_dump() if first else None,
                    "last_month": last.model_dump() if last else None,
                    "monthly": [m.model_dump() for m in trend.months],
                },
            )
        )

        if mode == "ollama":
            critique = run_critic_ollama(plan, trend)
        else:
            critique = run_critic_mock(plan, trend)

        if critique.status == CritiqueStatus.PASS:
            trace.append(f"iter={i} critic → PASS ({critique.summary})")
            agent_steps.append(
                AgentStepResult(
                    agent="Critic",
                    iteration=i,
                    status="pass",
                    summary=f"PASS — {critique.summary}",
                    details={
                        "status": critique.status.value,
                        "coverage_score": critique.coverage_score,
                        "confidence": critique.confidence,
                        "actions": [],
                    },
                )
            )
            break

        actions = ", ".join(a.action for a in critique.actions) or "none"
        trace.append(
            f"iter={i} critic → REVISE [{actions}] coverage={critique.coverage_score:.2f}"
        )
        agent_steps.append(
            AgentStepResult(
                agent="Critic",
                iteration=i,
                status="revise",
                summary=f"REVISE — {critique.summary}",
                details={
                    "status": critique.status.value,
                    "coverage_score": critique.coverage_score,
                    "confidence": critique.confidence,
                    "actions": [a.model_dump() for a in critique.actions],
                },
            )
        )
        # feedback loop continues — Criteria will apply actions next round
    else:
        trace.append("max_iterations reached — accepting best-effort trend")

    assert plan is not None and trend is not None

    if mode == "ollama":
        report = run_report_ollama(trend, plan, i, mode, trace)
    else:
        report = run_report_mock(trend, plan, i, mode, trace)

    agent_steps.append(
        AgentStepResult(
            agent="Report",
            iteration=i,
            status="ok",
            summary=report.headline,
            details={
                "headline": report.headline,
                "narrative": report.narrative,
                "iterations": report.iterations,
                "mode": report.mode,
            },
        )
    )

    preview_cols = [
        "listing_id",
        "price",
        "ppsf",
        "zip",
        "locality",
        "city",
        "list_month",
        "data_origin",
    ]
    preview_df = filtered.head(25)[[c for c in preview_cols if c in filtered.columns]].copy()
    preview = preview_df.where(preview_df.notna(), None).to_dict(orient="records")
    return PipelineResult(
        report=report,
        listings_preview=preview,
        filtered_count=int(len(filtered)),
        agent_steps=agent_steps,
    )
