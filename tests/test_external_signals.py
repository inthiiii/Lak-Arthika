"""Tests for external signal provenance, point-in-time joins and health."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

from lak_arthika.forecasting.health import assess_model_health
from lak_arthika.models.signals import ExternalSignal
from lak_arthika.signals.features import SignalIndex
from lak_arthika.signals.importers import import_official_csv
from lak_arthika.signals.nasa_power import parse_power_response
from lak_arthika.storage.signals import load_signals, store_signals


def signal(
    *,
    effective_date: date,
    available_date: date,
    value: float,
    name: str = "rainfall_mm",
    geography: str = "dambulla",
) -> ExternalSignal:
    return ExternalSignal(
        signal_name=name,
        geography_id=geography,
        effective_date=effective_date,
        available_date=available_date,
        value=value,
        unit="test-unit",
        source="nasa_power",
        source_url="https://example.test/source",
        retrieved_at=datetime(2025, 2, 1, tzinfo=UTC),
        content_sha256="a" * 64,
        vintage="2025-02-01",
    )


def test_point_in_time_join_excludes_unavailable_future_signal() -> None:
    index = SignalIndex(
        [
            signal(
                effective_date=date(2025, 1, 1),
                available_date=date(2025, 1, 4),
                value=10,
            ),
            signal(
                effective_date=date(2025, 1, 2),
                available_date=date(2025, 1, 8),
                value=99,
            ),
        ]
    )
    assert index.latest("dambulla", "rainfall_mm", date(2025, 1, 5)).value == 10
    assert index.latest("dambulla", "rainfall_mm", date(2025, 1, 8)).value == 99


def test_signal_store_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "signals.parquet"
    record = signal(effective_date=date(2025, 1, 1), available_date=date(2025, 1, 4), value=10)
    assert store_signals([record], path) == 1
    assert store_signals([record], path) == 0
    assert load_signals(path) == [record]


def test_nasa_power_parser_preserves_availability_and_digest() -> None:
    payload = json.dumps(
        {
            "properties": {
                "parameter": {
                    "PRECTOTCORR": {"20250101": 4.5},
                    "T2M": {"20250101": 27.0},
                    "RH2M": {"20250101": 81.0},
                }
            }
        }
    ).encode()
    records = parse_power_response(
        payload,
        market_id="dambulla",
        source_url="https://power.example/query",
        retrieved_at=datetime(2025, 1, 10, tzinfo=UTC),
    )
    assert len(records) == 3
    assert records[0].available_date == date(2025, 1, 4)
    assert len(records[0].content_sha256) == 64


def test_health_blocks_when_no_champion_exists(tmp_path: Path) -> None:
    health = assess_model_health(
        model_root=tmp_path / "models",
        signals_path=tmp_path / "signals.parquet",
        today=date(2025, 1, 1),
    )
    assert health.status == "blocked"
    assert health.model_version is None


def test_reviewed_official_csv_requires_and_normalizes_contract(tmp_path: Path) -> None:
    path = tmp_path / "exchange.csv"
    path.write_text(
        "effective_date,signal_name,value,unit,source_url,geography_id,vintage\n"
        "2025-01-01,usd_lkr,295.5,LKR per USD,https://www.cbsl.gov.lk/,national,2025-01-02\n"
    )
    records = import_official_csv(path, source="cbsl")
    assert records[0].available_date == date(2025, 1, 2)
    assert records[0].value == 295.5


def test_health_reports_baseline_calibration_and_signal_warnings(tmp_path: Path) -> None:
    model_root = tmp_path / "models"
    version_dir = model_root / "champion-v1"
    version_dir.mkdir(parents=True)
    (model_root / "current.json").write_text('{"model_version":"champion-v1"}')
    metadata = {
        "model_version": "champion-v1",
        "trained_at": "2025-01-10T00:00:00Z",
        "training_start": "2024-01-01",
        "training_end": "2025-01-09",
        "training_cutoff": "2025-01-09",
        "observations": 1000,
        "series": 10,
        "horizons": [7, 14, 30],
        "feature_version": "test",
        "estimator": "test",
        "intended_use": "test",
        "limitations": [],
    }
    horizon = {
        "horizon_days": 7,
        "samples": 100,
        "folds": 3,
        "model_metrics": {"mae": 10},
        "baseline_metrics": {"last_value": {"mae": 8}},
        "interval_coverage_80": 0.5,
        "interval_coverage_95": 0.8,
        "interval_radius_80_lkr": 10,
        "interval_radius_95_lkr": 20,
        "beats_seasonal_baseline": True,
        "beats_strongest_baseline": False,
    }
    quality = {
        "model_version": "champion-v1",
        "evaluated_at": "2025-01-10T00:00:00Z",
        "horizons": [horizon, {**horizon, "horizon_days": 14}, {**horizon, "horizon_days": 30}],
    }
    (version_dir / "metadata.json").write_text(json.dumps(metadata))
    (version_dir / "metrics.json").write_text(json.dumps(quality))

    health = assess_model_health(
        model_root=model_root,
        signals_path=tmp_path / "missing.parquet",
        today=date(2025, 1, 20),
    )
    assert health.status == "warning"
    assert health.strongest_baseline_wins == [7, 14, 30]
    assert health.undercovered_horizons == [7, 14, 30]
