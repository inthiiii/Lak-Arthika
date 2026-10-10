"""Command-line interface for LakArthika."""

import typer

from lak_arthika import __version__
from lak_arthika.config import get_settings

app = typer.Typer(
    name="lak-arthika",
    help="Developer commands for the LakArthika platform.",
    no_args_is_help=True,
)


@app.command()
def info() -> None:
    """Display information about the current application environment."""

    settings = get_settings()

    typer.echo(f"Service: {settings.app_name}")
    typer.echo(f"Version: {__version__}")
    typer.echo(f"Environment: {settings.environment}")


if __name__ == "__main__":
    app()
