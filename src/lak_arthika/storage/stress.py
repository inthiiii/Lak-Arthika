"""Persistence and read paths for pressure signals, alerts and evaluation."""

import json
from datetime import date
from pathlib import Path

import polars as pl

from lak_arthika.models.stress import (
    EconomicAlert,
    StressBacktestReport,
    StressComponents,
    StressSignal,
)


def store_stress_artifacts(
    signals: list[StressSignal],
    alerts: list[EconomicAlert],
    report: StressBacktestReport,
    *,
    signals_path: Path,
    alerts_path: Path,
    report_path: Path,
) -> None:
    """Atomically replace reproducible generated stress artifacts."""

    signals_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for signal in signals:
        row = signal.model_dump(mode="json", exclude={"components"})
        row.update(
            {f"component_{key}": value for key, value in signal.components.model_dump().items()}
        )
        rows.append(row)
    pl.DataFrame(rows).write_parquet(signals_path)
    alerts_path.write_text(
        json.dumps([item.model_dump(mode="json") for item in alerts], indent=2) + "\n"
    )
    report_path.write_text(report.model_dump_json(indent=2) + "\n")


def load_stress_signals(path: Path) -> list[StressSignal]:
    """Load validated signals from the generated feature store."""

    if not path.exists():
        raise FileNotFoundError(path)
    records = []
    for raw in pl.read_parquet(path).to_dicts():
        components = StressComponents(
            **{
                key: raw.pop(f"component_{key}")
                for key in ("anomaly", "momentum", "forecast_surprise", "spatial_pressure")
            }
        )
        records.append(StressSignal.model_validate({**raw, "components": components}))
    return records


def query_stress_signals(
    path: Path,
    *,
    market_id: str | None = None,
    commodity: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    latest: bool = False,
) -> list[StressSignal]:
    """Filter stress history; latest selects the newest row per market and commodity."""

    rows = load_stress_signals(path)
    rows = [
        row
        for row in rows
        if (market_id is None or row.market_id == market_id)
        and (commodity is None or row.commodity.casefold() == commodity.casefold())
        and (start_date is None or row.observation_date >= start_date)
        and (end_date is None or row.observation_date <= end_date)
    ]
    if latest:
        selected: dict[tuple[str, str], StressSignal] = {}
        for row in rows:
            key = row.market_id, row.commodity
            if key not in selected or row.observation_date > selected[key].observation_date:
                selected[key] = row
        rows = list(selected.values())
    return sorted(
        rows,
        key=lambda item: (item.observation_date, item.market_name, item.commodity),
        reverse=True,
    )


def load_alerts(path: Path) -> list[EconomicAlert]:
    if not path.exists():
        raise FileNotFoundError(path)
    return [EconomicAlert.model_validate(item) for item in json.loads(path.read_text())]


def load_backtest(path: Path) -> StressBacktestReport:
    if not path.exists():
        raise FileNotFoundError(path)
    return StressBacktestReport.model_validate_json(path.read_text())
