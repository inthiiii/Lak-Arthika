"""Future event labels used only during evaluation."""

from collections.abc import Sequence
from datetime import date


def future_pressure_labels(
    observation_dates: Sequence[date],
    prices: Sequence[float],
    *,
    horizon_days: int = 14,
    rise: float = 0.20,
) -> list[bool | None]:
    """Label a future rise inside a calendar window, never for model input."""

    if len(observation_dates) != len(prices):
        raise ValueError("Dates and prices must have the same length.")

    labels: list[bool | None] = []
    for index, current in enumerate(prices):
        future = [
            value
            for future_date, value in zip(
                observation_dates[index + 1 :], prices[index + 1 :], strict=True
            )
            if 0 < (future_date - observation_dates[index]).days <= horizon_days
        ]
        labels.append(None if not future else max(future) >= current * (1 + rise))
    return labels
