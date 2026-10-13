"""LakArthika HTTP API."""

from pathlib import Path
from typing import Literal

import polars as pl
from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel

from lak_arthika import __version__
from lak_arthika.config import get_settings
from lak_arthika.models.price import PriceRecord


class HealthResponse(BaseModel):
    """Response returned by the service health endpoint."""

    status: Literal["ok"]
    service: str
    environment: str
    version: str


def load_latest_prices(
    parquet_path: Path,
    *,
    market: str | None = None,
    commodity: str | None = None,
    limit: int = 100,
) -> list[PriceRecord]:
    """Load the newest observation for every requested market/commodity pair."""

    if not parquet_path.exists():
        raise FileNotFoundError(parquet_path)

    prices = pl.read_parquet(parquet_path)

    if market:
        prices = prices.filter(pl.col("market").str.to_lowercase() == market.strip().lower())

    if commodity:
        prices = prices.filter(pl.col("commodity").str.to_lowercase() == commodity.strip().lower())

    if prices.is_empty():
        return []

    latest = (
        prices.sort(
            ["observation_date", "ingested_at"],
            descending=[True, True],
        )
        .unique(
            subset=["market", "commodity"],
            keep="first",
            maintain_order=True,
        )
        .sort(["market", "commodity"])
        .head(limit)
    )

    return [PriceRecord.model_validate(row) for row in latest.to_dicts()]


def create_app(
    price_data_path: Path | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        description=(
            "Economic forecasting, early-warning and scenario-simulation services for Sri Lanka."
        ),
        version=__version__,
    )

    application.state.harti_price_data_path = price_data_path or settings.harti_price_parquet_path

    @application.get(
        "/health",
        response_model=HealthResponse,
        tags=["Operations"],
    )
    def health() -> HealthResponse:
        """Confirm that the API is running."""

        return HealthResponse(
            status="ok",
            service=settings.app_name,
            environment=settings.environment,
            version=__version__,
        )

    @application.get(
        "/v1/prices/latest",
        response_model=list[PriceRecord],
        tags=["Prices"],
    )
    def latest_prices(
        request: Request,
        market: str | None = Query(
            default=None,
            description="Optional exact market name, such as Dambulla.",
        ),
        commodity: str | None = Query(
            default=None,
            description="Optional exact commodity name, such as Carrot.",
        ),
        limit: int = Query(default=100, ge=1, le=1_000),
    ) -> list[PriceRecord]:
        """Return the newest available normalized HARTI prices."""

        parquet_path = Path(request.app.state.harti_price_data_path)

        try:
            return load_latest_prices(
                parquet_path,
                market=market,
                commodity=commodity,
                limit=limit,
            )
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=503,
                detail=(
                    "HARTI price data is not available. Run `lak-arthika harti sync-latest` "
                    "or `lak-arthika harti ingest-file --help` first."
                ),
            ) from error

    return application


app = create_app()
