"""Numerically safe forecast metrics."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def regression_metrics(
    actual: NDArray[np.float64],
    predicted: NDArray[np.float64],
    *,
    naive: NDArray[np.float64] | None = None,
    current: NDArray[np.float64] | None = None,
) -> dict[str, float | None]:
    """Return scale-aware point and direction metrics."""

    if len(actual) == 0 or len(actual) != len(predicted):
        raise ValueError("actual and predicted must be non-empty and equally sized")
    errors = actual - predicted
    absolute = np.abs(errors)
    denominator = np.abs(actual) + np.abs(predicted)
    smape_terms = np.divide(
        2 * absolute,
        denominator,
        out=np.zeros_like(absolute),
        where=denominator != 0,
    )
    result: dict[str, float | None] = {
        "mae": float(np.mean(absolute)),
        "rmse": float(np.sqrt(np.mean(np.square(errors)))),
        "wape": float(np.sum(absolute) / np.sum(np.abs(actual)))
        if np.sum(np.abs(actual))
        else None,
        "smape": float(np.mean(smape_terms)),
        "mase": None,
        "direction_accuracy": None,
    }
    if naive is not None:
        scale = float(np.mean(np.abs(actual - naive)))
        result["mase"] = float(np.mean(absolute) / scale) if scale else None
    if current is not None:
        actual_direction = np.sign(actual - current)
        predicted_direction = np.sign(predicted - current)
        result["direction_accuracy"] = float(np.mean(actual_direction == predicted_direction))
    return result


def interval_coverage(
    actual: NDArray[np.float64],
    predicted: NDArray[np.float64],
    radius: float,
) -> float:
    """Return the share of observations inside a symmetric interval."""

    return float(np.mean((actual >= predicted - radius) & (actual <= predicted + radius)))
