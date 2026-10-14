"""Parquet-backed bulletin manifest."""

from collections.abc import Sequence
from pathlib import Path

import polars as pl

from lak_arthika.models.manifest import BulletinManifestRecord

MANIFEST_IDENTITY = ["bulletin_date", "source_url"]


def load_manifest(path: Path) -> list[BulletinManifestRecord]:
    """Read all manifest records, returning an empty list before first discovery."""

    if not path.exists():
        return []

    return [BulletinManifestRecord.model_validate(row) for row in pl.read_parquet(path).to_dicts()]


def upsert_manifest(
    records: Sequence[BulletinManifestRecord],
    *,
    destination: Path,
) -> int:
    """Atomically insert or update manifest rows while preserving first-seen time."""

    if not records:
        return len(load_manifest(destination))

    existing = {record.identity: record for record in load_manifest(destination)}

    for record in records:
        previous = existing.get(record.identity)
        if previous is not None:
            record = record.model_copy(update={"first_seen_at": previous.first_seen_at})
        existing[record.identity] = record

    frame = pl.DataFrame(
        [record.model_dump(mode="python") for record in existing.values()],
        infer_schema_length=None,
    ).sort(MANIFEST_IDENTITY)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp.parquet")
    frame.write_parquet(temporary)
    temporary.replace(destination)
    return frame.height


def manifest_by_url(path: Path) -> dict[str, BulletinManifestRecord]:
    """Index the manifest by canonical source URL."""

    return {record.source_url: record for record in load_manifest(path)}
