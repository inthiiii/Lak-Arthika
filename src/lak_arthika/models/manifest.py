"""Models describing the lifecycle of source bulletins."""

from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field

BulletinStatus = Literal[
    "discovered",
    "downloaded",
    "processed",
    "quarantined",
    "failed",
]


class BulletinManifestRecord(BaseModel):
    """Durable state for one official HARTI bulletin URL."""

    bulletin_date: date
    language: str = "English"
    source_url: str = Field(min_length=1)
    status: BulletinStatus = "discovered"
    sha256: str | None = None
    local_pdf_path: str | None = None
    parser_version: str | None = None
    record_count: int = Field(default=0, ge=0)
    validation_status: Literal["pending", "passed", "failed"] = "pending"
    error_message: str | None = None
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def identity(self) -> tuple[date, str]:
        """Return the stable identity used by manifest upserts."""

        return self.bulletin_date, self.source_url
