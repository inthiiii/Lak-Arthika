"""Idempotent Parquet storage for immutable external signal vintages."""

from pathlib import Path

import polars as pl

from lak_arthika.models.signals import ExternalSignal

SIGNAL_KEY = [
    "source",
    "signal_name",
    "geography_id",
    "effective_date",
    "available_date",
    "vintage",
]


def store_signals(records: list[ExternalSignal], path: Path) -> int:
    """Append records idempotently and return the number of newly stored rows."""

    if not records:
        return 0
    incoming = pl.DataFrame([record.model_dump(mode="python") for record in records])
    existing = pl.read_parquet(path) if path.exists() else None
    combined = (
        incoming if existing is None else pl.concat([existing, incoming], how="diagonal_relaxed")
    )
    before = 0 if existing is None else existing.height
    combined = combined.unique(subset=SIGNAL_KEY, keep="last").sort(
        ["source", "signal_name", "geography_id", "effective_date", "vintage"]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    combined.write_parquet(path, compression="zstd")
    return max(0, combined.height - before)


def load_signals(path: Path) -> list[ExternalSignal]:
    """Load validated signals from the local feature store."""

    if not path.exists():
        return []
    return [ExternalSignal.model_validate(row) for row in pl.read_parquet(path).to_dicts()]
