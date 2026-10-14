"""Tests for the Phase 1B historical data engine."""

from datetime import UTC, date, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from lak_arthika.api import create_app
from lak_arthika.ingestion.harti import BulletinLink, DownloadedBulletin
from lak_arthika.ingestion.harti_archive import parse_archive_index
from lak_arthika.models.manifest import BulletinManifestRecord
from lak_arthika.models.price import PriceRecord
from lak_arthika.pipelines.harti_historical import (
    discover_historical_bulletins,
    download_discovered_bulletins,
    process_downloaded_history,
)
from lak_arthika.quality import assess_price_records
from lak_arthika.storage.analytics import (
    query_price_history,
    query_price_summary,
    refresh_analytics,
)
from lak_arthika.storage.historical import (
    count_partitioned_prices,
    upsert_partitioned_prices,
)
from lak_arthika.storage.manifest import load_manifest, upsert_manifest


def make_price(day: date, *, price: float, source_character: str) -> PriceRecord:
    """Create a canonical historical test observation."""

    return PriceRecord(
        bulletin_date=day,
        observation_date=day,
        category="Up Country Vegetable",
        commodity="Carrot",
        market="Dambulla",
        price_min_lkr=price,
        price_max_lkr=price + 20,
        price_midpoint_lkr=price + 10,
        source_url=f"https://example.test/{day.isoformat()}.pdf",
        source_sha256=source_character * 64,
        ingested_at=datetime.combine(day, datetime.min.time(), tzinfo=UTC),
    )


def write_markets(path: Path) -> None:
    """Write the minimum geospatial reference needed by analytical tests."""

    path.write_text(
        "market_id,market_name,district,province,latitude,longitude,market_type\n"
        "dambulla,Dambulla,Matale,Central,7.8742,80.6511,dedicated-economic-centre\n",
        encoding="utf-8",
    )


def test_parse_archive_index_filters_language_date_and_duplicates() -> None:
    """Only unique English PDFs within the requested range should be indexed."""

    html = """
    <table><tbody>
      <tr><td>2025-01-02</td><td>English</td><td><a href="/daily/a.pdf">Download</a></td></tr>
      <tr><td>2025-01-02</td><td>English</td><td><a href="/daily/a.pdf">Download</a></td></tr>
      <tr><td>2025-01-03</td><td>Sinhala</td><td><a href="/daily/b.pdf">Download</a></td></tr>
      <tr><td>2024-12-31</td><td>English</td><td><a href="/daily/c.pdf">Download</a></td></tr>
    </tbody></table>
    """

    links = parse_archive_index(
        html,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        base_url="https://www.harti.gov.lk/archive",
    )

    assert len(links) == 1
    assert links[0].bulletin_date == date(2025, 1, 2)
    assert links[0].url == "https://www.harti.gov.lk/daily/a.pdf"


def test_manifest_upsert_preserves_identity_and_first_seen(tmp_path: Path) -> None:
    """State changes should update one manifest row rather than duplicate it."""

    destination = tmp_path / "manifest.parquet"
    first_seen = datetime(2025, 1, 1, tzinfo=UTC)
    discovered = BulletinManifestRecord(
        bulletin_date=date(2025, 1, 2),
        source_url="https://example.test/a.pdf",
        first_seen_at=first_seen,
        updated_at=first_seen,
    )
    upsert_manifest([discovered], destination=destination)
    upsert_manifest(
        [
            discovered.model_copy(
                update={
                    "status": "downloaded",
                    "sha256": "a" * 64,
                    "updated_at": datetime(2025, 1, 3, tzinfo=UTC),
                }
            )
        ],
        destination=destination,
    )

    records = load_manifest(destination)
    assert len(records) == 1
    assert records[0].status == "downloaded"
    assert records[0].first_seen_at == first_seen


def test_manifest_infers_optional_fields_beyond_first_hundred_rows(tmp_path: Path) -> None:
    """A late checksum must not conflict with nulls in a large discovered manifest."""

    destination = tmp_path / "manifest.parquet"
    records = [
        BulletinManifestRecord(
            bulletin_date=date(2025, 1, 1),
            source_url=f"https://example.test/{index:03d}.pdf",
        )
        for index in range(101)
    ]
    records[-1] = records[-1].model_copy(update={"status": "downloaded", "sha256": "a" * 64})

    assert upsert_manifest(records, destination=destination) == 101
    assert load_manifest(destination)[-1].sha256 == "a" * 64


def test_discovery_and_download_are_resumable(tmp_path: Path) -> None:
    """A completed download should be recorded and skipped by the next run."""

    manifest_path = tmp_path / "manifest.parquet"
    raw_root = tmp_path / "raw"
    bulletin_day = date(2025, 1, 2)
    bulletin_url = "https://example.test/a.pdf"

    def fake_discoverer(**_: object) -> list[BulletinLink]:
        return [BulletinLink(bulletin_day, bulletin_url)]

    discover_historical_bulletins(
        start_date=bulletin_day,
        end_date=bulletin_day,
        manifest_path=manifest_path,
        discoverer=fake_discoverer,
    )

    calls = 0

    def fake_downloader(
        bulletin: BulletinLink,
        **_: object,
    ) -> DownloadedBulletin:
        nonlocal calls
        calls += 1
        pdf_path = raw_root / "a.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(b"%PDF-test")
        return DownloadedBulletin(
            bulletin_date=bulletin.bulletin_date,
            source_url=bulletin.url,
            pdf_path=pdf_path,
            metadata_path=raw_root / "a.metadata.json",
            sha256="a" * 64,
            ingested_at=datetime(2025, 1, 2, tzinfo=UTC),
        )

    first = download_discovered_bulletins(
        start_date=bulletin_day,
        end_date=bulletin_day,
        manifest_path=manifest_path,
        raw_root=raw_root,
        max_attempts=1,
        request_delay_seconds=0,
        downloader=fake_downloader,
    )
    second = download_discovered_bulletins(
        start_date=bulletin_day,
        end_date=bulletin_day,
        manifest_path=manifest_path,
        raw_root=raw_root,
        max_attempts=1,
        request_delay_seconds=0,
        downloader=fake_downloader,
    )

    assert first["downloaded"] == 1
    assert second["attempted"] == 0
    assert calls == 1
    assert load_manifest(manifest_path)[0].status == "downloaded"


