"""FastAPI backend for MetroMorph React UI."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lotline.analytics import (
    beds_breakdown,
    enrich_monthly,
    locality_share,
    market_snapshot,
    overview_kpis,
    price_histogram,
    price_tier_breakdown,
    zip_breakdown,
)
from lotline.chat_parser import EXAMPLE_QUESTIONS, parse_question
from lotline.llm import ollama_available, resolve_mode
from lotline.models import UserCriteria
from lotline.orchestrator import run_pipeline
from lotline.tools import DFW_ZIPS, filter_listings, load_listings, criteria_to_plan

app = FastAPI(title="MetroMorph API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_DF = None


def get_df():
    global _DF
    if _DF is None:
        _DF = load_listings()
    return _DF


class ChatRequest(BaseModel):
    message: str
    mode: str | None = "auto"  # auto | mock | ollama
    max_iterations: int = 3


class QueryRequest(BaseModel):
    price_min: float = 150_000
    price_max: float = 650_000
    beds_min: int = 2
    beds_max: int = 5
    sqft_min: float = 800
    sqft_max: float = 4_000
    zips: list[str] = Field(default_factory=list)
    window_end: str | None = None
    mode: str | None = "auto"
    max_iterations: int = 3


def _pack_result(result, interpretation: str | None = None, criteria: UserCriteria | None = None):
    report = result.report
    trend = report.trend
    plan = report.query_plan
    # Re-filter for analytics extras using final plan
    df = get_df()
    filtered = filter_listings(df, plan)
    monthly = enrich_monthly(trend)
    return {
        "interpretation": interpretation,
        "criteria": criteria.model_dump() if criteria else None,
        "headline": report.headline,
        "narrative": report.narrative,
        "mode": report.mode,
        "iterations": report.iterations,
        "trace": report.trace,
        "agent_steps": [s.model_dump() for s in result.agent_steps],
        "query_plan": plan.model_dump(),
        "trend": trend.model_dump(),
        "monthly": monthly,
        "filtered_count": result.filtered_count,
        "listings_preview": result.listings_preview,
        "analytics": {
            "kpis": overview_kpis(filtered),
            "by_zip": zip_breakdown(filtered),
            "by_beds": beds_breakdown(filtered),
            "by_price_tier": price_tier_breakdown(filtered),
            "price_histogram": price_histogram(filtered),
            "locality_share": locality_share(filtered),
        },
    }


@app.get("/api/health")
def health():
    df = get_df()
    return {
        "ok": True,
        "listings": int(len(df)),
        "ollama": ollama_available(),
        "mode_default": resolve_mode(),
        "zips": DFW_ZIPS,
        "examples": EXAMPLE_QUESTIONS,
    }


@app.get("/api/snapshot")
def snapshot():
    return market_snapshot(get_df())


@app.post("/api/chat")
def chat(req: ChatRequest):
    df = get_df()
    mode = None if req.mode in (None, "auto") else req.mode
    resolved = resolve_mode(mode)
    window_end = sorted(df["list_month"].unique().tolist())[-1]
    criteria, interpretation = parse_question(
        req.message, mode=resolved, default_window_end=window_end
    )
    result = run_pipeline(
        criteria, df=df, mode=resolved, max_iterations=req.max_iterations
    )
    return _pack_result(result, interpretation=interpretation, criteria=criteria)


@app.post("/api/query")
def query(req: QueryRequest):
    df = get_df()
    mode = None if req.mode in (None, "auto") else req.mode
    resolved = resolve_mode(mode)
    window_end = req.window_end or sorted(df["list_month"].unique().tolist())[-1]
    criteria = UserCriteria(
        price_min=req.price_min,
        price_max=req.price_max,
        beds_min=req.beds_min,
        beds_max=req.beds_max,
        sqft_min=req.sqft_min,
        sqft_max=req.sqft_max,
        zips=req.zips,
        window_end=window_end,
    )
    result = run_pipeline(
        criteria, df=df, mode=resolved, max_iterations=req.max_iterations
    )
    return _pack_result(result, interpretation="Structured query", criteria=criteria)


class MrRunRequest(BaseModel):
    n: int = Field(default=15, ge=1, le=50)
    seed: int = 7
    mrs: list[str] | None = None  # None / empty = all; e.g. ["MR3"] or ["MR3_duplicate"]
    verbose: bool = True
    no_smoke: bool = False
    # Attach mock agent pipeline traces for the first N cases (UI linkage; not used for pass/fail)
    agent_trace_cases: int = Field(default=3, ge=0, le=50)


@app.get("/api/mrs/list")
def mrs_list():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from harness.mrs import MR_CATALOG, MR_FUNCS

    return {
        "mrs": list(MR_FUNCS.keys()),
        "catalog": MR_CATALOG,
        "metrics_glossary": {
            "median_price": "Monthly median ZHVI (or scaled display) in the matched ZIP set",
            "median_ppsf": "Monthly median price per sqft (Redfin metro join / scaled)",
            "active_count": "Count of ZIP-month rows matched that month",
            "yoy_pct_change": "Year-over-year % change of latest vs 12 months earlier median",
            "coverage_score": "Fraction of window months with ≥1 observation",
        },
        "data": {
            "panel": "Frozen Zillow ZHVI ZIP-month + Redfin Dallas metro",
            "rows": int(len(get_df())),
            "zips": 16,
            "note": "Criteria seed randomizes queries only; market panel is fixed.",
        },
    }


@app.get("/api/mrs/summary")
def mrs_summary():
    """Return last saved harness JSON if present."""
    import json

    path = ROOT / "harness" / "results_table.json"
    if not path.exists():
        return {"available": False, "results": [], "message": "No saved results yet — run MRs from the UI or CLI."}
    return {"available": True, **json.loads(path.read_text())}


@app.post("/api/mrs/run")
def mrs_run(req: MrRunRequest):
    """Run all or selected metamorphic relations and return violation rates + CIs."""
    import json

    from fastapi import HTTPException

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import numpy as np
    from harness.mrs import agent_loop_smoke
    from harness.run_harness import make_base_inputs, resolve_mrs, run_one_mr

    try:
        selected = resolve_mrs(req.mrs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    rng = np.random.default_rng(req.seed)
    df = get_df()
    bases = make_base_inputs(req.n, rng)

    smoke = None
    if not req.no_smoke:
        smoke = agent_loop_smoke(df, bases[0])

    rows = []
    for mr_id, fn in selected.items():
        row = run_one_mr(
            mr_id,
            fn,
            df,
            bases,
            req.seed,
            agent_trace_cases=req.agent_trace_cases,
        )
        if not req.verbose:
            row = {k: v for k, v in row.items() if k != "cases"}
        rows.append(row)

    payload = {
        "available": True,
        "seed": req.seed,
        "n_base_inputs": req.n,
        "selected_mrs": list(selected),
        "smoke": smoke.__dict__ if smoke else None,
        "results": rows,
    }

    # Persist: full suite → results_table.json; single MR → results_<id>.json
    if req.mrs and len(selected) == 1:
        only = next(iter(selected))
        out = ROOT / "harness" / f"results_{only}.json"
    else:
        out = ROOT / "harness" / "results_table.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    payload["saved_to"] = str(out.relative_to(ROOT))
    return payload
