"""Reference models for Sri Lankan commodity markets."""

from datetime import date

from pydantic import BaseModel, Field


class MarketReference(BaseModel):
    """A geocoded market used by price and map APIs."""

    market_id: str = Field(min_length=1)
    market_name: str = Field(min_length=1)
    district: str = Field(min_length=1)
    province: str = Field(min_length=1)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    market_type: str = Field(min_length=1)


class MarketPricePoint(BaseModel):
    """The most recent price for one geocoded market at a requested date."""

    market_id: str = Field(min_length=1)
    market_name: str = Field(min_length=1)
    district: str = Field(min_length=1)
    province: str = Field(min_length=1)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    commodity: str = Field(min_length=1)
    category: str = Field(min_length=1)
    minimum_price_lkr: float = Field(gt=0)
    maximum_price_lkr: float = Field(gt=0)
    midpoint_price_lkr: float = Field(gt=0)
    previous_price_lkr: float | None = Field(default=None, gt=0)
    change_percentage: float | None = None
    observation_date: date
    source_url: str = Field(min_length=1)


class CatalogResponse(BaseModel):
    """Filter options and temporal coverage available to dashboard clients."""

    commodities: list[str]
    markets: list[MarketReference]
    minimum_date: date | None
    maximum_date: date | None
