"""Publication-blocking quality checks and quarantine reporting."""

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

from lak_arthika.models.price import PriceRecord


def assess_price_records(records: Sequence[PriceRecord]) -> dict[str, object]:
    """Evaluate structural, semantic and duplicate checks for one bulletin."""

    markets = sorted({record.market for record in records})
    commodities = sorted({record.commodity for record in records})
    identities = {(record.observation_date, record.market, record.commodity) for record in records}
    dates_are_plausible = all(
        record.bulletin_date - timedelta(days=7)
        <= record.observation_date
        <= record.bulletin_date + timedelta(days=1)
        for record in records
    )
    ratios_are_plausible = all(
        record.price_max_lkr / record.price_min_lkr <= 20 for record in records
    )

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
        "contains_no_duplicate_series": len(identities) == len(records),
        "observation_dates_are_plausible": dates_are_plausible,
        "price_ranges_are_plausible": ratios_are_plausible,
    }

    return {
        "valid": all(checks.values()),
        "record_count": len(records),
        "market_count": len(markets),
        "commodity_count": len(commodities),
        "markets": markets,
        "checks": checks,
    }


def append_quarantine_event(
    *,
    destination: Path,
    source_url: str,
    bulletin_date: str,
    reason: str,
    validation: dict[str, object] | None = None,
) -> None:
    """Append a machine-readable failure without contaminating clean datasets."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "source_url": source_url,
        "bulletin_date": bulletin_date,
        "reason": reason,
        "validation": validation,
    }

    with destination.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, default=str, sort_keys=True) + "\n")
