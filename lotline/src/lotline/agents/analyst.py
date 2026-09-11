"""Analyst Agent — compute the defined 12-month TrendOutput."""

from __future__ import annotations

import pandas as pd

from lotline.models import QueryPlan, TrendOutput
from lotline.tools import compute_trend


def run_analyst(listings: pd.DataFrame, plan: QueryPlan) -> TrendOutput:
    """Deterministic trend math — critical for trustworthy MRs."""
    return compute_trend(listings, plan)
