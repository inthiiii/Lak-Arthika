"""Public contracts for the experimental economic-pressure warning engine."""

from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field

StressSeverity = Literal["normal", "watch", "warning", "critical"]
AlertStatus = Literal["active", "resolved"]


class StressComponents(BaseModel):
    """Auditable component scores, each normalized to the 0–100 range."""

    anomaly: float = Field(ge=0, le=100)
    momentum: float = Field(ge=0, le=100)
    forecast_surprise: float = Field(ge=0, le=100)
    spatial_pressure: float = Field(ge=0, le=100)


class StressSignal(BaseModel):
    """One market/commodity pressure assessment at an observation date."""

    market_id: str
    market_name: str
    district: str
    province: str
    latitude: float
    longitude: float
    commodity: str
    observation_date: date
    price_midpoint_lkr: float = Field(gt=0)
    score: float = Field(ge=0, le=100)
    severity: StressSeverity
    confidence: float = Field(ge=0, le=1)
    components: StressComponents
    evidence_observations: int = Field(ge=1)
    stale: bool = False
    methodology_version: str = "economic-stress-v1"


class EconomicAlert(BaseModel):
    """Deduplicated alert lifecycle derived from persistent stress signals."""

    alert_id: str
    market_id: str
    market_name: str
    commodity: str
    status: AlertStatus
    severity: StressSeverity
    opened_at: date
    last_observed_at: date
    resolved_at: date | None = None
    peak_score: float = Field(ge=0, le=100)
    latest_score: float = Field(ge=0, le=100)
    observation_count: int = Field(ge=1)
    summary: str


class StressMethodology(BaseModel):
    """Machine-readable documentation of scoring and alert policy."""

    version: str = "economic-stress-v1"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    purpose: str
    event_definition: str
    component_weights: dict[str, float]
    severity_thresholds: dict[str, float]
    alert_policy: dict[str, int | float | str]
    limitations: list[str]


class StressBacktestReport(BaseModel):
    """Out-of-time event detection quality for the warning score."""

    methodology_version: str
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    train_end: date
    calibration_end: date
    test_start: date
    test_end: date
    selected_threshold: float
    samples: int
    positive_events: int
    precision: float
    recall: float
    f1: float
    pr_auc: float
    false_alert_rate: float
    median_lead_days: float | None
