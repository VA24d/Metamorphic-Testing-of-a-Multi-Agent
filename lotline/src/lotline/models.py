"""Shared typed contracts for agents, UI, and metamorphic tests."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CritiqueStatus(str, Enum):
    PASS = "pass"
    REVISE = "revise"


class UserCriteria(BaseModel):
    """Raw filters coming from the UI."""

    price_min: float = 150_000
    price_max: float = 650_000
    beds_min: int = 2
    beds_max: int = 5
    sqft_min: float = 800
    sqft_max: float = 4_000
    zips: list[str] = Field(default_factory=list)
    window_end: str = "2025-08"  # YYYY-MM, inclusive end of 12-month window
    currency_display: str = "USD"  # USD | USD_THOUSANDS
    area_unit: str = "sqft"


class QueryPlan(BaseModel):
    """Normalized plan produced / revised by the Criteria Agent."""

    price_min: float
    price_max: float
    beds_min: int
    beds_max: int
    sqft_min: float
    sqft_max: float
    zips: list[str] = Field(default_factory=list)
    window_start: str
    window_end: str
    currency_display: str = "USD"
    area_unit: str = "sqft"
    notes: list[str] = Field(default_factory=list)
    revision_round: int = 0


class MonthlyStat(BaseModel):
    month: str
    median_price: float
    median_price_per_sqft: float
    active_count: int


class TrendOutput(BaseModel):
    """Exact 12-month trend contract — every MR talks about these fields."""

    months: list[MonthlyStat]
    yoy_pct_change: float | None = None
    total_listings: int = 0
    coverage_score: float = 0.0
    empty_months: list[str] = Field(default_factory=list)


class CritiqueAction(BaseModel):
    action: str
    value: Any = None
    reason: str = ""


class Critique(BaseModel):
    status: CritiqueStatus
    coverage_score: float
    confidence: float
    actions: list[CritiqueAction] = Field(default_factory=list)
    summary: str = ""


class AgentReport(BaseModel):
    headline: str
    narrative: str
    trend: TrendOutput
    query_plan: QueryPlan
    iterations: int
    mode: str  # "mock" | "ollama"
    trace: list[str] = Field(default_factory=list)


class AgentStepResult(BaseModel):
    """One visible agent output for the UI."""

    agent: str  # Criteria | Scanner | Analyst | Critic | Report
    iteration: int
    status: str = "ok"  # ok | revise | pass
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)


class PipelineResult(BaseModel):
    report: AgentReport
    listings_preview: list[dict[str, Any]] = Field(default_factory=list)
    filtered_count: int = 0
    agent_steps: list[AgentStepResult] = Field(default_factory=list)
