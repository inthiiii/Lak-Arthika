"""Tests for the leakage-safe economic-pressure warning engine."""

import json
from datetime import date, timedelta
from pathlib import Path

import polars as pl
from fastapi.testclient import TestClient

from lak_arthika.api import create_app
from lak_arthika.models.stress import EconomicAlert, StressComponents, StressSignal
from lak_arthika.stress.alerts import derive_alerts
from lak_arthika.stress.backtest import evaluate_signals
from lak_arthika.stress.features import build_price_features, robust_z_score
from lak_arthika.stress.labels import future_pressure_labels
from lak_arthika.stress.scoring import composite_score, severity_for
from lak_arthika.stress.spatial import MarketNode, haversine_km, neighbours


def signal(day: int, score: float) -> StressSignal:
    return StressSignal(
        market_id="dambulla",
        market_name="Dambulla",
        district="Matale",
        province="Central",
        latitude=7.8742,
        longitude=80.6511,
        commodity="Tomato",
        observation_date=date(2025, 1, 1) + timedelta(days=day),
        price_midpoint_lkr=300,
        score=score,
        severity=severity_for(score),
        confidence=0.8,
        components=StressComponents(
            anomaly=score, momentum=score, forecast_surprise=score, spatial_pressure=score
        ),
        evidence_observations=30,
    )


def test_robust_features_do_not_read_future_values() -> None:
    past = [100.0 + index for index in range(35)]
    original = build_price_features(past[:30])
    changed_future = [*past[:30], 99_999]
    assert original == build_price_features(changed_future[:-1])
    assert robust_z_score(120, [100, 101, 99, 102, 98, 100]) > 0


def test_future_labels_are_not_available_at_series_end() -> None:
    labels = future_pressure_labels(
        [date(2025, 1, 1), date(2025, 1, 8), date(2025, 1, 12)],
        [100, 105, 125],
    )
    assert labels[0] is True
    assert labels[-1] is None


def test_score_and_severity_are_transparent() -> None:
    components = StressComponents(
        anomaly=100, momentum=80, forecast_surprise=60, spatial_pressure=40
    )
    assert composite_score(components) == 75
    assert severity_for(75) == "warning"


def test_market_graph_uses_distance_and_correlation() -> None:
    dambulla = MarketNode("dambulla", 7.8742, 80.6511)
    kandy = MarketNode("kandy", 7.2906, 80.6337)
    assert 50 < haversine_km(dambulla, kandy) < 100
    assert neighbours([dambulla, kandy], correlations={("dambulla", "kandy"): 0.7})["dambulla"]
    assert not neighbours([dambulla, kandy], correlations={("dambulla", "kandy"): 0.1})["dambulla"]


def test_alert_requires_persistence_and_resolves_after_three_calm_observations() -> None:
    alerts = derive_alerts(
        [signal(0, 55), signal(1, 72), signal(2, 60), signal(3, 30), signal(4, 35), signal(5, 20)]
    )
    assert len(alerts) == 1
    assert alerts[0].status == "resolved"
    assert alerts[0].opened_at == date(2025, 1, 1)
    assert alerts[0].resolved_at == date(2025, 1, 6)


def test_backtest_keeps_calibration_and_final_test_periods_separate() -> None:
    signals = [signal(day, 80 if day % 2 else 20) for day in range(10)]
    labels = {
        (item.market_id, item.commodity, item.observation_date): (item.score >= 50, 4)
        for item in signals
    }
    report = evaluate_signals(signals, labels)
    assert report.train_end < report.calibration_end < report.test_start
    assert report.test_end == date(2025, 1, 10)
    assert report.f1 == 1


def test_stress_api_serves_current_alerts_methodology_and_backtest(tmp_path: Path) -> None:
    signals_path = tmp_path / "stress.parquet"
    alerts_path = tmp_path / "alerts.json"
    report_path = tmp_path / "backtest.json"
    rows = [signal(0, 52), signal(1, 75)]
    pl.DataFrame(
        [
            {
                **item.model_dump(mode="json", exclude={"components"}),
                **{
                    f"component_{key}": value for key, value in item.components.model_dump().items()
                },
            }
            for item in rows
        ]
    ).write_parquet(signals_path)
    alert = EconomicAlert(
        alert_id="alert-one",
        market_id="dambulla",
        market_name="Dambulla",
        commodity="Tomato",
        status="active",
        severity="warning",
        opened_at=date(2025, 1, 1),
        last_observed_at=date(2025, 1, 2),
        peak_score=75,
        latest_score=75,
        observation_count=2,
        summary="Persistent Tomato price pressure at Dambulla.",
    )
    alerts_path.write_text(json.dumps([alert.model_dump(mode="json")]))
    report_path.write_text(
        json.dumps(
            {
                "methodology_version": "economic-stress-v1",
                "evaluated_at": "2025-01-03T00:00:00Z",
                "train_end": "2024-08-01",
                "calibration_end": "2024-10-01",
                "test_start": "2024-10-02",
                "test_end": "2025-01-01",
                "selected_threshold": 50,
                "samples": 100,
                "positive_events": 10,
                "precision": 0.5,
                "recall": 0.6,
                "f1": 0.55,
                "pr_auc": 0.57,
                "false_alert_rate": 0.08,
                "median_lead_days": 5,
            }
        )
    )
    client = TestClient(
        create_app(
            stress_signals_path=signals_path,
            stress_alerts_path=alerts_path,
            stress_report_path=report_path,
        )
    )

    current = client.get("/v1/stress/current?commodity=Tomato")
    assert current.status_code == 200
    assert current.json()[0]["score"] == 75
    assert client.get("/v1/alerts?status=active").json()[0]["alert_id"] == "alert-one"
    assert client.get("/v1/stress/methodology").json()["component_weights"]["anomaly"] == 0.35
    assert client.get("/v1/stress/backtest").json()["f1"] == 0.55


def test_stress_api_fails_safely_without_artifacts(tmp_path: Path) -> None:
    client = TestClient(create_app(stress_signals_path=tmp_path / "missing.parquet"))
    response = client.get("/v1/stress/current")
    assert response.status_code == 503
    assert "stress build" in response.json()["detail"]
