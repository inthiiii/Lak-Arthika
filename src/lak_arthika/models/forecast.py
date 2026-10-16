"""Public forecasting contracts."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ForecastRecord(BaseModel):
    """One direct-horizon experimental wholesale-price forecast."""

    market_id: str
    market_name: str
    commodity: str
    category: str
    generated_at: datetime
    origin_date: date
    training_cutoff: date
    forecast_date: date
    horizon_days: Literal[7, 14, 30]
    point_forecast_lkr: float = Field(ge=0)
    lower_80_lkr: float = Field(ge=0)
    upper_80_lkr: float = Field(ge=0)
    lower_95_lkr: float = Field(ge=0)
    upper_95_lkr: float = Field(ge=0)
    model_version: str
    feature_version: str
    model_type: str
    experimental: Literal[True] = True

    @model_validator(mode="after")
    def intervals_are_ordered(self) -> "ForecastRecord":
        """Reject malformed uncertainty intervals."""

        if not (
            self.lower_95_lkr
            <= self.lower_80_lkr
            <= self.point_forecast_lkr
            <= self.upper_80_lkr
            <= self.upper_95_lkr
        ):
            raise ValueError("Forecast intervals must contain the point forecast")
        return self


class HorizonQuality(BaseModel):
    """Out-of-time quality measurements for one forecast horizon."""

    horizon_days: Literal[7, 14, 30]
    samples: int
    folds: int
    model_metrics: dict[str, float | None]
    baseline_metrics: dict[str, dict[str, float | None]]
    interval_coverage_80: float
    interval_coverage_95: float
    interval_radius_80_lkr: float
    interval_radius_95_lkr: float
    beats_seasonal_baseline: bool


class ForecastQuality(BaseModel):
    """Evaluation report served with a model version."""

    model_version: str
    evaluated_at: datetime
    horizons: list[HorizonQuality]


class ModelMetadata(BaseModel):
    """Traceable metadata for the currently promoted model."""

    model_version: str
    trained_at: datetime
    training_start: date
    training_end: date
    training_cutoff: date
    observations: int
    series: int
    horizons: list[Literal[7, 14, 30]]
    feature_version: str
    estimator: str
    intended_use: str
    limitations: list[str]
