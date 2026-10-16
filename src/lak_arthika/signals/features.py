"""Point-in-time external-signal feature joins."""

from collections import defaultdict
from datetime import date
from statistics import fmean

from lak_arthika.models.signals import ExternalSignal

EXTERNAL_FEATURE_NAMES = (
    "rainfall_7d_mm",
    "rainfall_30d_mm",
    "temperature_7d_mean_c",
    "relative_humidity_7d_mean_pct",
    "auto_diesel_lkr",
    "usd_lkr",
    "weather_age_days",
    "fuel_age_days",
    "fx_age_days",
    "is_weekend",
    "is_month_end",
)


class SignalIndex:
    """In-memory index that enforces `available_date <= origin_date`."""

    def __init__(self, records: list[ExternalSignal]) -> None:
        self._records: dict[tuple[str, str], list[ExternalSignal]] = defaultdict(list)
        for record in records:
            self._records[(record.geography_id, record.signal_name)].append(record)
        for values in self._records.values():
            values.sort(key=lambda item: (item.effective_date, item.available_date, item.vintage))

    def _available(
        self, geography_id: str, signal_name: str, origin_date: date
    ) -> list[ExternalSignal]:
        local = self._records.get((geography_id, signal_name), [])
        national = self._records.get(("national", signal_name), [])
        return [
            item
            for item in [*local, *national]
            if item.effective_date <= origin_date and item.available_date <= origin_date
        ]

    def latest(
        self, geography_id: str, signal_name: str, origin_date: date
    ) -> ExternalSignal | None:
        """Return the latest signal that was available at the prediction origin."""

        values = self._available(geography_id, signal_name, origin_date)
        return max(values, key=lambda item: (item.effective_date, item.vintage)) if values else None

    def window(
        self,
        geography_id: str,
        signal_name: str,
        origin_date: date,
        *,
        days: int,
    ) -> list[ExternalSignal]:
        """Return available observations in a trailing effective-date window."""

        return [
            item
            for item in self._available(geography_id, signal_name, origin_date)
            if 0 <= (origin_date - item.effective_date).days < days
        ]

    def features_for(self, market_id: str, origin_date: date) -> tuple[float, ...]:
        """Produce stable numeric features and explicit missingness ages."""

        rainfall_7 = self.window(market_id, "rainfall_mm", origin_date, days=7)
        rainfall_30 = self.window(market_id, "rainfall_mm", origin_date, days=30)
        temperature = self.window(market_id, "temperature_mean_c", origin_date, days=7)
        humidity = self.window(market_id, "relative_humidity_pct", origin_date, days=7)
        weather_latest = self.latest(market_id, "rainfall_mm", origin_date)
        fuel = self.latest("national", "auto_diesel_lkr", origin_date)
        exchange = self.latest("national", "usd_lkr", origin_date)

        def mean_or_zero(values: list[ExternalSignal]) -> float:
            return fmean(item.value for item in values) if values else 0.0

        def age_or_sentinel(item: ExternalSignal | None) -> float:
            return float((origin_date - item.effective_date).days) if item else 999.0

        next_day = origin_date.toordinal() + 1
        is_month_end = date.fromordinal(next_day).month != origin_date.month
        return (
            sum(item.value for item in rainfall_7),
            sum(item.value for item in rainfall_30),
            mean_or_zero(temperature),
            mean_or_zero(humidity),
            fuel.value if fuel else 0.0,
            exchange.value if exchange else 0.0,
            age_or_sentinel(weather_latest),
            age_or_sentinel(fuel),
            age_or_sentinel(exchange),
            float(origin_date.weekday() >= 5),
            float(is_month_end),
        )
