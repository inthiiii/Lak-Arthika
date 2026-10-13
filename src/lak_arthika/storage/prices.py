"""Storage operations for normalized commodity prices."""

from collections.abc import Sequence
from pathlib import Path

import polars as pl

from lak_arthika.models.price import PriceRecord

PRICE_IDENTITY_COLUMNS = [
    "source_sha256",
    "observation_date",
    "market",
    "commodity",
]


def upsert_price_records(
    records: Sequence[PriceRecord],
    destination: Path,
) -> int:
    """Append validated records without duplicating the same source revision."""

    if not records:
        raise ValueError("Cannot store an empty collection of price records.")

    destination.parent.mkdir(parents=True, exist_ok=True)

    current = pl.DataFrame([record.model_dump(mode="python") for record in records])

    if destination.exists():
        previous = pl.read_parquet(destination)
        combined = pl.concat(
            [previous, current],
            how="diagonal_relaxed",
        )
    else:
        combined = current

    combined = combined.unique(
        subset=PRICE_IDENTITY_COLUMNS,
        keep="last",
        maintain_order=True,
    ).sort(
        [
            "observation_date",
            "market",
            "category",
            "commodity",
        ]
    )

    temporary_destination = destination.with_suffix(".tmp.parquet")
    combined.write_parquet(temporary_destination)
    temporary_destination.replace(destination)

    return combined.height
