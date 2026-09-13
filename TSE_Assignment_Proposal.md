# Metamorphic Testing of a Multi-Agent Housing-Trends Application — Design Proposal

**Due:** October 16, 2026
**Team size:** 2
**Framework:** Pydantic AI + local LLM (Ollama)

---

## 1. Mission

Build a **cyclic multi-agent housing-trend app** on a **frozen local dataset**, with a **visual UI**, then **scientifically measure** its behavior using **≥8 metamorphic relations (MRs)** and statistical violation rates.

---

## 2. What We're Building

### Product
A small application that:
- Takes user criteria (price band, beds/BHK, size, ZIP/locality, date window)
- Uses **multiple cooperating agents** to scan listings and analyze trends
- Reports how residential prices moved over the **past 12 months**
- Shows results in a **nice interactive UI**, including a geographic map of the covered ZIPs/localities colored by price tier

### City / market
**Decision: Dallas–Fort Worth, Texas.** Assumption made to unblock work; swapping to an Indian metro (Bengaluru, Mumbai, Delhi-NCR, Hyderabad, Chennai, Pune) later is a data-and-labels change only — same MR families, same statistical protocol, same agent architecture. Adapt criteria to local conventions if swapped (PIN/locality, ₹ lakh/crore, BHK, carpet/built-up sqft).

---

## 3. Multi-Agent Architecture (How It Works)

### How the user's query reaches the system

UI is a **structured criteria form**, not open chat: price min/max, beds/BHK, ZIP/locality (multi-select, or free-text with autocomplete), 12-month window (defaults to trailing 12 months, adjustable). User hits **Run**. That single form submission becomes the seed `QueryPlan` handed straight to Criteria Agent — one request in, one `TrendOutput` (+ trace log) out per run. No multi-turn dialogue in the core flow.

