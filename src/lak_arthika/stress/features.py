"""Leakage-safe robust features built only from observations available at scoring time."""

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median, pstdev


@dataclass(frozen=True)
class PriceFeatures:
    """Raw, interpretable pressure features before normalization."""

    robust_z: float
    momentum_7d: float
    volatility: float
    forecast_surprise: float
    evidence_observations: int


def safe_change(current: float, previous: float | None) -> float:
    """Return a safe fractional change."""

    if previous is None or previous <= 0:
        return 0.0
    return (current - previous) / previous


def robust_z_score(current: float, history: Sequence[float]) -> float:
    """Return a one-sided median/MAD z-score resistant to price spikes."""

    if len(history) < 5:
        return 0.0
    center = median(history)
    mad = median(abs(value - center) for value in history)
    if mad == 0:
        return 0.0 if current <= center else min((current - center) / max(center * 0.05, 1), 8)
    return max(0.0, 0.6745 * (current - center) / mad)


def build_price_features(prices_through_today: Sequence[float]) -> PriceFeatures:
    """Build features without reading any value after the current observation."""

    if not prices_through_today:
        raise ValueError("At least one price is required.")
    current = float(prices_through_today[-1])
    prior = [float(value) for value in prices_through_today[:-1]]
    baseline = prior[-30:]
    lag_7 = prior[-7] if len(prior) >= 7 else (prior[0] if prior else None)
    seasonal_expectation = median(prior[-14:]) if prior else current
    changes = [safe_change(b, a) for a, b in zip(baseline, baseline[1:], strict=False)]
    return PriceFeatures(
        robust_z=robust_z_score(current, baseline),
        momentum_7d=safe_change(current, lag_7),
        volatility=pstdev(changes) if len(changes) > 1 else 0.0,
        forecast_surprise=safe_change(current, seasonal_expectation),
        evidence_observations=len(prices_through_today),
    )
