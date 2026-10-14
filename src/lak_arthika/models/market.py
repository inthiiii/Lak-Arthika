"""Reference models for Sri Lankan commodity markets."""

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
