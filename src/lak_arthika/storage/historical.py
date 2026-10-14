"""Partitioned Parquet and interim storage for historical price records."""

import json
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

import polars as pl

from lak_arthika.models.price import PriceRecord
from lak_arthika.storage.prices import PRICE_IDENTITY_COLUMNS


def write_interim_records(
    records: Sequence[PriceRecord],
    *,
    destination_root: Path,
) -> Path:
    """Preserve parser output before publication into analytical partitions."""

    if not records:
        raise ValueError("Cannot preserve an empty parser result")

    bulletin_date = records[0].bulletin_date
    destination = (
        destination_root
        / str(bulletin_date.year)
        / f"{bulletin_date.month:02d}"
        / f"harti_{bulletin_date.isoformat()}_{records[0].source_sha256[:12]}.jsonl"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp.jsonl")

    with temporary.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(record.model_dump_json() + "\n")

    temporary.replace(destination)
    return destination


def upsert_partitioned_prices(
    records: Sequence[PriceRecord],
    *,
    destination_root: Path,
) -> int:
    """Upsert records into deterministic year/month Parquet partitions."""

    if not records:
        raise ValueError("Cannot store an empty collection of price records")

    grouped: dict[tuple[int, int], list[PriceRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.observation_date.year, record.observation_date.month)].append(record)

    for (year, month), partition_records in grouped.items():
        destination = destination_root / f"year={year}" / f"month={month:02d}" / "prices.parquet"
        destination.parent.mkdir(parents=True, exist_ok=True)
        current = pl.DataFrame([record.model_dump(mode="python") for record in partition_records])

        if destination.exists():
            current = pl.concat(
                [pl.read_parquet(destination), current],
                how="diagonal_relaxed",
            )

        current = current.unique(
            subset=PRICE_IDENTITY_COLUMNS,
            keep="last",
            maintain_order=True,
        ).sort(["observation_date", "market", "commodity"])
        temporary = destination.with_suffix(".tmp.parquet")
        current.write_parquet(temporary)
        temporary.replace(destination)

    return count_partitioned_prices(destination_root)


def partition_files(destination_root: Path) -> list[Path]:
    """Return all published price partitions in deterministic order."""

    return sorted(destination_root.glob("year=*/month=*/prices.parquet"))


def count_partitioned_prices(destination_root: Path) -> int:
    """Count all records across published partitions."""

    return sum(
        pl.scan_parquet(path).select(pl.len()).collect().item()
        for path in partition_files(destination_root)
    )


def export_partition_inventory(destination_root: Path) -> str:
    """Return a compact JSON inventory useful in CLI summaries."""

    inventory = [
        {"path": str(path), "records": pl.scan_parquet(path).select(pl.len()).collect().item()}
        for path in partition_files(destination_root)
    ]
    return json.dumps(inventory, sort_keys=True)
