"""Application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LAKARTHIKA_",
        extra="ignore",
    )

    app_name: str = "LakArthika"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    harti_raw_root: Path = Path("data/raw/harti/daily")
    harti_interim_root: Path = Path("data/interim/harti/daily")
    harti_partitioned_root: Path = Path("data/processed/harti/prices")
    harti_price_parquet_path: Path = Path("data/processed/harti/daily_wholesale_prices.parquet")
    harti_validation_report_path: Path = Path("data/processed/harti/last_validation.json")
    harti_manifest_path: Path = Path("data/metadata/harti_bulletins.parquet")
    harti_quarantine_path: Path = Path("data/metadata/harti_quarantine.jsonl")
    harti_analytics_path: Path = Path("data/analytics/lak_arthika.duckdb")
    markets_reference_path: Path = Path("data/reference/markets.csv")
    forecast_model_root: Path = Path("models/forecasting")
    external_signals_path: Path = Path("data/processed/signals/external_signals.parquet")
    harti_request_delay_seconds: float = 1.0
    harti_max_download_attempts: int = 3
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        """Return normalized browser origins configured for CORS."""

        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""

    return Settings()
