"""Build direct multi-horizon forecasting features from historical prices."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from statistics import fmean, pstdev

import duckdb
import numpy as np
from numpy.typing import NDArray

from lak_arthika.signals.features import EXTERNAL_FEATURE_NAMES, SignalIndex

FEATURE_VERSION = "price-and-external-signals-v2"
MIN_HISTORY = 28
FEATURE_NAMES = (
    "current_price",
    "lag_1",
    "lag_2",
    "lag_3",
    "lag_7",
    "lag_14",
    "lag_28",
    "rolling_mean_7",
    "rolling_mean_14",
    "rolling_mean_28",
    "rolling_std_7",
    "rolling_std_28",
    "days_since_last_observation",
    "day_of_week",
    "week_of_year",
    "month",
    "market_code",
    "commodity_code",
    *EXTERNAL_FEATURE_NAMES,
)


@dataclass(frozen=True)
class PriceObservation:
    """One geocoded price observation used by the feature builder."""

    observation_date: date
    market_id: str
    market_name: str
    commodity: str
    category: str
    price_midpoint_lkr: float


@dataclass(frozen=True)
class FeatureMappings:
    """Stable categorical mappings persisted with a trained model."""

    markets: dict[str, int]
    commodities: dict[str, int]


@dataclass(frozen=True)
class FeatureRow:
    """A feature vector with its temporal and series identity."""

    origin_date: date
    target_date: date
    market_id: str
    market_name: str
    commodity: str
    category: str
    current_price_lkr: float
    values: tuple[float, ...]
    target: float | None = None


def load_price_observations(
    database_path: Path,
    *,
    cutoff: date | None = None,
) -> list[PriceObservation]:
    """Load clean, geocoded observations from the DuckDB analytical layer."""

    where = "AND observation_date <= ?" if cutoff else ""
    parameters: list[object] = [cutoff] if cutoff else []
    with duckdb.connect(str(database_path), read_only=True) as connection:
        rows = connection.execute(
            f"""
            SELECT
                observation_date,
                market_id,
                market,
                commodity,
                category,
                price_midpoint_lkr
            FROM price_history
            WHERE market_id IS NOT NULL
              AND price_midpoint_lkr IS NOT NULL
              AND price_midpoint_lkr > 0
              {where}
            ORDER BY market_id, commodity, observation_date
            """,
            parameters,
        ).fetchall()

    return [
        PriceObservation(
            observation_date=row[0],
            market_id=row[1],
            market_name=row[2],
            commodity=row[3],
            category=row[4],
            price_midpoint_lkr=float(row[5]),
        )
        for row in rows
    ]


def make_feature_mappings(observations: list[PriceObservation]) -> FeatureMappings:
    """Create deterministic categorical encodings for markets and commodities."""

    markets = {
        value: index for index, value in enumerate(sorted({o.market_id for o in observations}))
    }
    commodities = {
        value: index for index, value in enumerate(sorted({o.commodity for o in observations}))
    }
    return FeatureMappings(markets=markets, commodities=commodities)


def _series(observations: list[PriceObservation]) -> list[list[PriceObservation]]:
    grouped: dict[tuple[str, str], list[PriceObservation]] = defaultdict(list)
    for observation in observations:
        grouped[(observation.market_id, observation.commodity)].append(observation)
    return [sorted(values, key=lambda item: item.observation_date) for values in grouped.values()]


def _values(
    observations: list[PriceObservation],
    index: int,
    mappings: FeatureMappings,
    signal_index: SignalIndex | None = None,
) -> tuple[float, ...]:
    current = observations[index]
    prices = [item.price_midpoint_lkr for item in observations]
    previous = observations[index - 1]

    def lag(distance: int) -> float:
        return prices[index - distance]

    prior_7 = prices[index - 7 : index]
    prior_14 = prices[index - 14 : index]
    prior_28 = prices[index - 28 : index]
    iso_calendar = current.observation_date.isocalendar()
    base_values = (
        current.price_midpoint_lkr,
        lag(1),
        lag(2),
        lag(3),
        lag(7),
        lag(14),
        lag(28),
        fmean(prior_7),
        fmean(prior_14),
        fmean(prior_28),
        pstdev(prior_7),
        pstdev(prior_28),
        float((current.observation_date - previous.observation_date).days),
        float(current.observation_date.weekday()),
        float(iso_calendar.week),
        float(current.observation_date.month),
        float(mappings.markets.get(current.market_id, -1)),
        float(mappings.commodities.get(current.commodity, -1)),
    )
    external_values = (
        signal_index.features_for(current.market_id, current.observation_date)
        if signal_index
        else (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 999.0, 999.0, 999.0, 0.0, 0.0)
    )
    return (*base_values, *external_values)


def build_supervised_rows(
    observations: list[PriceObservation],
    *,
    horizon_days: int,
    mappings: FeatureMappings | None = None,
    minimum_history: int = MIN_HISTORY,
    signal_index: SignalIndex | None = None,
) -> tuple[list[FeatureRow], FeatureMappings]:
    """Build direct-horizon rows whose targets exist on the exact future date."""

    if horizon_days < 1:
        raise ValueError("horizon_days must be positive")
    resolved_mappings = mappings or make_feature_mappings(observations)
    rows: list[FeatureRow] = []

    for values in _series(observations):
        target_by_date = {item.observation_date: item.price_midpoint_lkr for item in values}
        for index in range(minimum_history, len(values)):
            current = values[index]
            target_date = current.observation_date + timedelta(days=horizon_days)
            target = target_by_date.get(target_date)
            if target is None:
                continue
            rows.append(
                FeatureRow(
                    origin_date=current.observation_date,
                    target_date=target_date,
                    market_id=current.market_id,
                    market_name=current.market_name,
                    commodity=current.commodity,
                    category=current.category,
                    current_price_lkr=current.price_midpoint_lkr,
                    values=_values(values, index, resolved_mappings, signal_index),
                    target=target,
                )
            )
    return rows, resolved_mappings


def build_prediction_rows(
    observations: list[PriceObservation],
    *,
    horizon_days: int,
    mappings: FeatureMappings,
    minimum_history: int = MIN_HISTORY,
    signal_index: SignalIndex | None = None,
) -> list[FeatureRow]:
    """Build one latest feature row for each sufficiently long series."""

    rows: list[FeatureRow] = []
    for values in _series(observations):
        if len(values) <= minimum_history:
            continue
        index = len(values) - 1
        current = values[index]
        rows.append(
            FeatureRow(
                origin_date=current.observation_date,
                target_date=current.observation_date + timedelta(days=horizon_days),
                market_id=current.market_id,
                market_name=current.market_name,
                commodity=current.commodity,
                category=current.category,
                current_price_lkr=current.price_midpoint_lkr,
                values=_values(values, index, mappings, signal_index),
            )
        )
    return rows


def matrix(rows: list[FeatureRow]) -> NDArray[np.float64]:
    """Convert feature rows to a numeric matrix in the declared feature order."""

    return np.asarray([row.values for row in rows], dtype=np.float64)


def targets(rows: list[FeatureRow]) -> NDArray[np.float64]:
    """Convert supervised targets to a numeric vector."""

    if any(row.target is None for row in rows):
        raise ValueError("All rows must contain a target")
    return np.asarray([row.target for row in rows], dtype=np.float64)
