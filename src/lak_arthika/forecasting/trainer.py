"""Train, evaluate and publish forecasting-engine-v1 artifacts."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from lak_arthika.evaluation.backtest import expanding_window_folds
from lak_arthika.evaluation.metrics import interval_coverage, regression_metrics
from lak_arthika.features.price_features import (
    FEATURE_NAMES,
    FEATURE_VERSION,
    FeatureMappings,
    FeatureRow,
    build_prediction_rows,
    build_supervised_rows,
    load_price_observations,
    matrix,
    targets,
)
from lak_arthika.forecasting.baselines import baseline_predictions
from lak_arthika.models.forecast import (
    ForecastQuality,
    ForecastRecord,
    HorizonQuality,
    ModelMetadata,
)
from lak_arthika.models.signals import PromotionDecision
from lak_arthika.signals.features import SignalIndex
from lak_arthika.storage.signals import load_signals

HORIZONS: tuple[Literal[7, 14, 30], ...] = (7, 14, 30)
MODEL_TYPE = "global-hist-gradient-boosting-direct-residual"


def _estimator(random_state: int) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        learning_rate=0.06,
        max_iter=180,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        random_state=random_state,
    )


def _select(rows: list[FeatureRow], indices: list[int]) -> list[FeatureRow]:
    return [rows[index] for index in indices]


def _quantile(values: np.ndarray[Any, Any], probability: float) -> float:
    return float(np.quantile(values, probability, method="higher"))


def _evaluate_horizon(
    rows: list[FeatureRow], horizon: Literal[7, 14, 30], *, random_state: int
) -> tuple[HorizonQuality, np.ndarray[Any, Any]]:
    folds = expanding_window_folds(rows)
    actual_parts: list[np.ndarray[Any, Any]] = []
    prediction_parts: list[np.ndarray[Any, Any]] = []
    current_parts: list[np.ndarray[Any, Any]] = []
    origin_parts: list[np.ndarray[Any, Any]] = []
    baseline_parts: dict[str, list[np.ndarray[Any, Any]]] = {
        "last_value": [],
        "moving_average_7": [],
        "seasonal_naive": [],
    }
    if not folds:
        raise ValueError(f"Insufficient temporal coverage for {horizon}-day evaluation")
    for fold in folds:
        train_rows = _select(rows, fold.train)
        validation_rows = _select(rows, fold.validation)
        model = _estimator(random_state)
        train_current = np.asarray([row.current_price_lkr for row in train_rows])
        model.fit(matrix(train_rows), targets(train_rows) - train_current)
        actual_parts.append(targets(validation_rows))
        validation_current = np.asarray([row.current_price_lkr for row in validation_rows])
        prediction_parts.append(validation_current + model.predict(matrix(validation_rows)))
        current_parts.append(validation_current)
        origin_parts.append(np.asarray([row.origin_date.toordinal() for row in validation_rows]))
        fold_baselines = baseline_predictions(validation_rows, horizon_days=horizon)
        for name, values in fold_baselines.items():
            baseline_parts[name].append(values)

    actual = np.concatenate(actual_parts)
    predicted = np.concatenate(prediction_parts)
    current = np.concatenate(current_parts)
    origin_ordinals = np.concatenate(origin_parts)
    baselines = {name: np.concatenate(parts) for name, parts in baseline_parts.items()}
    residuals = np.abs(actual - predicted)
    temporal_order = np.argsort(origin_ordinals, kind="stable")
    calibration_end = max(1, int(len(temporal_order) * 0.6))
    calibration_indices = temporal_order[:calibration_end]
    evaluation_indices = temporal_order[calibration_end:]
    if not len(evaluation_indices):
        raise ValueError(f"Insufficient interval evaluation rows for {horizon}-day horizon")
    radius_80 = _quantile(residuals[calibration_indices], 0.8)
    radius_95 = _quantile(residuals[calibration_indices], 0.95)
    baseline_metrics = {
        name: regression_metrics(actual, values, current=current)
        for name, values in baselines.items()
    }
    model_metrics = regression_metrics(
        actual, predicted, naive=baselines["seasonal_naive"], current=current
    )
    model_mae = float(model_metrics["mae"] or 0)
    strongest_baseline_mae = min(
        float(metrics["mae"] or float("inf")) for metrics in baseline_metrics.values()
    )
    quality = HorizonQuality(
        horizon_days=horizon,
        samples=len(actual),
        folds=len(folds),
        model_metrics=model_metrics,
        baseline_metrics=baseline_metrics,
        interval_coverage_80=interval_coverage(
            actual[evaluation_indices], predicted[evaluation_indices], radius_80
        ),
        interval_coverage_95=interval_coverage(
            actual[evaluation_indices], predicted[evaluation_indices], radius_95
        ),
        interval_radius_80_lkr=radius_80,
        interval_radius_95_lkr=radius_95,
        beats_seasonal_baseline=(model_mae < float(baseline_metrics["seasonal_naive"]["mae"] or 0)),
        beats_strongest_baseline=model_mae < strongest_baseline_mae,
    )
    return quality, residuals


def train_forecasting_engine(
    *,
    database_path: Path,
    model_root: Path,
    model_version: str,
    cutoff: date | None = None,
    signals_path: Path | None = None,
    force_promote: bool = False,
) -> ModelMetadata:
    """Train all direct horizons and promote a complete artifact bundle."""

    observations = load_price_observations(database_path, cutoff=cutoff)
    if not observations:
        raise ValueError("No forecasting observations are available")
    trained_at = datetime.now(UTC)
    training_cutoff = max(item.observation_date for item in observations)
    mappings: FeatureMappings | None = None
    models: dict[int, HistGradientBoostingRegressor] = {}
    qualities: list[HorizonQuality] = []
    forecast_records: list[ForecastRecord] = []
    signal_index = SignalIndex(load_signals(signals_path)) if signals_path else None

    for horizon in HORIZONS:
        rows, mappings = build_supervised_rows(
            observations,
            horizon_days=horizon,
            mappings=mappings,
            signal_index=signal_index,
        )
        quality, _ = _evaluate_horizon(rows, horizon, random_state=42 + horizon)
        qualities.append(quality)
        model = _estimator(42 + horizon)
        training_current = np.asarray([row.current_price_lkr for row in rows])
        model.fit(matrix(rows), targets(rows) - training_current)
        models[horizon] = model
        prediction_rows = build_prediction_rows(
            observations,
            horizon_days=horizon,
            mappings=mappings,
            signal_index=signal_index,
        )
        prediction_current = np.asarray([row.current_price_lkr for row in prediction_rows])
        predictions = prediction_current + model.predict(matrix(prediction_rows))
        for row, raw_prediction in zip(prediction_rows, predictions, strict=True):
            point = max(0.0, float(raw_prediction))
            lower_80 = max(0.0, point - quality.interval_radius_80_lkr)
            lower_95 = max(0.0, point - quality.interval_radius_95_lkr)
            forecast_records.append(
                ForecastRecord(
                    market_id=row.market_id,
                    market_name=row.market_name,
                    commodity=row.commodity,
                    category=row.category,
                    generated_at=trained_at,
                    origin_date=row.origin_date,
                    training_cutoff=training_cutoff,
                    forecast_date=row.target_date,
                    horizon_days=horizon,
                    point_forecast_lkr=point,
                    lower_80_lkr=lower_80,
                    upper_80_lkr=point + quality.interval_radius_80_lkr,
                    lower_95_lkr=lower_95,
                    upper_95_lkr=point + quality.interval_radius_95_lkr,
                    model_version=model_version,
                    feature_version=FEATURE_VERSION,
                    model_type=MODEL_TYPE,
                )
            )

    assert mappings is not None
    metadata = ModelMetadata(
        model_version=model_version,
        trained_at=trained_at,
        training_start=min(item.observation_date for item in observations),
        training_end=training_cutoff,
        training_cutoff=training_cutoff,
        observations=len(observations),
        series=len({(item.market_id, item.commodity) for item in observations}),
        horizons=list(HORIZONS),
        feature_version=FEATURE_VERSION,
        estimator="sklearn.ensemble.HistGradientBoostingRegressor",
        intended_use="Experimental wholesale price decision support for Sri Lankan markets.",
        limitations=[
            "Forecasts inherit gaps and reporting errors in HARTI bulletins.",
            "External signals may be missing, stale, or revised by their publishers.",
            "Intervals are empirical backtest intervals, not guarantees.",
            "Not suitable for automated trading, procurement, or policy decisions without review.",
        ],
    )
    quality_report = ForecastQuality(
        model_version=model_version, evaluated_at=trained_at, horizons=qualities
    )
    version_dir = model_root / model_version
    version_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"models": models, "mappings": asdict(mappings), "features": FEATURE_NAMES},
        version_dir / "model.joblib",
    )
    (version_dir / "metadata.json").write_text(metadata.model_dump_json(indent=2))
    (version_dir / "metrics.json").write_text(quality_report.model_dump_json(indent=2))
    (version_dir / "forecasts.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in forecast_records], indent=2)
    )
    (version_dir / "feature_schema.json").write_text(
        json.dumps(
            {
                "feature_version": FEATURE_VERSION,
                "features": FEATURE_NAMES,
                "mappings": asdict(mappings),
            },
            indent=2,
        )
    )
    (version_dir / "model_card.md").write_text(_model_card(metadata, quality_report))
    model_root.mkdir(parents=True, exist_ok=True)
    beating_horizons = [
        int(item.horizon_days) for item in qualities if item.beats_strongest_baseline
    ]
    promoted = force_promote or len(beating_horizons) == len(HORIZONS)
    decision = PromotionDecision(
        candidate_version=model_version,
        evaluated_at=trained_at,
        promoted=promoted,
        forced=force_promote,
        required_horizons=list(HORIZONS),
        horizons_beating_strongest_baseline=beating_horizons,
        reasons=(
            ["Candidate beat the strongest registered baseline at every horizon."]
            if len(beating_horizons) == len(HORIZONS)
            else [
                "Candidate did not beat the strongest baseline at every horizon; "
                "the existing champion remains active."
            ]
        ),
    )
    (version_dir / "promotion.json").write_text(decision.model_dump_json(indent=2))
    with (model_root / "experiments.jsonl").open("a") as registry:
        registry.write(decision.model_dump_json() + "\n")
    if promoted:
        (model_root / "current.json").write_text(
            json.dumps({"model_version": model_version}, indent=2)
        )
    return metadata


def _model_card(metadata: ModelMetadata, quality: ForecastQuality) -> str:
    rows = ["| Horizon | MAE (LKR) | Seasonal MAE | 80% coverage |", "|---:|---:|---:|---:|"]
    for item in quality.horizons:
        model_mae = item.model_metrics["mae"]
        seasonal_mae = item.baseline_metrics["seasonal_naive"]["mae"]
        rows.append(
            f"| {item.horizon_days}d | {model_mae:.2f} | {seasonal_mae:.2f} | "
            f"{item.interval_coverage_80:.1%} |"
        )
    return "\n".join(
        [
            f"# LakArthika {metadata.model_version}",
            "",
            "Experimental direct multi-horizon wholesale-price model.",
            "",
            *rows,
            "",
            "## Intended use",
            "",
            metadata.intended_use,
            "",
            "## Limitations",
            "",
            *[f"- {item}" for item in metadata.limitations],
            "",
            "## Promotion rule",
            "",
            "Promotion requires lower MAE than every registered baseline at all horizons.",
            "",
        ]
    )
