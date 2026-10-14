"""Historical discovery, download, validation and publication pipeline."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import structlog

from lak_arthika.ingestion.harti import (
    BulletinLink,
    DownloadedBulletin,
    preserve_local_bulletin,
)
from lak_arthika.ingestion.harti_archive import (
    discover_archive_bulletins,
    download_with_retries,
)
from lak_arthika.ingestion.parsers import select_parser
from lak_arthika.models.manifest import BulletinManifestRecord
from lak_arthika.quality import append_quarantine_event, assess_price_records
from lak_arthika.storage.analytics import refresh_analytics
from lak_arthika.storage.historical import (
    count_partitioned_prices,
    upsert_partitioned_prices,
    write_interim_records,
)
from lak_arthika.storage.manifest import load_manifest, manifest_by_url, upsert_manifest
from lak_arthika.storage.prices import upsert_price_records

Discoverer = Callable[..., list[BulletinLink]]
Downloader = Callable[..., DownloadedBulletin]
logger = structlog.get_logger(__name__)


def discover_historical_bulletins(
    *,
    start_date: date,
    end_date: date,
    manifest_path: Path,
    discoverer: Discoverer = discover_archive_bulletins,
) -> dict[str, object]:
    """Discover official archive links and idempotently update the manifest."""

    links = discoverer(start_date=start_date, end_date=end_date)
    logger.info(
        "harti.archive.discovered",
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        bulletin_count=len(links),
    )
    existing = manifest_by_url(manifest_path)
    now = datetime.now(UTC)
    records: list[BulletinManifestRecord] = []

    for link in links:
        previous = existing.get(link.url)
        records.append(
            previous.model_copy(update={"updated_at": now})
            if previous
            else BulletinManifestRecord(
                bulletin_date=link.bulletin_date,
                source_url=link.url,
                first_seen_at=now,
                updated_at=now,
            )
        )

    total = upsert_manifest(records, destination=manifest_path)
    return {
        "status": "success",
        "discovered_in_range": len(links),
        "manifest_records": total,
        "manifest_path": str(manifest_path),
    }


def download_discovered_bulletins(
    *,
    start_date: date,
    end_date: date,
    manifest_path: Path,
    raw_root: Path,
    max_attempts: int,
    request_delay_seconds: float,
    downloader: Downloader = download_with_retries,
) -> dict[str, object]:
    """Resume downloads for discovered or previously failed manifest rows."""

    candidates = [
        record
        for record in load_manifest(manifest_path)
        if start_date <= record.bulletin_date <= end_date
        and record.status in {"discovered", "failed"}
    ]
    downloaded = 0
    failures = 0

    for record in candidates:
        try:
            bulletin = downloader(
                BulletinLink(record.bulletin_date, record.source_url),
                raw_root=raw_root,
                max_attempts=max_attempts,
                request_delay_seconds=request_delay_seconds,
            )
            updated = record.model_copy(
                update={
                    "status": "downloaded",
                    "sha256": bulletin.sha256,
                    "local_pdf_path": str(bulletin.pdf_path),
                    "error_message": None,
                    "updated_at": datetime.now(UTC),
                }
            )
            downloaded += 1
            logger.info(
                "harti.bulletin.downloaded",
                bulletin_date=record.bulletin_date.isoformat(),
                source_url=record.source_url,
                sha256=bulletin.sha256,
            )
        except Exception as error:  # each source failure must not abort the backfill
            updated = record.model_copy(
                update={
                    "status": "failed",
                    "error_message": f"{type(error).__name__}: {error}",
                    "updated_at": datetime.now(UTC),
                }
            )
            failures += 1
            logger.warning(
                "harti.bulletin.download_failed",
                bulletin_date=record.bulletin_date.isoformat(),
                source_url=record.source_url,
                error=str(error),
            )

        upsert_manifest([updated], destination=manifest_path)

    return {
        "status": "success" if failures == 0 else "partial",
        "attempted": len(candidates),
        "downloaded": downloaded,
        "failed": failures,
        "manifest_path": str(manifest_path),
    }


def process_downloaded_history(
    *,
    manifest_path: Path,
    interim_root: Path,
    partitioned_root: Path,
    snapshot_path: Path,
    quarantine_path: Path,
    analytics_path: Path,
    markets_path: Path,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, object]:
    """Parse and publish downloaded sources, quarantining any unsafe result."""

    candidates = [
        record
        for record in load_manifest(manifest_path)
        if record.status == "downloaded"
        and (start_date is None or record.bulletin_date >= start_date)
        and (end_date is None or record.bulletin_date <= end_date)
    ]
    processed = 0
    quarantined = 0

    for record in candidates:
        validation: dict[str, object] | None = None
        try:
            if not record.local_pdf_path or not record.sha256:
                raise ValueError("Downloaded manifest record is missing file provenance")

            bulletin = DownloadedBulletin(
                bulletin_date=record.bulletin_date,
                source_url=record.source_url,
                pdf_path=Path(record.local_pdf_path),
                metadata_path=Path(record.local_pdf_path).with_suffix(".metadata.json"),
                sha256=record.sha256,
                ingested_at=record.updated_at,
            )
            parser = select_parser(bulletin)
            records = parser.parse(bulletin)
            validation = assess_price_records(records)
            write_interim_records(records, destination_root=interim_root)

            if validation.get("valid") is not True:
                raise ValueError("Extracted records failed publication checks")

            upsert_partitioned_prices(
                records,
                destination_root=partitioned_root,
            )
            upsert_price_records(records, destination=snapshot_path)
            updated = record.model_copy(
                update={
                    "status": "processed",
                    "parser_version": parser.version,
                    "record_count": len(records),
                    "validation_status": "passed",
                    "error_message": None,
                    "updated_at": datetime.now(UTC),
                }
            )
            processed += 1
            logger.info(
                "harti.bulletin.published",
                bulletin_date=record.bulletin_date.isoformat(),
                source_url=record.source_url,
                parser_version=parser.version,
                record_count=len(records),
            )
        except Exception as error:  # quarantine is an intentional safe failure boundary
            append_quarantine_event(
                destination=quarantine_path,
                source_url=record.source_url,
                bulletin_date=record.bulletin_date.isoformat(),
                reason=f"{type(error).__name__}: {error}",
                validation=validation,
            )
            updated = record.model_copy(
                update={
                    "status": "quarantined",
                    "validation_status": "failed",
                    "error_message": f"{type(error).__name__}: {error}",
                    "updated_at": datetime.now(UTC),
                }
            )
            quarantined += 1
            logger.warning(
                "harti.bulletin.quarantined",
                bulletin_date=record.bulletin_date.isoformat(),
                source_url=record.source_url,
                error=str(error),
            )
        upsert_manifest([updated], destination=manifest_path)

    if processed:
        refresh_analytics(
            database_path=analytics_path,
            partitioned_root=partitioned_root,
            markets_path=markets_path,
        )

    return {
        "status": "success" if quarantined == 0 else "partial",
        "attempted": len(candidates),
        "processed": processed,
        "quarantined": quarantined,
        "published_records": count_partitioned_prices(partitioned_root),
        "analytics_path": str(analytics_path),
    }


def register_downloaded_bulletin(
    bulletin: DownloadedBulletin,
    *,
    manifest_path: Path,
) -> BulletinManifestRecord:
    """Register a manually preserved source for historical processing."""

    now = datetime.now(UTC)
    current = manifest_by_url(manifest_path).get(bulletin.source_url)
    record = BulletinManifestRecord(
        bulletin_date=bulletin.bulletin_date,
        source_url=bulletin.source_url,
        status="downloaded",
        sha256=bulletin.sha256,
        local_pdf_path=str(bulletin.pdf_path),
        first_seen_at=current.first_seen_at if current else now,
        updated_at=bulletin.ingested_at,
    )
    upsert_manifest([record], destination=manifest_path)
    return record


def ingest_local_historical_bulletin(
    *,
    source_path: Path,
    bulletin_date: date,
    source_url: str,
    raw_root: Path,
    manifest_path: Path,
    interim_root: Path,
    partitioned_root: Path,
    snapshot_path: Path,
    quarantine_path: Path,
    analytics_path: Path,
    markets_path: Path,
) -> dict[str, object]:
    """Preserve, register and process one manually obtained official PDF."""

    bulletin = preserve_local_bulletin(
        BulletinLink(bulletin_date, source_url),
        source_path=source_path,
        raw_root=raw_root,
    )
    register_downloaded_bulletin(bulletin, manifest_path=manifest_path)
    return process_downloaded_history(
        manifest_path=manifest_path,
        interim_root=interim_root,
        partitioned_root=partitioned_root,
        snapshot_path=snapshot_path,
        quarantine_path=quarantine_path,
        analytics_path=analytics_path,
        markets_path=markets_path,
        start_date=bulletin_date,
        end_date=bulletin_date,
    )


def summarize_manifest(records: Sequence[BulletinManifestRecord]) -> dict[str, int]:
    """Count manifest states for observability and API responses."""

    counts = {
        status: 0 for status in ("discovered", "downloaded", "processed", "quarantined", "failed")
    }
    for record in records:
        counts[record.status] += 1
    return counts
