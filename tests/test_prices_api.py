"""Tests for Parquet-backed price API behavior."""

from datetime import UTC, date, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from lak_arthika.api import create_app
from lak_arthika.models.price import PriceRecord
from lak_arthika.storage.prices import upsert_price_records


def make_record(
    *,
    observation_date: date,
    minimum: float,
    maximum: float,
) -> PriceRecord:
    """Create a valid test observation."""

    return PriceRecord(
        bulletin_date=observation_date,
        observation_date=observation_date,
        category="Up Country Vegetable",
        commodity="Carrot",
        market="Dambulla",
        price_min_lkr=minimum,
        price_max_lkr=maximum,
        price_midpoint_lkr=(minimum + maximum) / 2,
        source_url="https://example.test/harti.pdf",
        source_sha256=observation_date.isoformat()
        .replace("-", "a")
        .ljust(
            64,
            "a",
        ),
        ingested_at=datetime(
            observation_date.year,
            observation_date.month,
            observation_date.day,
            12,
            0,
            tzinfo=UTC,
        ),
    )


def test_latest_prices_returns_newest_record(
    tmp_path: Path,
) -> None:
    """Only the newest observation should be returned per series."""

    parquet_path = tmp_path / "prices.parquet"

    upsert_price_records(
        [
            make_record(
                observation_date=date(2026, 10, 6),
                minimum=100,
                maximum=120,
            ),
            make_record(
                observation_date=date(2026, 10, 7),
                minimum=130,
                maximum=150,
            ),
        ],
        destination=parquet_path,
    )

    client = TestClient(create_app(price_data_path=parquet_path))

    response = client.get(
        "/v1/prices/latest",
        params={
            "market": "Dambulla",
            "commodity": "Carrot",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1
    assert body[0]["observation_date"] == "2026-10-07"
    assert body[0]["price_min_lkr"] == 130
    assert body[0]["price_max_lkr"] == 150


def test_prices_endpoint_reports_missing_dataset(
    tmp_path: Path,
) -> None:
    """The API should fail clearly before the first ingestion."""

    missing_path = tmp_path / "missing.parquet"
    client = TestClient(create_app(price_data_path=missing_path))

    response = client.get("/v1/prices/latest")

    assert response.status_code == 503
