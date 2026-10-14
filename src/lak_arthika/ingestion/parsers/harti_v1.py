"""Parser for the current English HARTI daily bulletin layout."""

from lak_arthika.ingestion.harti import (
    DownloadedBulletin,
    extract_wholesale_vegetable_prices,
)
from lak_arthika.models.price import PriceRecord


class HartiV1Parser:
    """Extract wholesale vegetable tables used in current HARTI PDFs."""

    version = "harti-v1"

    def supports(self, bulletin: DownloadedBulletin) -> bool:
        """Select PDFs; structural validation happens during parsing."""

        return bulletin.pdf_path.suffix.lower() == ".pdf"

    def parse(self, bulletin: DownloadedBulletin) -> list[PriceRecord]:
        """Parse a current-layout HARTI bulletin."""

        return extract_wholesale_vegetable_prices(bulletin)
