"""Tests for leakage safety, metrics and forecast serving."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import numpy as np
from fastapi.testclient import TestClient
from sklearn.ensemble import HistGradientBoostingRegressor

from lak_arthika.api import create_app
from lak_arthika.evaluation.backtest import expanding_window_folds
from lak_arthika.evaluation.metrics import regression_metrics
from lak_arthika.features.price_features import PriceObservation, build_supervised_rows
from lak_arthika.forecasting import trainer


def observations(days: int = 120) -> list[PriceObservation]:
    return [
        PriceObservation(
            observation_date=date(2025, 1, 1) + timedelta(days=index),
            market_id="dambulla",
            market_name="Dambulla",
            commodity="Tomato",
            category="Vegetable",
            price_midpoint_lkr=100 + index,
        )
        for index in range(days)
    ]


def test_features_never_read_future_prices() -> None:
    original = observations()
    changed = [
        *original[:-1],
        PriceObservation(**{**original[-1].__dict__, "price_midpoint_lkr": 99_999}),
    ]
    rows, mappings = build_supervised_rows(original, horizon_days=7)
    changed_rows, _ = build_supervised_rows(changed, horizon_days=7, mappings=mappings)
    row = next(item for item in rows if item.origin_date == date(2025, 3, 1))
    changed_row = next(item for item in changed_rows if item.origin_date == date(2025, 3, 1))
    assert row.values == changed_row.values
    assert row.target == changed_row.target


def test_backtest_training_targets_end_before_validation() -> None:
    rows, _ = build_supervised_rows(observations(240), horizon_days=7)
    folds = expanding_window_folds(
        rows, minimum_train_rows=20, minimum_validation_rows=10, validation_days=30
    )
    assert folds
    for fold in folds:
        assert max(rows[index].target_date for index in fold.train) <= fold.cutoff
        assert min(rows[index].origin_date for index in fold.validation) > fold.cutoff


def test_metrics_are_safe_for_zero_values() -> None:
    result = regression_metrics(np.array([0.0, 10.0]), np.array([0.0, 12.0]))
    assert result["mae"] == 1.0
    assert result["smape"] == 0.09090909090909091


def test_forecast_api_refuses_to_serve_without_promoted_artifact(tmp_path: Path) -> None:
    client = TestClient(create_app(forecast_root=tmp_path))
    assert client.get("/v1/forecasts").status_code == 503


def test_forecast_api_filters_promoted_artifacts(tmp_path: Path) -> None:
    version = "forecast-v1-test"
    version_dir = tmp_path / version
    version_dir.mkdir()
    now = datetime.now(UTC).isoformat()
    forecast = {
        "market_id": "dambulla",
        "market_name": "Dambulla",
        "commodity": "Tomato",
        "category": "Vegetable",
        "generated_at": now,
        "origin_date": "2025-12-31",
        "training_cutoff": "2025-12-31",
        "forecast_date": "2026-01-07",
        "horizon_days": 7,
        "point_forecast_lkr": 310,
        "lower_80_lkr": 290,
        "upper_80_lkr": 330,
        "lower_95_lkr": 270,
        "upper_95_lkr": 350,
        "model_version": version,
        "feature_version": "price-features-v1",
        "model_type": "test",
        "experimental": True,
    }
    (tmp_path / "current.json").write_text(json.dumps({"model_version": version}))
    (version_dir / "forecasts.json").write_text(json.dumps([forecast]))
    client = TestClient(create_app(forecast_root=tmp_path))
    response = client.get("/v1/forecasts?market_id=dambulla&commodity=Tomato&horizon_days=7")
    assert response.status_code == 200
    assert response.json()[0]["point_forecast_lkr"] == 310


def test_training_publishes_a_complete_versioned_bundle(
    tmp_path: Path, monkeypatch: object
) -> None:
    database_path = tmp_path / "analytics.duckdb"
    rows = []
    for market_index in range(6):
        for day in range(220):
            rows.append(
                (
                    date(2025, 1, 1) + timedelta(days=day),
                    f"market-{market_index}",
                    f"Market {market_index}",
                    "Tomato",
                    "Vegetable",
                    float(100 + market_index * 10 + day % 30),
                )
            )
    with duckdb.connect(str(database_path)) as connection:
        connection.execute(
            """
            CREATE TABLE price_history (
                observation_date DATE, market_id VARCHAR, market VARCHAR,
                commodity VARCHAR, category VARCHAR, price_midpoint_lkr DOUBLE
            )
            """
        )
        connection.executemany("INSERT INTO price_history VALUES (?, ?, ?, ?, ?, ?)", rows)

    monkeypatch.setattr(
        trainer,
        "_estimator",
        lambda random_state: HistGradientBoostingRegressor(max_iter=5, random_state=random_state),
    )
    model_root = tmp_path / "models"
    metadata = trainer.train_forecasting_engine(
        database_path=database_path,
        model_root=model_root,
        model_version="test-v1",
    )

    assert metadata.horizons == [7, 14, 30]
    assert json.loads((model_root / "current.json").read_text())["model_version"] == "test-v1"
    for filename in (
        "model.joblib",
        "metadata.json",
        "metrics.json",
        "forecasts.json",
        "feature_schema.json",
        "model_card.md",
    ):
        assert (model_root / "test-v1" / filename).exists()
