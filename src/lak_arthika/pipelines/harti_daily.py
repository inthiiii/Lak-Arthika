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
    extract_wholesale_vegetable_prices,
    preserve_local_bulletin,
)
from lak_arthika.models.price import PriceRecord
from lak_arthika.storage.prices import upsert_price_records


def validate_extracted_records(
    records: Sequence[PriceRecord],
) -> dict[str, object]:
    """Run publication-blocking validation checks."""

    markets = sorted({record.market for record in records})
    commodities = sorted({record.commodity for record in records})

    checks = {
        "has_at_least_50_records": len(records) >= 50,
        "has_at_least_5_markets": len(markets) >= 5,
        "has_at_least_10_commodities": len(commodities) >= 10,
        "all_prices_are_positive": all(
            record.price_min_lkr > 0 and record.price_max_lkr > 0 for record in records
        ),
        "all_ranges_are_ordered": all(
            record.price_min_lkr <= record.price_max_lkr for record in records
        ),
    }

    return {
        "valid": all(checks.values()),
        "record_count": len(records),
        "market_count": len(markets),
        "commodity_count": len(commodities),
        "markets": markets,
        "checks": checks,
    }


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

    records = extract_wholesale_vegetable_prices(downloaded)
    validation_report = validate_extracted_records(records)

    validation_report.update(
        {
            "bulletin_date": downloaded.bulletin_date.isoformat(),
            "source_url": downloaded.source_url,
            "source_sha256": downloaded.sha256,
            "raw_pdf_path": str(downloaded.pdf_path),
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
