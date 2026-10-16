"""Strong, explainable baselines for direct price forecasting."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from lak_arthika.features.price_features import FEATURE_NAMES, FeatureRow

_INDEX = {name: index for index, name in enumerate(FEATURE_NAMES)}


def baseline_predictions(
    rows: list[FeatureRow],
    *,
    horizon_days: int,
) -> dict[str, NDArray[np.float64]]:
    """Predict with persistence, moving-average and seasonal-naive rules."""

    seasonal_lag = 7 if horizon_days <= 7 else 14 if horizon_days <= 14 else 28
    return {
        "last_value": np.asarray(
            [row.values[_INDEX["current_price"]] for row in rows], dtype=np.float64
        ),
        "moving_average_7": np.asarray(
            [row.values[_INDEX["rolling_mean_7"]] for row in rows], dtype=np.float64
        ),
        "seasonal_naive": np.asarray(
            [row.values[_INDEX[f"lag_{seasonal_lag}"]] for row in rows], dtype=np.float64
        ),
    }
