#!/usr/bin/env python3
"""Freeze Dallas slices from free public Zillow + Redfin CSVs (no synthetic listings).

Sources (no login):
- Zillow Research ZHVI ZIP / metro — https://www.zillow.com/research/data/
- Redfin Data Center metro tracker — https://www.redfin.com/news/data-center/

MetroMorph analyzes these aggregate ZIP-month / metro-month series directly.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data"

TARGET_ZIPS = [
    "75201", "75204", "75205", "75206", "75209", "75214", "75219", "75225",
    "75230", "75248", "75001", "75024", "75033", "75063", "76051", "76107",
]


def _month_key(col: str) -> str:
    return str(col)[:7]


def freeze_zhvi_zip() -> pd.DataFrame:
    z = pd.read_csv(RAW / "zhvi_zip.csv", dtype={"RegionName": str}, low_memory=False)
    z = z.copy()
    z["zip"] = z["RegionName"].astype(str).str.zfill(5)
    z = z[z["zip"].isin(TARGET_ZIPS)]
    id_cols = [c for c in ["zip", "StateName", "City", "Metro", "CountyName"] if c in z.columns]
    month_cols = [c for c in z.columns if len(str(c)) >= 7 and str(c)[:4].isdigit()][-24:]
    long = z.melt(id_vars=id_cols, value_vars=month_cols, var_name="month_end", value_name="zhvi")
    long["list_month"] = long["month_end"].map(_month_key)
    long = long.dropna(subset=["zhvi"])
    long["zhvi"] = long["zhvi"].astype(float)
    return long.sort_values(["zip", "list_month"]).reset_index(drop=True)


def freeze_redfin_dallas() -> pd.DataFrame:
    r = pd.read_csv(RAW / "redfin_metro.tsv.gz", sep="\t", compression="gzip", low_memory=False)
    d = r[
        (r["REGION"].astype(str).str.contains("Dallas, TX metro", case=False, na=False))
        & (r["PROPERTY_TYPE"] == "All Residential")
        & (r["PERIOD_DURATION"] == 30)
    ].copy()
    d["PERIOD_BEGIN"] = pd.to_datetime(d["PERIOD_BEGIN"])
    d["list_month"] = d["PERIOD_BEGIN"].dt.strftime("%Y-%m")
    keep = [
        "list_month", "PERIOD_BEGIN", "PERIOD_END", "REGION",
        "MEDIAN_SALE_PRICE", "MEDIAN_LIST_PRICE", "MEDIAN_PPSF", "MEDIAN_LIST_PPSF",
        "INVENTORY", "HOMES_SOLD", "NEW_LISTINGS", "MEDIAN_DOM",
    ]
    keep = [c for c in keep if c in d.columns]
    return d[keep].sort_values("list_month").drop_duplicates("list_month").reset_index(drop=True)


def freeze_zhvi_metro() -> None:
    m = pd.read_csv(RAW / "zhvi_metro.csv", low_memory=False)
    dm = m[m["RegionName"].astype(str).str.contains("Dallas, TX", na=False)].copy()
    if dm.empty:
        return
    id_cols = [c for c in dm.columns if not (len(str(c)) >= 7 and str(c)[:4].isdigit())]
    months = [c for c in dm.columns if len(str(c)) >= 7 and str(c)[:4].isdigit()][-24:]
    long = dm.melt(id_vars=id_cols, value_vars=months, var_name="month_end", value_name="zhvi")
    long["list_month"] = long["month_end"].map(_month_key)
    long.to_csv(OUT_DIR / "dallas_zhvi_metro_frozen.csv", index=False)


def write_sources(zhvi: pd.DataFrame, redfin: pd.DataFrame) -> None:
    text = f"""# Data sources

## Public downloads (free, no login)
1. **Zillow Research — ZHVI ZIP** (All Homes SFR/Condo, mid-tier, smoothed & seasonally adjusted)
   - https://www.zillow.com/research/data/
2. **Redfin Data Center — Metro Market Tracker**
   - https://www.redfin.com/news/data-center/
   - Filter: `Dallas, TX metro area`, `All Residential`, monthly

## Frozen artifacts in this repo (real aggregates only)
- `dallas_zhvi_zip_frozen.csv` — {len(zhvi):,} real ZIP-month ZHVI rows (16 DFW ZIPs)
- `dallas_redfin_metro_frozen.csv` — {len(redfin):,} real Dallas metro monthly metrics
- `dallas_zhvi_metro_frozen.csv` — Dallas metro ZHVI long slice (cross-check)

MetroMorph **does not** invent MLS micro-listings. Agents scan the ZIP-month ZHVI panel
joined with Redfin metro $/sqft and inventory.

## Rebuild
Place US-wide raw files under `data/raw/`, then:
```bash
python data/build_from_public.py
```
"""
    (OUT_DIR / "SOURCES.md").write_text(text)


def main() -> None:
    if not (RAW / "zhvi_zip.csv").exists() or not (RAW / "redfin_metro.tsv.gz").exists():
        raise SystemExit("Missing data/raw downloads (zhvi_zip.csv, redfin_metro.tsv.gz).")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zhvi = freeze_zhvi_zip()
    redfin = freeze_redfin_dallas()
    zhvi.to_csv(OUT_DIR / "dallas_zhvi_zip_frozen.csv", index=False)
    redfin.to_csv(OUT_DIR / "dallas_redfin_metro_frozen.csv", index=False)
    freeze_zhvi_metro()
    write_sources(zhvi, redfin)
    # remove legacy calibrated micro-listings if present
    legacy = OUT_DIR / "frozen_listings.csv"
    if legacy.exists():
        legacy.unlink()
        print(f"Removed legacy {legacy.name}")
    print(f"Wrote ZHVI ZIP rows={len(zhvi)} Redfin months={len(redfin)}")
    print("Real aggregate freeze complete — no synthetic listings.")


if __name__ == "__main__":
    main()
