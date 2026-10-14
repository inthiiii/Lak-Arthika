# HARTI historical data engine

## Responsibilities

The Phase 1B engine separates source acquisition from publication so a website outage,
layout change or malformed bulletin cannot silently corrupt training data.

1. Discovery records official English PDF links in a Parquet manifest.
2. Downloading is resumable, rate-limited, checksummed and retry bounded.
3. Parser selection is versioned to support historical layout changes.
4. Parser output is preserved as interim JSONL before publication.
5. Quality checks either publish records or append a quarantine event.
6. Published records are idempotently partitioned by observation year and month.
7. DuckDB views add rolling statistics and geographic market attributes.
8. FastAPI exposes history, summaries, markets and ingestion health.

## Identity and lineage

Bulletins are identified by publication date and source URL. Price records are identified by
source checksum, observation date, market and commodity. The raw PDF checksum is carried into
every published record, preserving a direct audit path from API output to source document.

## Safe failure behaviour

Network failures remain in the manifest with an error. Parser and validation failures are
quarantined. Neither state writes to the gold Parquet partitions. A later run can resume failed
downloads, while quarantined documents require a parser or data-quality review.

## Geospatial boundary

Market coordinates are maintained in a small reviewed CSV, not inferred during ingestion.
This makes the future map deterministic and gives district/province filters a stable source.
