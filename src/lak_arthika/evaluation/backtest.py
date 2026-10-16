"""Leakage-safe expanding-window evaluation."""

from dataclasses import dataclass
from datetime import date, timedelta

from lak_arthika.features.price_features import FeatureRow


@dataclass(frozen=True)
class TemporalFold:
    """Indices for one expanding-window train/validation split."""

    cutoff: date
    train: list[int]
    validation: list[int]


def expanding_window_folds(
    rows: list[FeatureRow],
    *,
    count: int = 3,
    validation_days: int = 45,
    minimum_train_rows: int = 500,
    minimum_validation_rows: int = 50,
) -> list[TemporalFold]:
    """Build folds where every training target predates the validation origin."""

    dates = sorted({row.origin_date for row in rows})
    if len(dates) < 4:
        return []
    positions = [int((len(dates) - 1) * fraction) for fraction in (0.55, 0.7, 0.85)]
    cutoffs = [dates[position] for position in positions[-count:]]
    folds: list[TemporalFold] = []
    for cutoff in cutoffs:
        validation_end = cutoff + timedelta(days=validation_days)
        train = [index for index, row in enumerate(rows) if row.target_date <= cutoff]
        validation = [
            index for index, row in enumerate(rows) if cutoff < row.origin_date <= validation_end
        ]
        if len(train) >= minimum_train_rows and len(validation) >= minimum_validation_rows:
            folds.append(TemporalFold(cutoff=cutoff, train=train, validation=validation))
    return folds
