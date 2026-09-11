"""Metamorphic relation definitions and checkers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd

from lotline.models import TrendOutput, UserCriteria
from lotline.orchestrator import run_pipeline
from lotline.tools import compute_trend, criteria_to_plan, filter_listings, shift_month


@dataclass
class MRResult:
    mr_id: str
    passed: bool
    detail: str
    metrics: dict[str, Any] = field(default_factory=dict)


def _prices(t: TrendOutput) -> np.ndarray:
    return np.array([m.median_price for m in t.months], dtype=float)


def _ppsf(t: TrendOutput) -> np.ndarray:
    return np.array([m.median_price_per_sqft for m in t.months], dtype=float)


def _counts(t: TrendOutput) -> np.ndarray:
    return np.array([m.active_count for m in t.months], dtype=float)


def _approx(a: np.ndarray, b: np.ndarray, rtol: float = 1e-9, atol: float = 1e-6) -> bool:
    if a.shape != b.shape:
        return False
    return bool(np.allclose(a, b, rtol=rtol, atol=atol, equal_nan=True))


def _series(t: TrendOutput) -> dict[str, Any]:
    return {
        "months": [m.month for m in t.months],
        "median_price": [round(float(m.median_price), 2) for m in t.months],
        "median_ppsf": [round(float(m.median_price_per_sqft), 4) for m in t.months],
        "active_count": [int(m.active_count) for m in t.months],
        "yoy_pct_change": None if t.yoy_pct_change is None else round(float(t.yoy_pct_change), 6),
        "total_listings": int(t.total_listings),
        "coverage_score": round(float(t.coverage_score), 4),
    }


def _pack(
    mr_id: str,
    ok: bool,
    detail: str,
    *,
    transform: str,
    expect: str,
    checks: dict[str, bool],
    source: TrendOutput | None = None,
    followup: TrendOutput | None = None,
    extra: dict[str, Any] | None = None,
) -> MRResult:
    metrics: dict[str, Any] = {
        "transform": transform,
        "expect": expect,
        "checks": checks,
    }
    if source is not None:
        metrics["source"] = _series(source)
    if followup is not None:
        metrics["followup"] = _series(followup)
    if extra:
        metrics.update(extra)
    return MRResult(mr_id, ok, detail, metrics)


def run_trend(df: pd.DataFrame, criteria: UserCriteria) -> TrendOutput:
    """Deterministic path used by most MRs (stable measurement)."""
    plan = criteria_to_plan(criteria)
    filtered = filter_listings(df, plan)
    return compute_trend(filtered, plan)


# ----- transforms -----

def transform_reorder(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    return df.sample(frac=1.0, random_state=int(rng.integers(0, 1_000_000))).reset_index(drop=True)


def transform_duplicate(df: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([df, df], ignore_index=True)


def transform_scale_prices(df: pd.DataFrame, k: float) -> pd.DataFrame:
    out = df.copy()
    out.loc[out["price"] > 0, "price"] = out.loc[out["price"] > 0, "price"] * k
    if "ppsf" in out.columns:
        out.loc[out["ppsf"] > 0, "ppsf"] = out.loc[out["ppsf"] > 0, "ppsf"] * k
    if "zhvi" in out.columns:
        out.loc[out["zhvi"] > 0, "zhvi"] = out.loc[out["zhvi"] > 0, "zhvi"] * k
    return out


def transform_add_month_prices(df: pd.DataFrame, month: str, x: float) -> pd.DataFrame:
    out = df.copy()
    mask = (out["list_month"] == month) & (out["price"] > 0)
    out.loc[mask, "price"] = out.loc[mask, "price"] + x
    return out


# ----- MR checkers -----

def mr_reorder(df: pd.DataFrame, criteria: UserCriteria, rng: np.random.Generator) -> MRResult:
    a = run_trend(df, criteria)
    b = run_trend(transform_reorder(df, rng), criteria)
    checks = {
        "median_price_equal": _approx(_prices(a), _prices(b)),
        "median_ppsf_equal": _approx(_ppsf(a), _ppsf(b)),
        "active_count_equal": _approx(_counts(a), _counts(b)),
    }
    ok = all(checks.values())
    return _pack(
        "MR1_reorder",
        ok,
        "stats identical after shuffle" if ok else "mismatch after reorder",
        transform="Shuffle ZIP-month row order (same data)",
        expect="median_price, median_ppsf, active_count unchanged",
        checks=checks,
        source=a,
        followup=b,
    )


def mr_currency_display(df: pd.DataFrame, criteria: UserCriteria, rng: np.random.Generator) -> MRResult:
    c1 = criteria.model_copy(update={"currency_display": "USD"})
    c2 = criteria.model_copy(update={"currency_display": "USD_THOUSANDS"})
    a = run_trend(df, c1)
    b = run_trend(df, c2)
    counts_ok = _approx(_counts(a), _counts(b))
    scale_ok = _approx(_prices(a) / 1000.0, _prices(b), rtol=1e-9, atol=1e-6)
    yoy_ok = True
    if a.yoy_pct_change is not None and b.yoy_pct_change is not None:
        yoy_ok = abs(a.yoy_pct_change - b.yoy_pct_change) < 1e-6
    checks = {
        "active_count_equal": counts_ok,
        "prices_followup_equals_source_div_1000": scale_ok,
        "yoy_pct_equal": yoy_ok,
    }
    ok = all(checks.values())
    return _pack(
        "MR2_currency_display",
        ok,
        "counts+yoy invariant; prices /1000" if ok else "currency relation failed",
        transform="Display currency USD → USD_THOUSANDS (÷1000)",
        expect="counts & YoY same; median_price_B ≈ median_price_A / 1000",
        checks=checks,
        source=a,
        followup=b,
    )


def mr_duplicate(df: pd.DataFrame, criteria: UserCriteria, rng: np.random.Generator) -> MRResult:
    a = run_trend(df, criteria)
    b = run_trend(transform_duplicate(df), criteria)
    med_ok = _approx(_prices(a), _prices(b)) and _approx(_ppsf(a), _ppsf(b), rtol=1e-9, atol=1e-4)
    count_ok = _approx(_counts(b), _counts(a) * 2)
    checks = {
        "median_price_equal": _approx(_prices(a), _prices(b)),
        "median_ppsf_equal": _approx(_ppsf(a), _ppsf(b), rtol=1e-9, atol=1e-4),
        "active_count_followup_equals_2x": count_ok,
    }
    ok = med_ok and count_ok
    return _pack(
        "MR3_duplicate",
        ok,
        "medians same, counts×2" if ok else "duplicate relation failed",
        transform="Duplicate every ZIP-month row (concat panel with itself)",
        expect="medians unchanged; active_count_B = 2 × active_count_A",
        checks=checks,
        source=a,
        followup=b,
    )


def mr_add_price_month(df: pd.DataFrame, criteria: UserCriteria, rng: np.random.Generator) -> MRResult:
    """Add +X to one month on the *already filtered* set so band membership stays fixed."""
    from lotline.tools import window_months

    plan = criteria_to_plan(criteria)
    months = window_months(plan.window_end, 12)
    target = months[int(rng.integers(0, 12))]
    x = 25_000.0
    filtered = filter_listings(df, plan)
    a = compute_trend(filtered, plan)
    idx = months.index(target)
    if a.months[idx].active_count == 0:
        return _pack(
            "MR4_add_month_price",
            True,
            f"skipped empty month {target}",
            transform=f"Add +{x:.0f} to prices in month {target}",
            expect="target month median rises by X; other months unchanged",
            checks={"skipped_empty_month": True},
            source=a,
            extra={"target_month": target, "delta": x},
        )

    bumped = filtered.copy()
    mask = bumped["list_month"] == target
    bumped.loc[mask, "price"] = bumped.loc[mask, "price"] + x
    b = compute_trend(bumped, plan)

    expected = a.months[idx].median_price + x
    rose = abs(b.months[idx].median_price - expected) <= 1.0
    others_ok = all(
        abs(a.months[i].median_price - b.months[i].median_price) <= 1e-6
        for i in range(12)
        if i != idx
    )
    checks = {
        "target_median_rose_by_x": rose,
        "other_months_unchanged": others_ok,
    }
    ok = rose and others_ok
    return _pack(
        "MR4_add_month_price",
        ok,
        f"+{x:.0f} on {target}" if ok else f"failed on {target}",
        transform=f"Add +{x:.0f} to filtered prices in month {target}",
        expect="target median_price +X; other months identical",
        checks=checks,
        source=a,
        followup=b,
        extra={
            "target_month": target,
            "delta": x,
            "source_target_median": round(float(a.months[idx].median_price), 2),
            "followup_target_median": round(float(b.months[idx].median_price), 2),
            "expected_target_median": round(float(expected), 2),
        },
    )


def mr_widen_price_band(df: pd.DataFrame, criteria: UserCriteria, rng: np.random.Generator) -> MRResult:
    wide = criteria.model_copy(
        update={
            "price_min": max(50_000, criteria.price_min * 0.85),
            "price_max": criteria.price_max * 1.2,
        }
    )
    a = run_trend(df, criteria)
    b = run_trend(df, wide)
    ok = bool(np.all(_counts(b) + 1e-9 >= _counts(a)))
    checks = {"active_count_monotone_nondecreasing": ok}
    return _pack(
        "MR5_widen_band",
        ok,
        "counts monotone non-decreasing" if ok else "widen band violated",
        transform="Widen price band (min×0.85, max×1.2)",
        expect="active_count_B[m] ≥ active_count_A[m] for all months",
        checks=checks,
        source=a,
        followup=b,
        extra={
            "source_band": [criteria.price_min, criteria.price_max],
            "followup_band": [wide.price_min, wide.price_max],
        },
    )


def mr_subregion(df: pd.DataFrame, criteria: UserCriteria, rng: np.random.Generator) -> MRResult:
    from lotline.tools import DFW_ZIPS

    zips = criteria.zips or list(DFW_ZIPS)
    if len(zips) < 2:
        return _pack(
            "MR6_subregion",
            True,
            "skipped — need ≥2 zips",
            transform="Compare ZIP subset vs full ZIP set",
            expect="subset active_count ≤ full active_count",
            checks={"skipped_too_few_zips": True},
        )
    sub = criteria.model_copy(update={"zips": zips[: max(1, len(zips) // 2)]})
    full = criteria.model_copy(update={"zips": zips})
    a = run_trend(df, sub)
    b = run_trend(df, full)
    ok = bool(np.all(_counts(a) <= _counts(b) + 1e-9))
    checks = {"subset_counts_le_full": ok}
    return _pack(
        "MR6_subregion",
        ok,
        "subset counts ≤ full" if ok else "subregion violated",
        transform="ZIP subset (first half) vs full ZIP list",
        expect="active_count_subset ≤ active_count_full every month",
        checks=checks,
        source=a,
        followup=b,
        extra={"subset_zips": sub.zips, "full_zips": full.zips},
    )


def mr_shift_window(df: pd.DataFrame, criteria: UserCriteria, rng: np.random.Generator) -> MRResult:
    end = criteria.window_end
    shifted = criteria.model_copy(update={"window_end": shift_month(end, 1)})
    if shifted.window_end > df["list_month"].max():
        return _pack(
            "MR7_shift_window",
            True,
            "skipped — no room to shift",
            transform="Shift 12-month window end by +1 month",
            expect="11-month overlapping medians & counts match",
            checks={"skipped_no_room": True},
        )
    a = run_trend(df, criteria)
    b = run_trend(df, shifted)
    ok_p = _approx(_prices(a)[1:], _prices(b)[:-1], rtol=1e-9, atol=1e-6)
    ok_c = _approx(_counts(a)[1:], _counts(b)[:-1])
    checks = {
        "overlap_median_price_equal": ok_p,
        "overlap_active_count_equal": ok_c,
    }
    ok = ok_p and ok_c
    return _pack(
        "MR7_shift_window",
        ok,
        "11-month overlap matches" if ok else "overlap mismatch",
        transform=f"window_end {end} → {shifted.window_end}",
        expect="A.months[1:] == B.months[:-1] for price & count",
        checks=checks,
        source=a,
        followup=b,
        extra={"window_end_source": end, "window_end_followup": shifted.window_end},
    )


def mr_scale_prices(df: pd.DataFrame, criteria: UserCriteria, rng: np.random.Generator) -> MRResult:
    """Scale prices on the filtered set (avoids price-band membership artifacts)."""
    k = 1.25
    c = criteria.model_copy(update={"currency_display": "USD"})
    plan = criteria_to_plan(c)
    filtered = filter_listings(df, plan)
    a = compute_trend(filtered, plan)
    scaled = transform_scale_prices(filtered, k)
    b = compute_trend(scaled, plan)
    price_ok = _approx(_prices(b), _prices(a) * k, rtol=1e-6, atol=1e-3)
    ppsf_ok = _approx(_ppsf(b), _ppsf(a) * k, rtol=1e-6, atol=1e-3)
    yoy_ok = True
    if a.yoy_pct_change is not None and b.yoy_pct_change is not None:
        yoy_ok = abs(a.yoy_pct_change - b.yoy_pct_change) < 1e-4
    checks = {
        "median_price_scaled_by_k": price_ok,
        "median_ppsf_scaled_by_k": ppsf_ok,
        "yoy_pct_invariant": yoy_ok,
    }
    ok = price_ok and ppsf_ok and yoy_ok
    return _pack(
        "MR8_scale_k",
        ok,
        f"scaled by {k}" if ok else "scale relation failed",
        transform=f"Multiply filtered price & ppsf by k={k}",
        expect="medians ×k; YoY % unchanged",
        checks=checks,
        source=a,
        followup=b,
        extra={"k": k},
    )


MR_FUNCS: dict[str, Callable] = {
    "MR1_reorder": mr_reorder,
    "MR2_currency_display": mr_currency_display,
    "MR3_duplicate": mr_duplicate,
    "MR4_add_month_price": mr_add_price_month,
    "MR5_widen_band": mr_widen_price_band,
    "MR6_subregion": mr_subregion,
    "MR7_shift_window": mr_shift_window,
    "MR8_scale_k": mr_scale_prices,
}


# Catalog for UI / docs (transform + metrics + agents under test)
MR_CATALOG: list[dict[str, Any]] = [
    {
        "id": "MR1_reorder",
        "family": "invariance",
        "title": "Row reorder",
        "transform": "Shuffle ZIP-month rows",
        "metrics": ["median_price", "median_ppsf", "active_count"],
        "expect": "All three series identical after shuffle",
        "agents": ["Scanner", "Analyst"],
        "agent_rationale": "Scanner row order must not change Analyst monthly medians/counts.",
    },
    {
        "id": "MR2_currency_display",
        "family": "invariance",
        "title": "Currency display",
        "transform": "USD → USD_THOUSANDS (÷1000)",
        "metrics": ["median_price", "active_count", "yoy_pct_change"],
        "expect": "counts & YoY same; prices scale by 1/1000",
        "agents": ["Analyst", "Report"],
        "agent_rationale": "Analyst/Report display scaling must preserve counts and YoY %.",
    },
    {
        "id": "MR3_duplicate",
        "family": "invariance",
        "title": "Duplicate panel",
        "transform": "Concatenate panel with itself",
        "metrics": ["median_price", "median_ppsf", "active_count"],
        "expect": "medians same; counts ×2",
        "agents": ["Scanner", "Analyst"],
        "agent_rationale": "Scanner duplicate rows; Analyst medians stable, counts scale.",
    },
    {
        "id": "MR4_add_month_price",
        "family": "additive",
        "title": "Add +$X one month",
        "transform": "Add +25000 to one month’s prices",
        "metrics": ["median_price (target month)", "median_price (other months)"],
        "expect": "target median +25000; others unchanged",
        "agents": ["Analyst"],
        "agent_rationale": "Analyst monthly median must move only for the bumped month.",
    },
    {
        "id": "MR5_widen_band",
        "family": "monotonic",
        "title": "Widen price band",
        "transform": "price_min×0.85, price_max×1.2",
        "metrics": ["active_count"],
        "expect": "counts never decrease",
        "agents": ["Criteria", "Scanner", "Critic"],
        "agent_rationale": "Criteria/Scanner wider band; Critic coverage should not shrink.",
    },
    {
        "id": "MR6_subregion",
        "family": "monotonic",
        "title": "ZIP subset",
        "transform": "Half of ZIPs vs full set",
        "metrics": ["active_count"],
        "expect": "subset counts ≤ full counts",
        "agents": ["Criteria", "Scanner"],
        "agent_rationale": "Criteria ZIP plan + Scanner filter: subset ⊆ full.",
    },
    {
        "id": "MR7_shift_window",
        "family": "consistency",
        "title": "Shift window +1mo",
        "transform": "window_end += 1 month",
        "metrics": ["median_price (11-mo overlap)", "active_count (overlap)"],
        "expect": "overlapping months match",
        "agents": ["Criteria", "Analyst"],
        "agent_rationale": "Criteria window + Analyst series must agree on overlapping months.",
    },
    {
        "id": "MR8_scale_k",
        "family": "multiplicative",
        "title": "Scale prices ×1.25",
        "transform": "Multiply price & ppsf by 1.25",
        "metrics": ["median_price", "median_ppsf", "yoy_pct_change"],
        "expect": "medians ×1.25; YoY % invariant",
        "agents": ["Analyst", "Report"],
        "agent_rationale": "Analyst scaled levels; Report YoY % unchanged under uniform scale.",
    },
]

MR_CATALOG_BY_ID: dict[str, dict[str, Any]] = {c["id"]: c for c in MR_CATALOG}


def agent_loop_smoke(df: pd.DataFrame, criteria: UserCriteria) -> MRResult:
    """Optional: ensure orchestrator loop runs (not a formal MR)."""
    result = run_pipeline(criteria, df=df, mode="mock", max_iterations=3)
    ok = result.report.trend.total_listings >= 0 and len(result.report.trace) > 0
    return MRResult("SMOKE_agent_loop", ok, " | ".join(result.report.trace[-3:]))


def capture_agent_trace(df: pd.DataFrame, criteria: UserCriteria, max_iterations: int = 3) -> dict[str, Any]:
    """Run mock multi-agent pipeline for UI linkage (does not affect MR pass/fail)."""
    result = run_pipeline(criteria, df=df, mode="mock", max_iterations=max_iterations)
    steps = []
    for s in result.agent_steps:
        steps.append(
            {
                "agent": s.agent,
                "iteration": s.iteration,
                "status": s.status,
                "summary": s.summary,
                "details": s.details if isinstance(s.details, dict) else {},
            }
        )
    return {
        "mode": result.report.mode,
        "iterations": result.report.iterations,
        "trace": list(result.report.trace),
        "agent_steps": steps,
        "headline": result.report.headline,
    }