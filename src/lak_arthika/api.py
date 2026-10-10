"""LakArthika HTTP API."""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from lak_arthika import __version__
from lak_arthika.config import get_settings


class HealthResponse(BaseModel):
    """Response returned by the service health endpoint."""

    status: Literal["ok"]
    service: str
    environment: str
    version: str


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        description=(
            "Economic forecasting, early-warning and scenario-simulation services for Sri Lanka."
        ),
        version=__version__,
    )

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

    return application


app = create_app()
