"""Command-line interface for LakArthika."""

import json
from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from lak_arthika import __version__
from lak_arthika.config import get_settings
from lak_arthika.pipelines.harti_daily import run_harti_daily_sync, run_harti_file_sync

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

    try:
        parsed_date = date.fromisoformat(bulletin_date)
    except ValueError as error:
        raise typer.BadParameter(
            "Expected YYYY-MM-DD.",
            param_hint="--bulletin-date",
        ) from error

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


if __name__ == "__main__":
    app()
