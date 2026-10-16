"""Strict normalized import contract for reviewed CBSL and CPC extracts."""

import csv
import hashlib
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from lak_arthika.models.signals import ExternalSignal
from lak_arthika.signals.catalog import SOURCES


def import_official_csv(path: Path, *, source: str) -> list[ExternalSignal]:
    """Import a reviewed official extract without guessing column meanings."""

    if source not in {"cbsl", "ceypetco"}:
        raise ValueError("source must be cbsl or ceypetco")
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    retrieved_at = datetime.now(UTC)
    specification = SOURCES[source]
    records: list[ExternalSignal] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"effective_date", "signal_name", "value", "unit", "source_url"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"CSV requires columns: {', '.join(sorted(required))}")
        for row in reader:
            effective_date = date.fromisoformat(row["effective_date"])
            records.append(
                ExternalSignal(
                    signal_name=row["signal_name"],
                    geography_id=row.get("geography_id") or "national",
                    effective_date=effective_date,
                    available_date=effective_date + timedelta(days=specification.expected_lag_days),
                    value=float(row["value"]),
                    unit=row["unit"],
                    source=source,  # type: ignore[arg-type]
                    source_url=row["source_url"],
                    retrieved_at=retrieved_at,
                    content_sha256=digest,
                    vintage=row.get("vintage") or retrieved_at.date().isoformat(),
                )
            )
    return records
