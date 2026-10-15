"""Command-line interface for LakArthika."""

import json
from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from lak_arthika import __version__
from lak_arthika.config import get_settings
from lak_arthika.pipelines.harti_daily import run_harti_daily_sync, run_harti_file_sync
from lak_arthika.pipelines.harti_historical import (
    discover_historical_bulletins,
    download_discovered_bulletins,
    ingest_local_historical_bulletin,
    process_downloaded_history,
)
from lak_arthika.storage.analytics import query_price_history, refresh_analytics
from lak_arthika.storage.manifest import load_manifest

app = typer.Typer(
    name="lak-arthika",
    help="Developer commands for the LakArthika platform.",
    no_args_is_help=True,
)

harti_app = typer.Typer(
    help="Download and process HARTI commodity-price data.",
    no_args_is_help=True,
)

app.add_typer(harti_app, name="harti")


def _parse_date(value: str, *, option_name: str) -> date:
    """Parse a CLI date with a consistent actionable error."""

    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise typer.BadParameter(
            "Expected YYYY-MM-DD.",
            param_hint=option_name,
        ) from error


@app.command()
def info() -> None:
    """Display information about the current environment."""

    settings = get_settings()

    typer.echo(f"Service: {settings.app_name}")
    typer.echo(f"Version: {__version__}")
    typer.echo(f"Environment: {settings.environment}")


@harti_app.command("sync-latest")
def sync_latest_harti_bulletin() -> None:
    """Process the newest English HARTI daily bulletin."""

    settings = get_settings()

    summary = run_harti_daily_sync(
        raw_root=settings.harti_raw_root,
        parquet_path=settings.harti_price_parquet_path,
        validation_report_path=settings.harti_validation_report_path,
    )

    typer.echo(json.dumps(summary, indent=2))


@harti_app.command("ingest-file")
def ingest_harti_bulletin(
    pdf_path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to an official HARTI daily-price PDF.",
        ),
    ],
    bulletin_date: Annotated[
        str,
        typer.Option(
            "--bulletin-date",
            help="Publication date in YYYY-MM-DD format.",
        ),
    ],
    source_url: Annotated[
        str,
        typer.Option(
            "--source-url",
            help="Official URL from which the PDF was obtained.",
        ),
    ],
) -> None:
    """Process an official bulletin that is already available locally."""

    parsed_date = _parse_date(bulletin_date, option_name="--bulletin-date")

    settings = get_settings()
    summary = run_harti_file_sync(
        source_path=pdf_path,
        bulletin_date=parsed_date,
        source_url=source_url,
        raw_root=settings.harti_raw_root,
        parquet_path=settings.harti_price_parquet_path,
        validation_report_path=settings.harti_validation_report_path,
    )

    typer.echo(json.dumps(summary, indent=2))


@harti_app.command("discover")
def discover_harti_archive(
    start: Annotated[str, typer.Option("--from", help="First bulletin date (YYYY-MM-DD).")],
    end: Annotated[str, typer.Option("--to", help="Last bulletin date (YYYY-MM-DD).")],
) -> None:
    """Index official English HARTI archive links without downloading them."""

    settings = get_settings()
    summary = discover_historical_bulletins(
        start_date=_parse_date(start, option_name="--from"),
        end_date=_parse_date(end, option_name="--to"),
        manifest_path=settings.harti_manifest_path,
    )
    typer.echo(json.dumps(summary, indent=2))


@harti_app.command("download")
def download_harti_archive(
    start: Annotated[str, typer.Option("--from", help="First bulletin date (YYYY-MM-DD).")],
    end: Annotated[str, typer.Option("--to", help="Last bulletin date (YYYY-MM-DD).")],
) -> None:
    """Resume downloads for discovered HARTI bulletins."""

    settings = get_settings()
    summary = download_discovered_bulletins(
        start_date=_parse_date(start, option_name="--from"),
        end_date=_parse_date(end, option_name="--to"),
        manifest_path=settings.harti_manifest_path,
        raw_root=settings.harti_raw_root,
        max_attempts=settings.harti_max_download_attempts,
        request_delay_seconds=settings.harti_request_delay_seconds,
    )
    typer.echo(json.dumps(summary, indent=2))


@harti_app.command("process")
def process_harti_archive(
    start: Annotated[str | None, typer.Option("--from")] = None,
    end: Annotated[str | None, typer.Option("--to")] = None,
) -> None:
    """Validate and publish all downloaded manifest entries."""

    settings = get_settings()
    summary = process_downloaded_history(
        manifest_path=settings.harti_manifest_path,
        interim_root=settings.harti_interim_root,
        partitioned_root=settings.harti_partitioned_root,
        snapshot_path=settings.harti_price_parquet_path,
        quarantine_path=settings.harti_quarantine_path,
        analytics_path=settings.harti_analytics_path,
        markets_path=settings.markets_reference_path,
        start_date=_parse_date(start, option_name="--from") if start else None,
        end_date=_parse_date(end, option_name="--to") if end else None,
    )
    typer.echo(json.dumps(summary, indent=2))


