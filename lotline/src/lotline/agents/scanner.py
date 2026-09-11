"""Scanner Agent — retrieve listings for the current QueryPlan."""

from __future__ import annotations

import pandas as pd

from lotline.models import QueryPlan
from lotline.tools import filter_listings


def run_scanner(df: pd.DataFrame, plan: QueryPlan) -> pd.DataFrame:
    """Deterministic tool call — LLM does not invent listings."""
    return filter_listings(df, plan)
