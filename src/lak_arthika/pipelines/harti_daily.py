"""End-to-end pipeline for the latest HARTI daily bulletin."""

import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from lak_arthika.ingestion.harti import (
    BulletinLink,
    DownloadedBulletin,
    discover_latest_bulletin,
    download_bulletin,
    preserve_local_bulletin,
)
from lak_arthika.ingestion.parsers import select_parser
from lak_arthika.models.price import PriceRecord
from lak_arthika.quality import assess_price_records
from lak_arthika.storage.prices import upsert_price_records


def validate_extracted_records(
    records: Sequence[PriceRecord],
) -> dict[str, object]:
    """Run publication-blocking validation checks."""

    return assess_price_records(records)


def run_harti_daily_sync(
    *,
    raw_root: Path,
    parquet_path: Path,
    validation_report_path: Path,
) -> dict[str, object]:
    """Discover, preserve, extract, validate and store one bulletin."""

    bulletin_link = discover_latest_bulletin()

    downloaded = download_bulletin(
        bulletin_link,
        raw_root=raw_root,
    )

    return process_downloaded_bulletin(
        downloaded,
        parquet_path=parquet_path,
        validation_report_path=validation_report_path,
    )


def run_harti_file_sync(
    *,
    source_path: Path,
    bulletin_date: date,
    source_url: str,
    raw_root: Path,
    parquet_path: Path,
    validation_report_path: Path,
) -> dict[str, object]:
    """Process an official HARTI PDF that was downloaded manually."""

    downloaded = preserve_local_bulletin(
        BulletinLink(bulletin_date=bulletin_date, url=source_url),
        source_path=source_path,
        raw_root=raw_root,
    )

    return process_downloaded_bulletin(
        downloaded,
        parquet_path=parquet_path,
        validation_report_path=validation_report_path,
    )


def process_downloaded_bulletin(
    downloaded: DownloadedBulletin,
    *,
    parquet_path: Path,
    validation_report_path: Path,
) -> dict[str, object]:
    """Extract, validate and store one preserved HARTI bulletin."""

    parser = select_parser(downloaded)
    records = parser.parse(downloaded)
    validation_report = validate_extracted_records(records)

    validation_report.update(
        {
            "bulletin_date": downloaded.bulletin_date.isoformat(),
            "source_url": downloaded.source_url,
            "source_sha256": downloaded.sha256,
            "raw_pdf_path": str(downloaded.pdf_path),
            "parser_version": parser.version,
        }
    )

    validation_report_path.parent.mkdir(parents=True, exist_ok=True)
    validation_report_path.write_text(
        json.dumps(validation_report, indent=2),
        encoding="utf-8",
    )

    if validation_report.get("valid") is not True:
        raise ValueError(f"HARTI extraction failed validation. See {validation_report_path}.")

    total_stored_records = upsert_price_records(
        records,
        destination=parquet_path,
    )

    return {
        "status": "success",
        "bulletin_date": downloaded.bulletin_date.isoformat(),
        "extracted_records": len(records),
        "stored_records": total_stored_records,
        "raw_pdf_path": str(downloaded.pdf_path),
        "parquet_path": str(parquet_path),
        "validation_report_path": str(validation_report_path),
        "source_sha256": downloaded.sha256,
    }
