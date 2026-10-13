"""Validated price-domain models."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class PriceRecord(BaseModel):
    """One validated commodity-price observation."""

    source_name: Literal["HARTI"] = "HARTI"
    bulletin_date: date
    observation_date: date

    category: str = Field(min_length=1)
    commodity: str = Field(min_length=1)
    market: str = Field(min_length=1)

    currency: Literal["LKR"] = "LKR"
    unit: Literal["kg"] = "kg"

    price_min_lkr: float = Field(gt=0, le=100_000)
    price_max_lkr: float = Field(gt=0, le=100_000)
    price_midpoint_lkr: float = Field(gt=0, le=100_000)

    source_url: str = Field(min_length=1)
    source_sha256: str = Field(min_length=64, max_length=64)
    ingested_at: datetime

    @model_validator(mode="after")
    def validate_price_range(self) -> "PriceRecord":
        """Ensure that the price range and midpoint are internally consistent."""

        if self.price_min_lkr > self.price_max_lkr:
            raise ValueError("Minimum price cannot exceed maximum price.")

        expected_midpoint = (self.price_min_lkr + self.price_max_lkr) / 2

        if abs(self.price_midpoint_lkr - expected_midpoint) > 0.01:
            raise ValueError("Price midpoint does not match the price range.")

        return self
