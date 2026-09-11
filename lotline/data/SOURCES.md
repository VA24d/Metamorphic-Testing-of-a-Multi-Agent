# Data sources

## Public downloads (free, no login)
1. **Zillow Research — ZHVI ZIP** (All Homes SFR/Condo, mid-tier, smoothed & seasonally adjusted)
   - https://www.zillow.com/research/data/
2. **Redfin Data Center — Metro Market Tracker**
   - https://www.redfin.com/news/data-center/
   - Filter: `Dallas, TX metro area`, `All Residential`, monthly

## Frozen artifacts in this repo (real aggregates only)
- `dallas_zhvi_zip_frozen.csv` — 384 real ZIP-month ZHVI rows (16 DFW ZIPs)
- `dallas_redfin_metro_frozen.csv` — 173 real Dallas metro monthly metrics
- `dallas_zhvi_metro_frozen.csv` — Dallas metro ZHVI long slice (cross-check)

MetroMorph **does not** invent MLS micro-listings. Agents scan the ZIP-month ZHVI panel
joined with Redfin metro $/sqft and inventory.

## Rebuild
Place US-wide raw files under `data/raw/`, then:
```bash
python data/build_from_public.py
```
