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
    harti_price_parquet_path: Path = Path("data/processed/harti/daily_wholesale_prices.parquet")
    harti_validation_report_path: Path = Path("data/processed/harti/last_validation.json")


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""

    return Settings()
