"""Orchestration for the versioned economic-pressure engine."""

from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import duckdb

from lak_arthika.models.stress import StressMethodology, StressSignal
from lak_arthika.storage.stress import store_stress_artifacts
from lak_arthika.stress.alerts import derive_alerts
from lak_arthika.stress.backtest import evaluate_signals
from lak_arthika.stress.features import PriceFeatures, build_price_features
from lak_arthika.stress.scoring import (
    WEIGHTS,
    composite_score,
    confidence_for,
    normalize_components,
    severity_for,
)
from lak_arthika.stress.spatial import MarketNode, neighbours, pearson, weighted_neighbour_pressure


def methodology() -> StressMethodology:
    """Return stable public documentation for economic-stress-v1."""

    return StressMethodology(
        purpose="Early warning of unusual wholesale food-price pressure for decision support.",
        event_definition=(
            "A market/commodity price rises at least 20% within the following 14 calendar days."
        ),
        component_weights=WEIGHTS,
        severity_thresholds={"watch": 50, "warning": 70, "critical": 85},
        alert_policy={
            "minimum_persistent_observations": 2,
            "resolution_observations_below_40": 3,
            "cooldown_days": 7,
        },
        limitations=[
            "This is an experimental pressure warning, not a shortage prediction.",
            "It does not establish causality or recommend automatic policy action.",
            "Sparse or stale bulletins reduce confidence and can delay detection.",
            "Backtest performance may not represent future market conditions.",
        ],
    )


def _load_rows(database_path: Path, cutoff: date | None) -> list[dict[str, Any]]:
    if not database_path.exists():
        raise FileNotFoundError(database_path)
    cutoff_clause = "AND observation_date <= ?" if cutoff else ""
    parameters = [cutoff] if cutoff else []
    with duckdb.connect(str(database_path), read_only=True) as connection:
        cursor = connection.execute(
            f"""
            SELECT observation_date, market_id, market AS market_name, district, province,
                   latitude, longitude, commodity, avg(price_midpoint_lkr) AS price_midpoint_lkr
            FROM price_history
            WHERE market_id IS NOT NULL {cutoff_clause}
            GROUP BY ALL ORDER BY observation_date, market_id, commodity
            """,
            parameters,
        )
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _correlations(
    rows: list[dict[str, Any]], commodity: str, training_end: date
) -> dict[tuple[str, str], float]:
    by_market: dict[str, dict[date, float]] = defaultdict(dict)
    for row in rows:
        if row["commodity"] == commodity and row["observation_date"] <= training_end:
            by_market[str(row["market_id"])][row["observation_date"]] = float(
                row["price_midpoint_lkr"]
            )
    result: dict[tuple[str, str], float] = {}
    market_ids = sorted(by_market)
    for index, left in enumerate(market_ids):
        for right in market_ids[index + 1 :]:
            shared = sorted(set(by_market[left]) & set(by_market[right]))
            result[(left, right)] = pearson(
                [by_market[left][day] for day in shared], [by_market[right][day] for day in shared]
            )
    return result


def _event_labels(
    rows: list[dict[str, Any]],
) -> dict[tuple[str, str, date], tuple[bool, int | None]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["market_id"]), str(row["commodity"]))].append(row)
    labels: dict[tuple[str, str, date], tuple[bool, int | None]] = {}
    for (market_id, commodity), series in grouped.items():
        for index, current in enumerate(series):
            future = [
                row
                for row in series[index + 1 :]
                if 0 < (row["observation_date"] - current["observation_date"]).days <= 14
            ]
            triggering = [
                row
                for row in future
                if float(row["price_midpoint_lkr"]) >= float(current["price_midpoint_lkr"]) * 1.2
            ]
            if future:
                lead = (
                    min(
                        (row["observation_date"] - current["observation_date"]).days
                        for row in triggering
                    )
                    if triggering
                    else None
                )
                labels[(market_id, commodity, current["observation_date"])] = (
                    bool(triggering),
                    lead,
                )
    return labels


def build_signals(rows: list[dict[str, Any]]) -> list[StressSignal]:
    """Build historical signals using only information available on each date."""

    if not rows:
        raise ValueError("No geocoded price history is available.")
    all_dates = sorted({row["observation_date"] for row in rows})
    training_end = all_dates[max(0, int(len(all_dates) * 0.6) - 1)]
    latest_date = max(all_dates)
    nodes_by_id = {
        str(row["market_id"]): MarketNode(
            str(row["market_id"]), float(row["latitude"]), float(row["longitude"])
        )
        for row in rows
    }
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["market_id"]), str(row["commodity"]))].append(row)

    features: dict[tuple[str, str, date], PriceFeatures] = {}
    for (market_id, commodity), series in grouped.items():
        prices: list[float] = []
        for row in series:
            prices.append(float(row["price_midpoint_lkr"]))
            features[(market_id, commodity, row["observation_date"])] = build_price_features(prices)

    signals: list[StressSignal] = []
    for commodity in sorted({str(row["commodity"]) for row in rows}):
        graph = neighbours(
            list(nodes_by_id.values()), correlations=_correlations(rows, commodity, training_end)
        )
        commodity_rows = [row for row in rows if row["commodity"] == commodity]
        for observation_date in sorted({row["observation_date"] for row in commodity_rows}):
            daily = [row for row in commodity_rows if row["observation_date"] == observation_date]
            anomaly_by_market = {
                str(row["market_id"]): min(
                    features[(str(row["market_id"]), commodity, observation_date)].robust_z
                    / 4
                    * 100,
                    100,
                )
                for row in daily
            }
            for row in daily:
                market_id = str(row["market_id"])
                feature = features[(market_id, commodity, observation_date)]
                spatial = weighted_neighbour_pressure(market_id, anomaly_by_market, graph)
                components = normalize_components(feature, spatial)
                score = composite_score(components)
                signals.append(
                    StressSignal(
                        market_id=market_id,
                        market_name=str(row["market_name"]),
                        district=str(row["district"]),
                        province=str(row["province"]),
                        latitude=float(row["latitude"]),
                        longitude=float(row["longitude"]),
                        commodity=commodity,
                        observation_date=observation_date,
                        price_midpoint_lkr=float(row["price_midpoint_lkr"]),
                        score=score,
                        severity=severity_for(score),
                        confidence=confidence_for(
                            feature.evidence_observations, len(graph.get(market_id, []))
                        ),
                        components=components,
                        evidence_observations=feature.evidence_observations,
                        stale=(latest_date - observation_date).days > 7,
                    )
                )
    return signals


def build_stress_engine(
    *,
    database_path: Path,
    signals_path: Path,
    alerts_path: Path,
    report_path: Path,
    cutoff: date | None = None,
) -> dict[str, object]:
    """Build, evaluate and publish all v1 economic-pressure artifacts."""

    rows = _load_rows(database_path, cutoff)
    signals = build_signals(rows)
    report = evaluate_signals(signals, _event_labels(rows))
    alerts = derive_alerts(signals)
    store_stress_artifacts(
        signals,
        alerts,
        report,
        signals_path=signals_path,
        alerts_path=alerts_path,
        report_path=report_path,
    )
    return {
        "signals": len(signals),
        "alerts": len(alerts),
        "active_alerts": sum(item.status == "active" for item in alerts),
        "latest_observation_date": max(item.observation_date for item in signals),
        "selected_threshold": report.selected_threshold,
        "test_f1": report.f1,
    }
