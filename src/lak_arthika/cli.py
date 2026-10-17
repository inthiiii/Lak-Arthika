"""Command-line interface for LakArthika."""

import json
from datetime import date
from pathlib import Path
from typing import Annotated

import httpx
import polars as pl
import typer

from lak_arthika import __version__
from lak_arthika.config import get_settings
from lak_arthika.forecasting.artifacts import load_metadata, load_quality
from lak_arthika.forecasting.health import assess_model_health
from lak_arthika.forecasting.trainer import train_forecasting_engine
from lak_arthika.pipelines.harti_daily import run_harti_daily_sync, run_harti_file_sync
from lak_arthika.pipelines.harti_historical import (
    discover_historical_bulletins,
    download_discovered_bulletins,
    ingest_local_historical_bulletin,
    process_downloaded_history,
)
from lak_arthika.signals.importers import import_official_csv
from lak_arthika.signals.nasa_power import fetch_power_signals
from lak_arthika.storage.analytics import query_price_history, refresh_analytics
from lak_arthika.storage.manifest import load_manifest
from lak_arthika.storage.signals import load_signals, store_signals
from lak_arthika.storage.stress import load_alerts, load_backtest, query_stress_signals
from lak_arthika.stress.engine import build_stress_engine

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

forecast_app = typer.Typer(
    help="Train and inspect experimental market-price forecasts.",
    no_args_is_help=True,
)
app.add_typer(forecast_app, name="forecast")

signals_app = typer.Typer(
    help="Ingest provenance-backed weather and economic signals.",
    no_args_is_help=True,
)
app.add_typer(signals_app, name="signals")

stress_app = typer.Typer(
    help="Build and inspect experimental economic-pressure warnings.",
    no_args_is_help=True,
)
app.add_typer(stress_app, name="stress")


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


@forecast_app.command("train")
def train_forecast(
    version: Annotated[str, typer.Option("--version", help="Immutable model version.")],
    cutoff: Annotated[
        str | None, typer.Option("--cutoff", help="Optional YYYY-MM-DD cutoff.")
    ] = None,
    force_promote: Annotated[
        bool,
        typer.Option(
            "--force-promote",
            help="Override the champion gate after explicit review.",
        ),
    ] = False,
) -> None:
    """Train, backtest, package and promote forecasting-engine-v1."""

    settings = get_settings()
    metadata = train_forecasting_engine(
        database_path=settings.harti_analytics_path,
        model_root=settings.forecast_model_root,
        model_version=version,
        cutoff=_parse_date(cutoff, option_name="--cutoff") if cutoff else None,
        signals_path=settings.external_signals_path,
        force_promote=force_promote,
    )
    typer.echo(metadata.model_dump_json(indent=2))


@forecast_app.command("status")
def forecast_status() -> None:
    """Show the promoted model and its out-of-time quality report."""

    settings = get_settings()
    try:
        payload = {
            "model": load_metadata(settings.forecast_model_root).model_dump(mode="json"),
            "quality": load_quality(settings.forecast_model_root).model_dump(mode="json"),
        }
    except FileNotFoundError as error:
        raise typer.BadParameter(
            "No promoted forecast exists. Run `lak-arthika forecast train --version forecast-v1`."
        ) from error
    typer.echo(json.dumps(payload, indent=2))


@forecast_app.command("health")
def forecast_health() -> None:
    """Assess champion performance, calibration and upstream freshness."""

    settings = get_settings()
    health = assess_model_health(
        model_root=settings.forecast_model_root,
        signals_path=settings.external_signals_path,
    )
    typer.echo(health.model_dump_json(indent=2))


@signals_app.command("sync-weather")
def sync_weather(
    start: Annotated[str, typer.Option("--from", help="First date (YYYY-MM-DD).")],
    end: Annotated[str, typer.Option("--to", help="Last date (YYYY-MM-DD).")],
) -> None:
    """Fetch NASA POWER rainfall, temperature and humidity for every market."""

    settings = get_settings()
    start_date = _parse_date(start, option_name="--from")
    end_date = _parse_date(end, option_name="--to")
    if start_date > end_date:
        raise typer.BadParameter("--from must be on or before --to")
    markets = pl.read_csv(settings.markets_reference_path).to_dicts()
    records = []
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        for market in markets:
            records.extend(
                fetch_power_signals(
                    market_id=str(market["market_id"]),
                    latitude=float(market["latitude"]),
                    longitude=float(market["longitude"]),
                    start=start_date,
                    end=end_date,
                    client=client,
                )
            )
    inserted = store_signals(records, settings.external_signals_path)
    typer.echo(json.dumps({"downloaded": len(records), "inserted": inserted}, indent=2))


@signals_app.command("import-official")
def import_official_signals(
    csv_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, resolve_path=True)],
    source: Annotated[str, typer.Option("--source", help="cbsl or ceypetco")],
) -> None:
    """Import a reviewed normalized CBSL or Ceypetco CSV extract."""

    settings = get_settings()
    records = import_official_csv(csv_path, source=source)
    inserted = store_signals(records, settings.external_signals_path)
    typer.echo(json.dumps({"read": len(records), "inserted": inserted}, indent=2))


@signals_app.command("status")
def signal_status() -> None:
    """Summarize the local external-signal feature store."""

    settings = get_settings()
    records = load_signals(settings.external_signals_path)
    by_source = {
        source: {
            "records": len([item for item in records if item.source == source]),
            "latest_effective_date": max(
                (item.effective_date for item in records if item.source == source),
                default=None,
            ),
        }
        for source in ("nasa_power", "cbsl", "ceypetco")
    }
    typer.echo(json.dumps(by_source, indent=2, default=str))


@stress_app.command("build")
def build_stress(
    cutoff: Annotated[
        str | None, typer.Option("--cutoff", help="Optional YYYY-MM-DD cutoff.")
    ] = None,
) -> None:
    """Build leakage-safe scores, alerts and an out-of-time report."""

    settings = get_settings()
    summary = build_stress_engine(
        database_path=settings.harti_analytics_path,
        signals_path=settings.stress_signals_path,
        alerts_path=settings.stress_alerts_path,
        report_path=settings.stress_report_path,
        cutoff=_parse_date(cutoff, option_name="--cutoff") if cutoff else None,
    )
    typer.echo(json.dumps(summary, indent=2, default=str))


@stress_app.command("status")
def stress_status() -> None:
    """Show current signal, alert and temporal-evaluation status."""

    settings = get_settings()
    try:
        signals = query_stress_signals(settings.stress_signals_path, latest=True)
        alerts = load_alerts(settings.stress_alerts_path)
        report = load_backtest(settings.stress_report_path)
    except FileNotFoundError as error:
        raise typer.BadParameter(
            "Stress artifacts are unavailable. Run `lak-arthika stress build`."
        ) from error
    typer.echo(
        json.dumps(
            {
                "current_signals": len(signals),
                "active_alerts": sum(item.status == "active" for item in alerts),
                "latest_observation_date": max(
                    (item.observation_date for item in signals), default=None
                ),
                "backtest": report.model_dump(mode="json"),
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    app()
