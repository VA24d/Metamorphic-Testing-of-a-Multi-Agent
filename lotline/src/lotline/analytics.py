"""Extra analytics derived from ZIP-month market panel + trend output."""

from __future__ import annotations

import numpy as np
import pandas as pd

from lotline.models import TrendOutput


def enrich_monthly(trend: TrendOutput) -> list[dict]:
    rows = []
    prev = None
    for m in trend.months:
        mom = None
        if prev and prev > 0 and m.median_price > 0:
            mom = (m.median_price - prev) / prev * 100.0
        rows.append(
            {
                "month": m.month,
                "median_price": m.median_price,
                "median_price_per_sqft": m.median_price_per_sqft,
                "active_count": m.active_count,
                "mom_pct_change": round(mom, 2) if mom is not None else None,
            }
        )
        prev = m.median_price
    return rows


def zip_breakdown(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    g = (
        df.groupby(["zip", "locality"], as_index=False)
        .agg(
            listings=("listing_id", "count"),
            median_price=("price", "median"),
            median_ppsf=("ppsf", "median"),
        )
        .sort_values("median_price", ascending=False)
    )
    return [
        {
            "zip": r.zip,
            "locality": r.locality,
            "listings": int(r.listings),
            "median_price": float(r.median_price),
            "median_ppsf": float(r.median_ppsf) if pd.notna(r.median_ppsf) else 0.0,
            "median_beds": 0.0,
            "median_sqft": 0.0,
        }
        for r in g.itertuples(index=False)
    ]


def beds_breakdown(df: pd.DataFrame) -> list[dict]:
    """Beds are not in public ZHVI/Redfin aggregates — return empty."""
    return []


def price_tier_breakdown(df: pd.DataFrame) -> list[dict]:
    """ZHVI price-tier mix (proxy chart — beds unavailable in public feeds)."""
    if df.empty or "price" not in df.columns:
        return []
    prices = df["price"].dropna()
    prices = prices[prices > 0]
    if prices.empty:
        return []

    # Fixed DFW-oriented tiers so the chart stays comparable across queries
    edges = [0, 300_000, 450_000, 600_000, 800_000, 1_200_000, float("inf")]
    labels = ["<$300k", "$300–450k", "$450–600k", "$600–800k", "$800k–1.2M", "$1.2M+"]
    cats = pd.cut(prices, bins=edges, labels=labels, right=False)
    out: list[dict] = []
    for label in labels:
        mask = cats == label
        subset = prices[mask]
        if len(subset) == 0:
            continue
        out.append(
            {
                "tier": str(label),
                "listings": int(len(subset)),
                "median_price": float(np.median(subset)),
            }
        )
    return out


def price_histogram(df: pd.DataFrame, bins: int = 12) -> list[dict]:
    if df.empty:
        return []
    prices = df["price"].to_numpy()
    counts, edges = np.histogram(prices, bins=min(bins, max(3, len(np.unique(prices)))))
    out = []
    for i, c in enumerate(counts):
        lo = float(edges[i])
        hi = float(edges[i + 1])
        out.append(
            {
                "bucket": f"${lo:,.0f}–${hi:,.0f}",
                "lo": lo,
                "hi": hi,
                "count": int(c),
            }
        )
    return out


def locality_share(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    g = df.groupby("locality", as_index=False).agg(listings=("listing_id", "count"))
    total = g["listings"].sum() or 1
    g["share_pct"] = g["listings"] / total * 100.0
    g = g.sort_values("listings", ascending=False).head(10)
    return [
        {"locality": r.locality, "listings": int(r.listings), "share_pct": float(r.share_pct)}
        for r in g.itertuples(index=False)
    ]


def overview_kpis(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "listings": 0,
            "median_price": 0,
            "median_ppsf": 0,
            "median_sqft": 0,
            "zips": 0,
            "localities": 0,
        }
    return {
        "listings": int(len(df)),
        "median_price": float(np.median(df["price"])),
        "median_ppsf": float(np.median(df["ppsf"].dropna())) if df["ppsf"].notna().any() else 0.0,
        "median_sqft": 0.0,
        "zips": int(df["zip"].nunique()),
        "localities": int(df["locality"].nunique()),
    }


def market_snapshot(df: pd.DataFrame) -> dict:
    """Unfiltered market-panel snapshot for landing analytics."""
    clean = df[df["price"] > 0].copy()
    months = (
        clean.groupby("list_month", as_index=False)
        .agg(median_price=("price", "median"), active_count=("zip", "nunique"))
        .sort_values("list_month")
    )
    return {
        "total_listings": int(len(clean)),
        "zip_count": int(clean["zip"].nunique()),
        "month_span": int(clean["list_month"].nunique()),
        "median_price": float(np.median(clean["price"])),
        "monthly": months.to_dict(orient="records"),
        "top_zips": zip_breakdown(clean)[:8],
        "beds": [],
        "price_tiers": price_tier_breakdown(clean),
        "price_hist": price_histogram(clean),
        "localities": locality_share(clean),
    }
