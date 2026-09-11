#!/usr/bin/env python3
"""Run metamorphic relations and print violation rates + 95% Wilson CIs.

Usage (from lotline/):
  # All 8 MRs (assignment table)
  PYTHONPATH=src python harness/run_harness.py --n 30 --seed 7

  # One MR only
  PYTHONPATH=src python harness/run_harness.py --mr MR3_duplicate --n 30 --seed 7

  # List MR ids
  PYTHONPATH=src python harness/run_harness.py --list
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from lotline.models import UserCriteria  # noqa: E402
from lotline.tools import DFW_ZIPS, load_listings  # noqa: E402
from harness.mrs import MR_FUNCS, agent_loop_smoke  # noqa: E402


def wilson_ci(successes: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    z = norm.ppf(1 - alpha / 2)
    p = successes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = (z / denom) * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return (max(0.0, center - half), min(1.0, center + half))


def make_base_inputs(n: int, rng: np.random.Generator) -> list[UserCriteria]:
    ends = [f"2025-{m:02d}" for m in range(8, 13)] + [f"2026-{m:02d}" for m in range(1, 6)]
    inputs: list[UserCriteria] = []
    for i in range(n):
        lo = float(rng.integers(250, 450) * 1000)
        hi = float(lo + rng.integers(200, 600) * 1000)
        b0 = int(rng.integers(1, 4))
        b1 = int(rng.integers(b0, 6))
        zcount = int(rng.integers(4, len(DFW_ZIPS) + 1))
        zips = list(rng.choice(DFW_ZIPS, size=zcount, replace=False))
        inputs.append(
            UserCriteria(
                price_min=lo,
                price_max=hi,
                beds_min=b0,
                beds_max=b1,
                sqft_min=float(rng.integers(700, 1200)),
                sqft_max=float(rng.integers(2500, 4500)),
                zips=zips,
                window_end=str(rng.choice(ends)),
                currency_display="USD",
            )
        )
    return inputs


def resolve_mrs(selection: list[str] | None) -> dict:
    """Return MR_FUNCS subset. selection=None means all.

    Accepts full ids (MR3_duplicate) or short prefixes (MR3).
    """
    if not selection:
        return dict(MR_FUNCS)
    out: dict = {}
    unknown: list[str] = []
    for raw in selection:
        key = raw.strip()
        upper = key.upper()
        match = None
        if key in MR_FUNCS:
            match = key
        else:
            candidates = [mid for mid in MR_FUNCS if mid.upper() == upper or mid.upper().startswith(upper + "_")]
            if len(candidates) == 1:
                match = candidates[0]
            elif len(candidates) > 1:
                raise ValueError(f"Ambiguous MR '{key}'; matches {candidates}. Use a full id.")
        if match is None:
            unknown.append(key)
        else:
            out[match] = MR_FUNCS[match]
    if unknown:
        known = ", ".join(MR_FUNCS)
        raise ValueError(f"Unknown MR id(s): {unknown}. Known: {known}")
    return out


def run_one_mr(
    mr_id: str,
    fn,
    df,
    bases: list[UserCriteria],
    seed: int,
    *,
    agent_trace_cases: int = 3,
) -> dict:
    """Run MR checkers; optionally attach mock agent traces for the first N cases.

    Pass/fail stays on deterministic trend metrics. Agent traces are for UI linkage only.
    """
    from harness.mrs import MR_CATALOG_BY_ID, capture_agent_trace

    meta = MR_CATALOG_BY_ID.get(mr_id, {})
    agents = list(meta.get("agents") or [])
    agent_rationale = str(meta.get("agent_rationale") or "")

    violations = 0
    details = []
    per_case = []
    for i, criteria in enumerate(bases):
        r = np.random.default_rng(seed + hash(mr_id) % 10_000)
        result = fn(df, criteria, r)
        metrics = dict(result.metrics or {})
        metrics["agents"] = agents
        metrics["agent_rationale"] = agent_rationale
        if i < max(0, agent_trace_cases):
            metrics["agent_pipeline"] = capture_agent_trace(df, criteria)
        case = {
            "case": i,
            "passed": result.passed,
            "detail": result.detail,
            "criteria": {
                "price_min": criteria.price_min,
                "price_max": criteria.price_max,
                "zips": criteria.zips,
                "window_end": criteria.window_end,
                "beds_min": criteria.beds_min,
                "beds_max": criteria.beds_max,
            },
            "metrics": metrics,
        }
        per_case.append(case)
        if not result.passed:
            violations += 1
            details.append(f"case {i}: {result.detail}")
    n = len(bases)
    rate = violations / n if n else 0.0
    lo, hi = wilson_ci(violations, n)
    return {
        "mr_id": mr_id,
        "n": n,
        "violations": violations,
        "violation_rate": rate,
        "ci95": [lo, hi],
        "seed": seed,
        "agents": agents,
        "agent_rationale": agent_rationale,
        "sample_failures": details[:5],
        "cases": per_case,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MetroMorph MR harness — run all MRs or one at a time",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  PYTHONPATH=src python harness/run_harness.py --list\n"
            "  PYTHONPATH=src python harness/run_harness.py --n 30 --seed 7\n"
            "  PYTHONPATH=src python harness/run_harness.py --mr MR1_reorder --n 30\n"
            "  PYTHONPATH=src python harness/run_harness.py --mr MR3 --mr MR5 --n 15\n"
        ),
    )
    parser.add_argument("--n", type=int, default=30, help="Base inputs per MR")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--mr",
        action="append",
        dest="mrs",
        metavar="ID",
        help="Run only this MR (repeatable). Accepts MR3 or MR3_duplicate. Default: all.",
    )
    parser.add_argument("--list", action="store_true", help="Print available MR ids and exit")
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="JSON output path (default: results_table.json or results_<mr>.json for single)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print pass/fail for every base input (useful for individual MR debugging)",
    )
    parser.add_argument("--no-smoke", action="store_true", help="Skip agent-loop smoke check")
    parser.add_argument(
        "--agent-trace-cases",
        type=int,
        default=1,
        help="Attach mock agent pipeline traces for the first N cases (0=off)",
    )
    args = parser.parse_args()

    if args.list:
        print("Available metamorphic relations:")
        for mid in MR_FUNCS:
            print(f"  {mid}")
        return

    try:
        selected = resolve_mrs(args.mrs)
    except ValueError as e:
        raise SystemExit(str(e)) from e
    rng = np.random.default_rng(args.seed)
    df = load_listings()
    bases = make_base_inputs(args.n, rng)

    smoke = None
    if not args.no_smoke:
        smoke = agent_loop_smoke(df, bases[0])
        print("SMOKE:", smoke.passed, smoke.detail)

    scope = "all MRs" if not args.mrs else ", ".join(selected)
    print(f"\nRunning: {scope}  (n={args.n}, seed={args.seed})")
    print("\nMR_ID                      n  viol  rate     95% CI")
    print("-" * 64)

    rows = []
    for mr_id, fn in selected.items():
        row = run_one_mr(
            mr_id,
            fn,
            df,
            bases,
            args.seed,
            agent_trace_cases=args.agent_trace_cases,
        )
        rows.append(row)
        print(
            f"{mr_id:24s}  {row['n']:3d}  {row['violations']:4d}  "
            f"{row['violation_rate']:6.3f}  [{row['ci95'][0]:.3f}, {row['ci95'][1]:.3f}]"
        )
        if args.verbose:
            for case in row["cases"]:
                mark = "PASS" if case["passed"] else "FAIL"
                print(f"    [{mark}] case {case['case']:02d}: {case['detail']}")
            if row["sample_failures"]:
                print(f"    failures: {row['sample_failures']}")

    if args.out:
        out_name = args.out
    elif args.mrs and len(selected) == 1:
        only = next(iter(selected))
        out_name = f"harness/results_{only}.json"
    else:
        out_name = "harness/results_table.json"

    out = ROOT / out_name
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "seed": args.seed,
        "n_base_inputs": args.n,
        "selected_mrs": list(selected),
        "smoke": smoke.__dict__ if smoke else None,
        "results": [{k: v for k, v in r.items() if k != "cases" or args.verbose} for r in rows],
    }
    # always keep cases in JSON for individual runs; trim for full suite unless verbose
    if args.mrs or args.verbose:
        payload["results"] = rows
    else:
        payload["results"] = [{k: v for k, v in r.items() if k != "cases"} for r in rows]

    out.write_text(json.dumps(payload, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