| # | Agent | Responsibility | Backed by |
|---|--------|----------------|-----------|
| 1 | **Criteria Agent** | Normalizes user filters into a structured `QueryPlan`; applies Critic revisions literally (not a from-scratch re-derivation) | Deterministic (form validation/type-coercion) + **LLM only** when the ZIP/locality field is free text and matches >1 known locality (resolves it, and is what sets `ambiguous_locality`) |
| 2 | **Scanner Agent** | Queries the **frozen** listings snapshot using the current plan | Deterministic (pandas) |
| 3 | **Analyst Agent** | Computes 12-month trend stats; picks the estimator (see dependency #2 below) | Deterministic (pandas) |
| 4 | **Critic Agent** | Judges coverage/confidence → **Pass** or **Revise** with a concrete structured delta | Deterministic (threshold check on `confidence_score`, itself a plain formula) |
| 5 | **Report Agent** | Packages the final `TrendOutput`; generates the narrative | LLM (Pydantic AI → Ollama), packaging itself is deterministic |

3 of 5 agents never call the model — matches "keep agents small, prefer deterministic tools for math." Only the two NL-facing edges (parsing free-text criteria, writing the narrative) touch the LLM at all.

### How agents actually pass data to each other

One Python process, synchronous, sequential — no message bus, no async dispatch, no separate agent processes. The orchestrator (Section 6) calls each `agent.run()` in order, passing typed Pydantic objects as arguments/return values: `QueryPlan` → `listings` → `TrendOutput` → `Critique`. The Critic→Criteria loop-back is exactly this: Critic returns a `Critique` object carrying a structured `revision` payload (e.g. `{widen_price_pct: 15}`), and the orchestrator passes that object straight into `criteria_agent.run(user_criteria, revision=critique)`. That typed object *is* the interaction contract — there's no separate agent-to-agent protocol beyond normal function calls.

### Control flow

```text
User
  → Criteria Agent
      → Scanner Agent
          → Analyst Agent
              → Critic Agent
                    ├─ Pass  → Report Agent → UI
                    └─ Revise → back to Criteria Agent
                         loop until Pass or max_iterations (= 3)
```

### Concrete decision rules (what actually drives the loop)

- **Coverage check:** every one of the 12 months must have ≥ `N_min = 10` active listings. Below that, Critic returns `Revise{widen_price_pct: +15}`.
- **Confidence check:** Critic combines coverage completeness with estimator agreement into `confidence_score` (0–1). Pass requires full coverage **and** `confidence_score ≥ 0.85`.
- **Revise payload is structured, not vague** — e.g. `{"widen_price_pct": 15}` or `{"expand_locality_set": true}` — so Criteria Agent applies a literal, loggable delta instead of re-prompting from nothing.

**Worked example (goes in the final report as runtime evidence):**
```text
iter=1  coverage=0.42                      → Revise{widen_price_pct:+15}
iter=2  coverage=0.71, confidence=0.79     → Revise{widen_price_pct:+15}
iter=3  coverage=1.00, confidence=0.88     → Pass
```

### Loop-exhaustion fallback (max_iterations hit, never Pass)

- Report Agent still emits a `TrendOutput` built from the **last** Analyst result — never a blank/error.
- `confidence_flag` on that output is set to `"max_iterations_exhausted"`.
- UI shows a visible low-confidence banner whenever the flag isn't `"pass"`.
- Trace logs the exhaustion explicitly, e.g. `iter=3 coverage=1.00 confidence=0.71 → max_iterations reached, no pass → emitting low-confidence report`.

### Two independent examples of "genuine dependency" (PDF requirement c)

One Critic loop can look like it's doing double duty for both the feedback-loop requirement (a) and the dependency requirement (c). Two smaller, independent examples remove that ambiguity:

1. **Criteria → Scanner.** Criteria Agent sets a structured `ambiguous_locality: bool` flag on the `QueryPlan` when user input matches more than one known locality. Scanner Agent reads that flag and *changes strategy* — broadens to all matching localities and tags rows by which one matched — instead of just consuming whatever rows it's handed.
2. **Scanner → Analyst.** Analyst Agent picks its estimator based on the data Scanner actually returned: if the price-per-sqft coefficient of variation (CV) across a month's matched listings exceeds `0.30`, it switches from a plain **Stratified Median** to a **Hedonic (regression-adjusted)** estimator for that month, and records which one ran in `estimator_used`. Scanner's output composition — not just its data — changed what Analyst does next.

### Why one Scanner Agent, not several

PDF phrasing ("several cooperating agents each scan listings") reads like plural scanners. Our design uses one Scanner Agent inside a 5-role pipeline instead — cooperation here is role-specialization (Criteria/Scanner/Analyst/Critic/Report each doing distinct work and feeding each other), not parallel redundant scanning. State this plainly in the design note so it doesn't read as under-scoped.

---

## 4. Output Contract

Locked before any agent or MR code is written — every MR is a statement about these exact fields.

For each month `m` in the 12-month window:

| Field | Type | Notes |
|---|---|---|
| `median_price[m]` | float | core trend metric |
| `median_price_per_sqft[m]` | float | core trend metric (₹/sqft for the India variant) |
| `active_listing_count[m]` | int | core trend metric |
| `yoy_pct_change[m]` | float | promoted from "optional" — cheap to compute, directly answers "how did prices move" |
| `estimator_used[m]` | `"stratified_median"` \| `"hedonic_adjusted"` | exposes Analyst's per-month algorithm choice — see dependency #2 above |

Run-level (not per-month):

| Field | Type | Notes |
|---|---|---|
| `confidence_score` | float 0–1 | Critic's Pass/Revise input |
| `confidence_flag` | `"pass"` \| `"max_iterations_exhausted"` | terminal state of the loop — always defined, see Section 3 fallback |

Optional: locality/ZIP rankings.

---

## 5. Datasets

**Primary — per-listing:** Kaggle *USA Real Estate Dataset* (`kaggle.com/datasets/ahmedshahriarsakib/usa-real-estate-dataset`, 2.2M listings), filtered to Dallas–Fort Worth ZIPs. Columns kept: `price`, `beds`, `bath`, `house_size` (sqft), `zip`, `prev_sold_date`/`list month`.

**Target ZIP set (10 core Dallas ZIPs, spanning price tiers):** 75201, 75202, 75204, 75205, 75206, 75209, 75214, 75219, 75225, 75230 — downtown/arts district through university/lakewood through the higher-end north Dallas tier. Deliberately mixed tiers so MR5/MR6 (widen/restrict) have real headroom to move.

**Secondary — cross-check only, not part of the Output Contract or any MR assertion:** Zillow Research ZHVI monthly home-value index for the Dallas–Fort Worth–Arlington MSA (`zillow.com/research/data`) — a published trend line to sanity-check our computed medians against in the UI, kept strictly out of the MR harness so it can't quietly become an oracle.

**Geo layer (for the map UI):** a small hand-built JSON of the 10 ZIPs' centroid coordinates (public ZCTA/USPS centroid data) — supports the interactive map, not used by any agent or MR.

### Freeze procedure
1. Download the Kaggle set once; filter to the 10 ZIPs above.
2. Keep only the columns listed; drop anything else.
3. Save as `data/frozen_listings.csv`, committed to the repo.
4. Check coverage across all 12 months before freezing — no month should be empty.
5. Cite source + exact filter rule in the design note and final report.

### Hard rules
- **No live-only results.** Instructor must re-run offline from our snapshot. Live sites that change score zero on rigor.
- **Public/exported/synthetic data only.** No personal data or paid credentials into listing sites.

---

## 6. Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Agent framework | **Pydantic AI** | Typed/structured outputs; strong for MR checks; allowed in PDF |
| Local LLM | **Ollama** + small model (Llama / Qwen / Mistral) | Free, local, recommended by PDF |
| Filtering & stats | Deterministic **Python / pandas** tools | Reliable numbers for MRs |
| UI | Streamlit (or FastAPI + simple frontend) | Fast to ship, interactive |
| Data | `data/frozen_listings.csv` committed in repo | Reproducibility |

### Orchestration sketch

```text
plan = criteria_agent.run(user_criteria)
while iteration < max_iter:
    listings = scanner_agent.run(plan)
    trend = analyst_agent.run(listings)
    critique = critic_agent.run(plan, listings, trend)
    if critique.status == "pass":
        break
    plan = criteria_agent.run(user_criteria, revision=critique)  # feedback + dependency
report = report_agent.run(trend)
```

Draw this as a **graph with the cycle marked** in the design note.

**Performance note:** run the metamorphic harness with LLM narrative generation switched off — evaluate the numeric `TrendOutput` fields purely in-process — and only turn narrative generation on for interactive UI calls. Hundreds of harness runs going through a live LLM call each time is a needless bottleneck.

---

## 7. Metamorphic Testing Plan

```text
base_input → run(system) → output_A
transform(base_input or data) → run(system) → output_B
assert relation(output_A, output_B, tolerance)
```

### Three required families (keep all three; ≥8 MRs total)

Carrying **11 candidates** (4 invariance, 4 monotonic, 3 directional), not exactly 8: PDF explicitly allows an MR to turn out ill-conceived and get **dropped**, not just refined. If that happens to one of MR1–8, promote MR9/10/11 rather than inventing a replacement mid-harness. Final report only needs ≥8 surviving, all 3 families present.

#### A. Invariance

| MR | Transformation | Expected relation | Practical assert |
|----|----------------|--------------------|-------------------|
| MR1 | Reorder / relabel listings | Trend + summary stats unchanged | `A == B` for all trend stats |
| MR2 | Change currency/units display (USD↔thousands, ₹ crore↔lakh, sqft↔same) | Percentages & rankings identical | rankings equal; only display scale differs |
| MR3 | Duplicate every listing (2× dataset) | Medians / $/sqft unchanged; active count doubles | medians equal; `count_B ≈ 2 × count_A` |
| MR9 *(buffer)* | Duplicate every listing (2×), track unique-seller/listing-id count | Unique-seller count **unchanged** — contrasts with MR3's count doubling; validates the metric distinguishes duplicate inflation from real growth (the exact "ill-conceived MR" trap PDF calls out for duplicates vs. a "unique sellers" metric) | `unique_sellers_B == unique_sellers_A` |

#### B. Monotonic

| MR | Transformation | Expected relation | Practical assert |
|----|----------------|--------------------|-------------------|
| MR4 | Add $X (or ₹X) to every list price in one month | That month's median rises ≈ X; no month decreases | `median_B[t] ≈ median_A[t] + X`; no month decreases |
| MR5 | Widen price-band criterion (superset) | Active-count series ≥ original, month by month | `count_B[m] >= count_A[m]` for every month |
| MR6 | Restrict to sub-region (subset of ZIPs/localities) | Each monthly count ≤ all-region count | `count_sub[m] <= count_full[m]` for every month |
| MR11 *(buffer)* | Tighten bed/BHK minimum (stricter subset, e.g. 3+ BHK only) | Monthly active count ≤ original series (same pattern as MR6, different dimension) | `count_B[m] <= count_A[m]` for every month |

**Truncation caveat (applies to MR4, MR8, MR10):** if the base criteria carries a fixed upper price cap, an additive/multiplicative price transform can push listings that were just under the cap over it — they get filtered out, and the median can legitimately *drop*, which reads as a false violation. Define these MRs' input subdomain to exclude base queries with an upper price cap close to the transformation delta, or state the exclusion explicitly as part of the MR's documented subdomain.

#### C. Directional

| MR | Transformation | Expected relation | Practical assert |
|----|----------------|--------------------|-------------------|
| MR7 | Shift 12-month window forward by 1 month | 11 overlapping months' stats match | 11 overlapping months match within tolerance |
| MR8 | Scale all prices by factor k > 1 | Median $/sqft scales ≈ k; % trend shape invariant | `median_B ≈ k × median_A`; %-change shape ≈ same |
| MR10 *(buffer)* | Apply scale factor k only to the most recent 3 months (localized/partial scaling) | Only touched months scale by k; untouched months stay within tolerance of original — tests localized directional response, distinct from MR8's global scaling | `median_B[m] ≈ k × median_A[m]` only for touched months; else `median_B[m] ≈ median_A[m]` |

### Evaluation protocol

Per MR we report: number of distinct base inputs (**≥ 30**), seed list (if non-deterministic; **k ≥ 3** seeds each), violation count, violation rate, and 95% CI.

```text
violation_rate = (number of failing base inputs) / (total base inputs)
```

A base input = one criteria set / data slice (different price bands, BHK filters, ZIP/locality sets, end-months). Store them in `tests/base_inputs.json` with a fixed generator seed.

**Non-determinism policy:** prefer temperature 0 / deterministic tools, but **temp 0 on Ollama is not a determinism guarantee** — local backends (quantization, threading, batching) can still vary run-to-run even at temp 0. Treat every LLM-touched agent as non-deterministic by default and apply the k≥3-seed protocol unconditionally to any MR that passes through an LLM step. Document the fail rule clearly (e.g., fail if any seed-pair violates, or fail on majority) and stick to it.

**Confidence interval method:** violation rate is a proportion over a small sample (~30 base inputs), and counts can sit near 0 or the total, where a normal-approximation CI breaks down. Use the **Wilson score interval** for all reported 95% CIs, and say so explicitly in the report's methodology section.

**Harness implementation note:** when comparing two monthly series (source run vs. follow-up run), join by calendar-month key (`{m.month: value}`), never by positional order (`zip(series_a, series_b)`). A follow-up run that legitimately produces fewer than 12 months (e.g. from strict filtering) will silently misalign a positional comparison; missing months should compare as explicit 0, not be dropped.

### Diagnosing top-3 violated MRs

Classify each with evidence:
1. **Genuine agent/aggregation fault**
2. **Data artifact** (bad listings, missing months)
3. **Ill-conceived MR** (property does not actually hold for our metric — an MR is a hypothesis, not an axiom; refining it with clear reasoning is graded positively)
4. **Harness bug** (bad transform/tolerance)

**"Enough" tests:** ≥30 is the minimum floor; conclude "enough" once the CI is tight enough to support the conclusion.

---

## 8. Deliverables

- Design note: architecture + data source + 8 MR sketches, submitted within the first ~10 days
- Working application on the frozen snapshot + visual UI (trend chart, monthly-counts table, map), fully offline
- Agent graph with real feedback, iterate/stop, and dependency — with runtime evidence (the worked example in Section 3)
- MR catalog with justifications; ≥8 MRs across all 3 families
- Metamorphic harness executed; violation rates + 95% Wilson CIs, each MR on ≥30 base inputs
- Top-3 violations diagnosed
- Final report (10–12 pages): system & data source, MR catalog, results (rates + CIs), root-cause analysis of top-3 violations, threats to validity, reflection (~½ page on what an LLM could/couldn't have produced without running the system)
- Git repo with: code, frozen data snapshot, `NOTEBOOK.md`, `AI_USE.md` (including cases where an AI tool was wrong and how it was caught), one-command reproduction of the headline results table

---

**End of proposal**
