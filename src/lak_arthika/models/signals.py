"""Contracts for point-in-time external economic and weather signals."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ExternalSignal(BaseModel):
    """One provenance-backed signal value with an explicit availability boundary."""

    signal_name: str
    geography_id: str
    effective_date: date
    available_date: date
    value: float
    unit: str
    source: Literal["nasa_power", "cbsl", "ceypetco", "calendar"]
    source_url: str
    retrieved_at: datetime
    content_sha256: str
    vintage: str


class SignalFreshness(BaseModel):
    """Freshness state for one source family."""

    source: str
    latest_effective_date: date | None
    observation_count: int
    age_days: int | None
    stale: bool


class ModelHealth(BaseModel):
    """Operational and statistical health for the promoted forecast model."""

    status: Literal["healthy", "warning", "blocked"]
    model_version: str | None
    checked_at: datetime
    training_cutoff: date | None
    training_data_age_days: int | None
    strongest_baseline_wins: list[int]
    undercovered_horizons: list[int]
    signals: list[SignalFreshness]
    messages: list[str]


class PromotionDecision(BaseModel):
    """Auditable champion/challenger decision."""

    candidate_version: str
    evaluated_at: datetime
    promoted: bool
    forced: bool = False
    required_horizons: list[int]
    horizons_beating_strongest_baseline: list[int]
    reasons: list[str]
    strongest_baseline: str = Field(default="minimum MAE across registered baselines")
