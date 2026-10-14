"""Contracts shared by source-document parsers."""

from typing import Protocol

from lak_arthika.ingestion.harti import DownloadedBulletin
from lak_arthika.models.price import PriceRecord


class BulletinParser(Protocol):
    """A versioned parser that emits the canonical price schema."""

    version: str

    def supports(self, bulletin: DownloadedBulletin) -> bool:
        """Return whether this parser supports the source document."""

    def parse(self, bulletin: DownloadedBulletin) -> list[PriceRecord]:
        """Extract normalized records from the source document."""
