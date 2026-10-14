"""Data-quality response models."""

from pydantic import BaseModel, Field


class QualityStatus(BaseModel):
    """Aggregated ingestion health exposed by the API."""

    total_bulletins: int = Field(ge=0)
    processed_bulletins: int = Field(ge=0)
    quarantined_bulletins: int = Field(ge=0)
    failed_bulletins: int = Field(ge=0)
    pending_bulletins: int = Field(ge=0)
    latest_error: str | None = None
