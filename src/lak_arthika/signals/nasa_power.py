"""NASA POWER daily weather adapter."""

import hashlib
import json
from datetime import UTC, date, datetime, timedelta

import httpx

from lak_arthika.models.signals import ExternalSignal
from lak_arthika.signals.catalog import NASA_POWER

PARAMETERS = {
    "PRECTOTCORR": ("rainfall_mm", "mm/day"),
    "T2M": ("temperature_mean_c", "celsius"),
    "RH2M": ("relative_humidity_pct", "percent"),
}


def build_power_url(*, latitude: float, longitude: float, start: date, end: date) -> str:
    """Build a reproducible NASA POWER request URL."""

    parameters = ",".join(PARAMETERS)
    return (
        f"{NASA_POWER.url}?parameters={parameters}&community=AG"
        f"&longitude={longitude}&latitude={latitude}"
        f"&start={start:%Y%m%d}&end={end:%Y%m%d}&format=JSON"
    )


def parse_power_response(
    payload: bytes,
    *,
    market_id: str,
    source_url: str,
    retrieved_at: datetime,
) -> list[ExternalSignal]:
    """Normalize one POWER point response and preserve its content digest."""

    document = json.loads(payload)
    values = document["properties"]["parameter"]
    digest = hashlib.sha256(payload).hexdigest()
    records: list[ExternalSignal] = []
    for parameter, (signal_name, unit) in PARAMETERS.items():
        for raw_date, raw_value in values.get(parameter, {}).items():
            value = float(raw_value)
            if value <= -900:
                continue
            effective_date = datetime.strptime(raw_date, "%Y%m%d").date()
            records.append(
                ExternalSignal(
                    signal_name=signal_name,
                    geography_id=market_id,
                    effective_date=effective_date,
                    available_date=effective_date + timedelta(days=NASA_POWER.expected_lag_days),
                    value=value,
                    unit=unit,
                    source="nasa_power",
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                    content_sha256=digest,
                    vintage=retrieved_at.date().isoformat(),
                )
            )
    return records


def fetch_power_signals(
    *,
    market_id: str,
    latitude: float,
    longitude: float,
    start: date,
    end: date,
    client: httpx.Client | None = None,
) -> list[ExternalSignal]:
    """Download and normalize weather history for one market coordinate."""

    source_url = build_power_url(latitude=latitude, longitude=longitude, start=start, end=end)
    owns_client = client is None
    resolved_client = client or httpx.Client(timeout=60.0, follow_redirects=True)
    try:
        response = resolved_client.get(source_url)
        response.raise_for_status()
        return parse_power_response(
            response.content,
            market_id=market_id,
            source_url=source_url,
            retrieved_at=datetime.now(UTC),
        )
    finally:
        if owns_client:
            resolved_client.close()