def test_parser_failure_is_quarantined_without_publication(tmp_path: Path) -> None:
    """A malformed PDF should never reach the partitioned gold dataset."""

    manifest_path = tmp_path / "manifest.parquet"
    invalid_pdf = tmp_path / "raw" / "invalid.pdf"
    invalid_pdf.parent.mkdir(parents=True)
    invalid_pdf.write_bytes(b"%PDF-invalid")
    upsert_manifest(
        [
            BulletinManifestRecord(
                bulletin_date=date(2025, 1, 2),
                source_url="https://example.test/invalid.pdf",
                status="downloaded",
                sha256="a" * 64,
                local_pdf_path=str(invalid_pdf),
            )
        ],
        destination=manifest_path,
    )

    result = process_downloaded_history(
        manifest_path=manifest_path,
        interim_root=tmp_path / "interim",
        partitioned_root=tmp_path / "prices",
        snapshot_path=tmp_path / "snapshot.parquet",
        quarantine_path=tmp_path / "quarantine.jsonl",
        analytics_path=tmp_path / "analytics.duckdb",
        markets_path=tmp_path / "markets.csv",
    )

    assert result["quarantined"] == 1
    assert result["published_records"] == 0
    assert load_manifest(manifest_path)[0].status == "quarantined"
    assert (tmp_path / "quarantine.jsonl").exists()


def test_partitioned_storage_and_duckdb_are_idempotent(tmp_path: Path) -> None:
    """Repeated publication should not duplicate records or analytical results."""

    partitioned_root = tmp_path / "prices"
    database_path = tmp_path / "analytics.duckdb"
    markets_path = tmp_path / "markets.csv"
    write_markets(markets_path)
    records = [
        make_price(date(2025, 1, 1), price=100, source_character="a"),
        make_price(date(2025, 1, 2), price=120, source_character="b"),
    ]

    assert upsert_partitioned_prices(records, destination_root=partitioned_root) == 2
    assert upsert_partitioned_prices(records, destination_root=partitioned_root) == 2
    assert count_partitioned_prices(partitioned_root) == 2

    refresh_analytics(
        database_path=database_path,
        partitioned_root=partitioned_root,
        markets_path=markets_path,
    )
    history = query_price_history(
        database_path=database_path,
        market="dambulla",
        commodity="carrot",
    )
    summary = query_price_summary(database_path=database_path)

    assert len(history) == 2
    assert history[0]["district"] == "Matale"
    assert history[0]["moving_average_7"] == 120
    assert summary[0]["observation_count"] == 2
    assert summary[0]["average_price_lkr"] == 120


def test_quality_gate_detects_duplicate_series() -> None:
    """Duplicate observations must be rejected before gold publication."""

    record = make_price(date(2025, 1, 1), price=100, source_character="a")
    report = assess_price_records([record, record])

    assert report["valid"] is False
    assert report["checks"]["contains_no_duplicate_series"] is False


def test_historical_and_market_api(tmp_path: Path) -> None:
    """History, map and quality endpoints should share the same local data products."""

    partitioned_root = tmp_path / "prices"
    database_path = tmp_path / "analytics.duckdb"
    markets_path = tmp_path / "markets.csv"
    manifest_path = tmp_path / "manifest.parquet"
    snapshot_path = tmp_path / "snapshot.parquet"
    write_markets(markets_path)
    records = [make_price(date(2025, 1, 2), price=120, source_character="b")]
    upsert_partitioned_prices(records, destination_root=partitioned_root)
    refresh_analytics(
        database_path=database_path,
        partitioned_root=partitioned_root,
        markets_path=markets_path,
    )
    upsert_manifest(
        [
            BulletinManifestRecord(
                bulletin_date=date(2025, 1, 2),
                source_url="https://example.test/a.pdf",
                status="processed",
                validation_status="passed",
                record_count=1,
            )
        ],
        destination=manifest_path,
    )
    client = TestClient(
        create_app(
            price_data_path=snapshot_path,
            analytics_path=database_path,
            markets_path=markets_path,
            manifest_path=manifest_path,
        )
    )

    markets_response = client.get("/v1/markets")
    history_response = client.get(
        "/v1/prices/history",
        params={"district": "Matale", "commodity": "Carrot"},
    )
    market_response = client.get("/v1/markets/dambulla/prices")
    quality_response = client.get("/v1/data-quality/status")

    assert markets_response.status_code == 200
    assert markets_response.json()[0]["latitude"] == 7.8742
    assert history_response.status_code == 200
    assert len(history_response.json()) == 1
    assert market_response.status_code == 200
    assert quality_response.json()["processed_bulletins"] == 1
