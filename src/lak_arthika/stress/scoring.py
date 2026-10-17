"""Transparent economic-pressure score and severity rules."""

from lak_arthika.models.stress import StressComponents, StressSeverity
from lak_arthika.stress.features import PriceFeatures

WEIGHTS = {"anomaly": 0.35, "momentum": 0.25, "forecast_surprise": 0.20, "spatial_pressure": 0.20}
THRESHOLDS = {"watch": 50.0, "warning": 70.0, "critical": 85.0}


def _bounded(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def normalize_components(features: PriceFeatures, spatial_pressure: float) -> StressComponents:
    """Map feature magnitudes to explainable bounded component scores."""

    return StressComponents(
        anomaly=_bounded(features.robust_z / 4 * 100),
        momentum=_bounded(features.momentum_7d / 0.25 * 100),
        forecast_surprise=_bounded(features.forecast_surprise / 0.20 * 100),
        spatial_pressure=_bounded(spatial_pressure),
    )


def composite_score(components: StressComponents) -> float:
    """Calculate the fixed weighted score."""

    score = (
        components.anomaly * WEIGHTS["anomaly"]
        + components.momentum * WEIGHTS["momentum"]
        + components.forecast_surprise * WEIGHTS["forecast_surprise"]
        + components.spatial_pressure * WEIGHTS["spatial_pressure"]
    )
    return round(score, 2)


def severity_for(score: float) -> StressSeverity:
    """Translate a continuous score into a public warning band."""

    if score >= THRESHOLDS["critical"]:
        return "critical"
    if score >= THRESHOLDS["warning"]:
        return "warning"
    if score >= THRESHOLDS["watch"]:
        return "watch"
    return "normal"


def confidence_for(evidence_observations: int, neighbour_count: int) -> float:
    """Keep data sufficiency separate from event severity."""

    history = min(evidence_observations / 30, 1.0)
    spatial = min(neighbour_count / 3, 1.0)
    return round(0.8 * history + 0.2 * spatial, 3)
