"""Parser selection for evolving bulletin layouts."""

from lak_arthika.ingestion.harti import DownloadedBulletin
from lak_arthika.ingestion.parsers.base import BulletinParser
from lak_arthika.ingestion.parsers.harti_v1 import HartiV1Parser

PARSERS: tuple[BulletinParser, ...] = (HartiV1Parser(),)


def select_parser(bulletin: DownloadedBulletin) -> BulletinParser:
    """Return the first compatible parser or fail with an actionable error."""

    for parser in PARSERS:
        if parser.supports(bulletin):
            return parser

    raise ValueError(f"No registered parser supports {bulletin.pdf_path}")
