# Design note (draft) — MetroMorph multi-agent architecture

## Output contract
For each of 12 months ending at `window_end`:
- `median_price` — median Zillow ZHVI across selected DFW ZIPs
- `median_price_per_sqft` — Redfin Dallas metro median $/sqft
- `active_count` — count of ZIP-month observations contributing that month
Plus `yoy_pct_change`, `coverage_score`, `total_listings`.

## Agent graph (cycle marked)

```text
                 ┌────────────────────────────────────────┐
                 │            FEEDBACK CYCLE ★            │
                 ▼                                        │
           Criteria Agent                                 │
                 │                                        │
                 ▼                                        │
           Scanner Agent  (ZHVI ZIP panel + Redfin join)  │
                 │                                        │
                 ▼                                        │
           Analyst Agent  (monthly ZHVI / $/sqft / counts)│
                 │                                        │
                 ▼                                        │
           Critic Agent ──── Pass ──► Report Agent ──► UI │
                 │                                        │
                 └──── Revise (actions) ──────────────────┘
```

### Why the loop is necessary
Thin ZIP/price slices leave months with too few ZIP observations. The Critic measures coverage and **changes the next QueryPlan** (widen price_max, expand ZIPs). That is a genuine dependency, not a decorative retry.

## Data (public Zillow + Redfin only)
Free downloads (no login):
1. **Zillow Research ZHVI** (ZIP + metro) — https://www.zillow.com/research/data/
2. **Redfin Data Center** metro tracker — https://www.redfin.com/news/data-center/

Frozen in-repo (real aggregates, no synthetic micro-listings):
- `data/dallas_zhvi_zip_frozen.csv`
- `data/dallas_redfin_metro_frozen.csv`
- `data/dallas_zhvi_metro_frozen.csv`
- See `data/SOURCES.md`

Agents scan **ZIP-month ZHVI rows** joined with Redfin metro $/sqft & inventory. Beds/sqft filters are not available in these public feeds (documented assumption).

## Eight MR sketches
1. Reorder invariance  
2. Currency display invariance  
3. Duplicate observations (counts ×2)  
4. Add +X to one month ZHVI (monotonic)  
5. Widen price band (counts ≥)  
6. Sub-region ZIPs (counts ≤)  
7. Shift window +1 (11-month overlap)  
8. Scale prices by k (medians ×k, YoY shape)

See `harness/mrs.py` and `harness/run_harness.py`.
