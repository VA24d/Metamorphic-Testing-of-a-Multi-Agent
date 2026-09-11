"""Deterministic market-panel filters and 12-month trend computation.

Uses real public aggregates only:
- Zillow ZHVI by ZIP-month (`dallas_zhvi_zip_frozen.csv`)
- Redfin Dallas metro monthly metrics (`dallas_redfin_metro_frozen.csv`)

Each analysis row is one ZIP-month observation (not MLS micro-listings).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from lotline.models import MonthlyStat, QueryPlan, TrendOutput, UserCriteria

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
ZHVI_PATH = DATA_DIR / "dallas_zhvi_zip_frozen.csv"
REDFIN_PATH = DATA_DIR / "dallas_redfin_metro_frozen.csv"

DFW_ZIPS = [
    "75201",
    "75204",
    "75205",
    "75206",
    "75209",
    "75214",
    "75219",
    "75225",
    "75230",
    "75248",
    "75001",
    "75024",
    "75033",
    "75063",
    "76051",
    "76107",
]

LOCALITIES = {
    "75201": "Downtown Dallas",
    "75204": "Uptown",
    "75205": "Highland Park",
    "75206": "East Dallas",
    "75209": "Bluffview",
    "75214": "Lakewood",
    "75219": "Oak Lawn",
    "75225": "University Park",
    "75230": "North Dallas",
    "75248": "Far North Dallas",
    "75001": "Addison",
    "75024": "Plano",
    "75033": "Frisco",
    "75063": "Irving",
    "76051": "Grapevine",
    "76107": "Fort Worth Cultural District",
}


def load_market_panel(
    zhvi_path: Path | None = None,
    redfin_path: Path | None = None,
) -> pd.DataFrame:
    """ZIP-month panel: price=ZHVI, ppsf/inventory from Redfin metro join."""
    zhvi = pd.read_csv(zhvi_path or ZHVI_PATH, dtype={"zip": str})
    zhvi["zip"] = zhvi["zip"].astype(str).str.zfill(5)
    zhvi["list_month"] = zhvi["list_month"].astype(str)
    zhvi = zhvi.dropna(subset=["zhvi"])
    zhvi = zhvi[zhvi["zhvi"] > 0].copy()

    redfin = pd.read_csv(redfin_path or REDFIN_PATH)
    redfin["list_month"] = redfin["list_month"].astype(str)
    keep = ["list_month", "MEDIAN_PPSF", "INVENTORY", "MEDIAN_SALE_PRICE", "HOMES_SOLD"]
    keep = [c for c in keep if c in redfin.columns]
    redfin = redfin[keep].drop_duplicates("list_month")

    panel = zhvi.merge(redfin, on="list_month", how="left")
    panel["price"] = panel["zhvi"].astype(float)
    panel["ppsf"] = panel["MEDIAN_PPSF"].astype(float)
    # fallback ppsf if Redfin missing for a month
    panel["ppsf"] = panel["ppsf"].fillna(panel["price"] / 2000.0)
    panel["inventory"] = panel["INVENTORY"].fillna(0).astype(float)
    if "City" in panel.columns:
        panel["city"] = panel["City"].astype(str)
    else:
        panel["city"] = "Dallas"
    panel["locality"] = panel["zip"].map(LOCALITIES).fillna(panel["city"])
    panel["listing_id"] = panel["zip"] + "-" + panel["list_month"]
    panel["beds"] = None
    panel["sqft"] = None
    panel["state"] = "TX"
    panel["data_origin"] = "zillow_zhvi+redfin_metro"
    cols = [
        "listing_id",
        "price",
        "ppsf",
        "inventory",
        "beds",
        "sqft",
        "zip",
        "locality",
        "city",
        "state",
        "list_month",
        "zhvi",
        "data_origin",
    ]
    return panel[cols].sort_values(["list_month", "zip"]).reset_index(drop=True)


# Back-compat alias used across codebase
def load_listings(path: Path | None = None) -> pd.DataFrame:
    """Load the real market panel (path ignored; kept for call-site compatibility)."""
    return load_market_panel()


def shift_month(yyyy_mm: str, delta: int) -> str:
    y, m = map(int, yyyy_mm.split("-"))
    m0 = y * 12 + (m - 1) + delta
    y2, m2 = divmod(m0, 12)
    return f"{y2:04d}-{m2 + 1:02d}"


def window_months(window_end: str, n: int = 12) -> list[str]:
    return [shift_month(window_end, -i) for i in range(n - 1, -1, -1)]


def criteria_to_plan(criteria: UserCriteria, revision_round: int = 0) -> QueryPlan:
    zips = criteria.zips or list(DFW_ZIPS)
    notes = [
        "Initialized from user criteria",
        "Aggregate mode: filters use ZHVI (price) + ZIP/month; beds/sqft not in public feeds",
    ]
    return QueryPlan(
        price_min=criteria.price_min,
        price_max=criteria.price_max,
        beds_min=criteria.beds_min,
        beds_max=criteria.beds_max,
        sqft_min=criteria.sqft_min,
        sqft_max=criteria.sqft_max,
        zips=zips,
        window_start=shift_month(criteria.window_end, -11),
        window_end=criteria.window_end,
        currency_display=criteria.currency_display,
        area_unit=criteria.area_unit,
        notes=notes,
        revision_round=revision_round,
    )


def filter_listings(df: pd.DataFrame, plan: QueryPlan) -> pd.DataFrame:
    """Filter ZIP-month panel by window, ZIPs, and ZHVI price band."""
    months = set(window_months(plan.window_end, 12))
    out = df.copy()
    out = out[out["price"] > 0]
    out = out[out["list_month"].isin(months)]
    out = out[out["zip"].isin(plan.zips)]
    out = out[(out["price"] >= plan.price_min) & (out["price"] <= plan.price_max)]
    # beds/sqft intentionally not applied — not present in ZHVI/Redfin aggregates
    return out.reset_index(drop=True)


def _display_price(price: float, currency_display: str) -> float:
    if currency_display == "USD_THOUSANDS":
        return price / 1000.0
    return price


def compute_trend(df: pd.DataFrame, plan: QueryPlan) -> TrendOutput:
    """Per month: median ZHVI across ZIPs, median Redfin $/sqft, ZIP coverage count."""
    months = window_months(plan.window_end, 12)
    stats: list[MonthlyStat] = []
    empty: list[str] = []

    for m in months:
        sub = df[df["list_month"] == m]
        if sub.empty:
            empty.append(m)
            stats.append(
                MonthlyStat(
                    month=m,
                    median_price=0.0,
                    median_price_per_sqft=0.0,
                    active_count=0,
                )
            )
            continue

        med_price = float(np.median(sub["price"].to_numpy()))
        med_ppsf = float(np.median(sub["ppsf"].dropna().to_numpy())) if sub["ppsf"].notna().any() else 0.0
        # observation count (ZIP-month rows); unique ZIP coverage used in score_coverage via threshold
        active = int(len(sub))

        stats.append(
            MonthlyStat(
                month=m,
                median_price=_display_price(med_price, plan.currency_display),
                median_price_per_sqft=med_ppsf,
                active_count=active,
            )
        )

    yoy = None
    if stats[0].median_price > 0 and stats[-1].median_price > 0:
        yoy = (stats[-1].median_price - stats[0].median_price) / stats[0].median_price * 100.0

    counts = [s.active_count for s in stats]
    # Coverage: fraction of months with enough ZIP coverage (default threshold 4 ZIPs)
    coverage = float(np.mean([1.0 if c >= 4 else c / 4.0 for c in counts])) if counts else 0.0

    return TrendOutput(
        months=stats,
        yoy_pct_change=yoy,
        total_listings=int(len(df)),
        coverage_score=round(coverage, 4),
        empty_months=empty,
    )


def score_coverage(trend: TrendOutput, min_per_month: int = 4) -> dict:
    counts = [m.active_count for m in trend.months]
    weak = [m.month for m in trend.months if m.active_count < min_per_month]
    return {
        "coverage_score": trend.coverage_score,
        "weak_months": weak,
        "min_count": int(min(counts) if counts else 0),
        "mean_count": float(np.mean(counts) if counts else 0),
    }
