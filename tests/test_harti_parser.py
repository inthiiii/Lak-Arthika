"""Tests for HARTI PDF-table normalization."""

from datetime import UTC, date, datetime

from lak_arthika.ingestion.harti import (
    extract_records_from_table,
    parse_price_range,
)


def test_parse_price_range() -> None:
    """Ranges, single prices and missing values should be recognized."""

    assert parse_price_range("400 - 450") == (400.0, 450.0)
    assert parse_price_range("1,200 - 1,300") == (1200.0, 1300.0)
    assert parse_price_range("120") == (120.0, 120.0)
    assert parse_price_range("-") is None
    assert parse_price_range(None) is None


def test_extract_records_from_table() -> None:
    """The parser should normalize market-price cells into records."""

    rows: list[list[str | None]] = [
        [
            "Variety",
            "2026.10.07",
            "2026.10.07",
            "2026.10.06",
        ],
        [
            None,
            "Peliyagoda\nMarket",
            "Dambulla\nMarket",
            "Veyangoda\nMarket",
        ],
        [
            "Up Country Vegetable",
            None,
            "",
            "",
        ],
        [
            "Beans",
            "400 - 450",
            "-",
            "440 - 500",
        ],
        [
            "Carrot",
            "150 - 160",
            "180",
            "-",
        ],
        [
            "Banana",
            "",
            "",
            "",
        ],
    ]

    records = extract_records_from_table(
        rows,
        bulletin_date=date(2026, 10, 7),
        source_url="https://example.test/harti.pdf",
        source_sha256="a" * 64,
        ingested_at=datetime(
            2026,
            10,
            7,
            12,
            0,
            tzinfo=UTC,
        ),
    )

    assert len(records) == 4

    beans_peliyagoda = next(
        record
        for record in records
        if record.commodity == "Beans" and record.market == "Peliyagoda"
    )

    assert beans_peliyagoda.price_min_lkr == 400
    assert beans_peliyagoda.price_max_lkr == 450
    assert beans_peliyagoda.price_midpoint_lkr == 425

    carrot_dambulla = next(
        record for record in records if record.commodity == "Carrot" and record.market == "Dambulla"
    )

    assert carrot_dambulla.price_min_lkr == 180
    assert carrot_dambulla.price_max_lkr == 180
