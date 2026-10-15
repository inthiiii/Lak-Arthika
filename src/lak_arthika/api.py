"""LakArthika HTTP API."""

from datetime import date
from pathlib import Path
from typing import Annotated, Literal

import polars as pl
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from lak_arthika import __version__
from lak_arthika.config import get_settings
from lak_arthika.models.manifest import BulletinManifestRecord
from lak_arthika.models.market import CatalogResponse, MarketPricePoint, MarketReference
from lak_arthika.models.price import PriceRecord
from lak_arthika.models.quality import QualityStatus
from lak_arthika.storage.analytics import (
    query_catalog,
    query_market_price_points,
    query_price_history,
    query_price_summary,
)
from lak_arthika.storage.manifest import load_manifest


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


def load_markets(markets_path: Path) -> list[MarketReference]:
    """Load the version-controlled market and coordinate reference."""

    if not markets_path.exists():
        raise FileNotFoundError(markets_path)

    return [MarketReference.model_validate(row) for row in pl.read_csv(markets_path).to_dicts()]


def quality_status(records: list[BulletinManifestRecord]) -> QualityStatus:
    """Aggregate manifest states into an operational data-quality status."""

    counts = {
        status: sum(record.status == status for record in records)
        for status in ("processed", "quarantined", "failed")
    }
    pending = sum(record.status in {"discovered", "downloaded"} for record in records)
    errors = [record.error_message for record in records if record.error_message]
    return QualityStatus(
        total_bulletins=len(records),
        processed_bulletins=counts["processed"],
        quarantined_bulletins=counts["quarantined"],
        failed_bulletins=counts["failed"],
        pending_bulletins=pending,
        latest_error=errors[-1] if errors else None,
    )


def create_app(
    price_data_path: Path | None = None,
    analytics_path: Path | None = None,
    markets_path: Path | None = None,
    manifest_path: Path | None = None,
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
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
    )

    application.state.harti_price_data_path = price_data_path or settings.harti_price_parquet_path
    application.state.harti_analytics_path = analytics_path or settings.harti_analytics_path
    application.state.markets_reference_path = markets_path or settings.markets_reference_path
    application.state.harti_manifest_path = manifest_path or settings.harti_manifest_path

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

    @application.get("/v1/prices/history", tags=["Prices"])
    def price_history(
        request: Request,
        market: str | None = None,
        commodity: str | None = None,
        district: str | None = None,
        province: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = Query(default=1_000, ge=1, le=10_000),
    ) -> list[dict[str, object]]:
        """Return filtered historical observations and moving averages."""

        database_path = Path(request.app.state.harti_analytics_path)
        if not database_path.exists():
            raise HTTPException(status_code=503, detail="Historical analytics are not available.")

        return query_price_history(
            database_path=database_path,
            market=market,
            commodity=commodity,
            district=district,
            province=province,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    @application.get("/v1/prices/summary", tags=["Prices"])
    def price_summary(
        request: Request,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, object]]:
        """Return price range, average and volatility summaries."""

        database_path = Path(request.app.state.harti_analytics_path)
        if not database_path.exists():
            raise HTTPException(status_code=503, detail="Historical analytics are not available.")
        return query_price_summary(
            database_path=database_path,
            start_date=start_date,
            end_date=end_date,
        )

    @application.get(
        "/v1/catalog",
        response_model=CatalogResponse,
        tags=["Dashboard"],
    )
    def catalog(request: Request) -> CatalogResponse:
        """Return filter options and data coverage for public clients."""

        database_path = Path(request.app.state.harti_analytics_path)
        if not database_path.exists():
            raise HTTPException(status_code=503, detail="Historical analytics are not available.")
        try:
            reference_markets = load_markets(Path(request.app.state.markets_reference_path))
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=503, detail="Market reference is not available."
            ) from error
        commodities, minimum_date, maximum_date = query_catalog(database_path)
        return CatalogResponse(
            commodities=commodities,
            markets=reference_markets,
            minimum_date=minimum_date,
            maximum_date=maximum_date,
        )

    @application.get(
        "/v1/map/prices",
        response_model=list[MarketPricePoint],
        tags=["Dashboard"],
    )
    def map_prices(
        request: Request,
        commodity: Annotated[str, Query(min_length=1)],
        observation_date: Annotated[date | None, Query(alias="date")] = None,
    ) -> list[MarketPricePoint]:
        """Return map-ready market prices at or before a selected date."""

        database_path = Path(request.app.state.harti_analytics_path)
        if not database_path.exists():
            raise HTTPException(status_code=503, detail="Historical analytics are not available.")
        return [
            MarketPricePoint.model_validate(row)
            for row in query_market_price_points(
                database_path=database_path,
                commodity=commodity,
                observation_date=observation_date,
            )
        ]

    @application.get(
        "/v1/markets",
        response_model=list[MarketReference],
        tags=["Markets"],
    )
    def markets(request: Request) -> list[MarketReference]:
        """Return geocoded markets for map clients."""

        try:
            return load_markets(Path(request.app.state.markets_reference_path))
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=503, detail="Market reference is not available."
            ) from error

    @application.get("/v1/markets/{market_id}/prices", tags=["Markets"])
    def market_prices(
        market_id: str,
        request: Request,
        commodity: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = Query(default=1_000, ge=1, le=10_000),
    ) -> list[dict[str, object]]:
        """Return historical prices for one stable map market identifier."""

        database_path = Path(request.app.state.harti_analytics_path)
        try:
            reference_markets = load_markets(Path(request.app.state.markets_reference_path))
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=503, detail="Market reference is not available."
            ) from error
        if not database_path.exists():
            raise HTTPException(status_code=503, detail="Historical analytics are not available.")

        market = next((item for item in reference_markets if item.market_id == market_id), None)
        if market is None:
            raise HTTPException(status_code=404, detail="Market was not found.")
        return query_price_history(
            database_path=database_path,
            market=market.market_name,
            commodity=commodity,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    @application.get(
        "/v1/data-quality/status",
        response_model=QualityStatus,
        tags=["Data Quality"],
    )
    def data_quality_status(request: Request) -> QualityStatus:
        """Expose manifest-backed ingestion health."""

        records = load_manifest(Path(request.app.state.harti_manifest_path))
        return quality_status(records)

    return application


app = create_app()