@harti_app.command("backfill")
def backfill_harti_archive(
    start: Annotated[str, typer.Option("--from", help="First bulletin date (YYYY-MM-DD).")],
    end: Annotated[str, typer.Option("--to", help="Last bulletin date (YYYY-MM-DD).")],
) -> None:
    """Discover, download and process a historical date range."""

    settings = get_settings()
    parsed_start = _parse_date(start, option_name="--from")
    parsed_end = _parse_date(end, option_name="--to")
    results = {
        "discovery": discover_historical_bulletins(
            start_date=parsed_start,
            end_date=parsed_end,
            manifest_path=settings.harti_manifest_path,
        ),
        "download": download_discovered_bulletins(
            start_date=parsed_start,
            end_date=parsed_end,
            manifest_path=settings.harti_manifest_path,
            raw_root=settings.harti_raw_root,
            max_attempts=settings.harti_max_download_attempts,
            request_delay_seconds=settings.harti_request_delay_seconds,
        ),
        "process": process_downloaded_history(
            manifest_path=settings.harti_manifest_path,
            interim_root=settings.harti_interim_root,
            partitioned_root=settings.harti_partitioned_root,
            snapshot_path=settings.harti_price_parquet_path,
            quarantine_path=settings.harti_quarantine_path,
            analytics_path=settings.harti_analytics_path,
            markets_path=settings.markets_reference_path,
            start_date=parsed_start,
            end_date=parsed_end,
        ),
    }
    typer.echo(json.dumps(results, indent=2))


@harti_app.command("ingest-history-file")
def ingest_historical_file(
    pdf_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, resolve_path=True)],
    bulletin_date: Annotated[str, typer.Option("--bulletin-date")],
    source_url: Annotated[str, typer.Option("--source-url")],
) -> None:
    """Publish one manually obtained PDF through the historical pipeline."""

    settings = get_settings()
    summary = ingest_local_historical_bulletin(
        source_path=pdf_path,
        bulletin_date=_parse_date(bulletin_date, option_name="--bulletin-date"),
        source_url=source_url,
        raw_root=settings.harti_raw_root,
        manifest_path=settings.harti_manifest_path,
        interim_root=settings.harti_interim_root,
        partitioned_root=settings.harti_partitioned_root,
        snapshot_path=settings.harti_price_parquet_path,
        quarantine_path=settings.harti_quarantine_path,
        analytics_path=settings.harti_analytics_path,
        markets_path=settings.markets_reference_path,
    )
    typer.echo(json.dumps(summary, indent=2))


@harti_app.command("query")
def query_harti_history(
    market: Annotated[str | None, typer.Option("--market")] = None,
    commodity: Annotated[str | None, typer.Option("--commodity")] = None,
    start: Annotated[str | None, typer.Option("--from")] = None,
    end: Annotated[str | None, typer.Option("--to")] = None,
    limit: Annotated[int, typer.Option(min=1, max=10_000)] = 100,
) -> None:
    """Query the historical DuckDB analytical layer."""

    settings = get_settings()
    refresh_analytics(
        database_path=settings.harti_analytics_path,
        partitioned_root=settings.harti_partitioned_root,
        markets_path=settings.markets_reference_path,
    )
    rows = query_price_history(
        database_path=settings.harti_analytics_path,
        market=market,
        commodity=commodity,
        start_date=_parse_date(start, option_name="--from") if start else None,
        end_date=_parse_date(end, option_name="--to") if end else None,
        limit=limit,
    )
    typer.echo(json.dumps(rows, indent=2, default=str))


@harti_app.command("status")
def harti_status() -> None:
    """Summarize the historical bulletin manifest and analytical store."""

    settings = get_settings()
    records = load_manifest(settings.harti_manifest_path)
    counts = {
        state: sum(record.status == state for record in records)
        for state in ("processed", "quarantined", "failed", "downloaded", "discovered")
    }
    summary = {
        "total_bulletins": len(records),
        "processed_bulletins": counts["processed"],
        "quarantined_bulletins": counts["quarantined"],
        "failed_bulletins": counts["failed"],
        "pending_bulletins": counts["downloaded"] + counts["discovered"],
        "analytics_available": settings.harti_analytics_path.exists(),
        "manifest_path": str(settings.harti_manifest_path),
    }
    typer.echo(json.dumps(summary, indent=2))


if __name__ == "__main__":
    app()
