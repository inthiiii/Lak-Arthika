"""Operational and statistical model-health assessment."""

from datetime import UTC, date, datetime
from pathlib import Path

from lak_arthika.forecasting.artifacts import load_metadata, load_quality
from lak_arthika.models.signals import ModelHealth, SignalFreshness
from lak_arthika.storage.signals import load_signals

STALE_AFTER_DAYS = {"nasa_power": 10, "cbsl": 7, "ceypetco": 45}


def assess_model_health(
    *, model_root: Path, signals_path: Path, today: date | None = None
) -> ModelHealth:
    """Combine model performance, calibration and source freshness."""

    checked_at = datetime.now(UTC)
    current_date = today or checked_at.date()
    try:
        metadata = load_metadata(model_root)
        quality = load_quality(model_root)
    except FileNotFoundError:
        return ModelHealth(
            status="blocked",
            model_version=None,
            checked_at=checked_at,
            training_cutoff=None,
            training_data_age_days=None,
            strongest_baseline_wins=[],
            undercovered_horizons=[],
            signals=[],
            messages=["No promoted model artifact is available."],
        )

    records = load_signals(signals_path)
    freshness: list[SignalFreshness] = []
    for source, threshold in STALE_AFTER_DAYS.items():
        source_records = [record for record in records if record.source == source]
        latest = max((record.effective_date for record in source_records), default=None)
        age = (current_date - latest).days if latest else None
        freshness.append(
            SignalFreshness(
                source=source,
                latest_effective_date=latest,
                observation_count=len(source_records),
                age_days=age,
                stale=age is None or age > threshold,
            )
        )

    strongest_baseline_wins = [
        int(item.horizon_days) for item in quality.horizons if not item.beats_strongest_baseline
    ]
    undercovered = [
        int(item.horizon_days) for item in quality.horizons if item.interval_coverage_80 < 0.7
    ]
    messages: list[str] = []
    if strongest_baseline_wins:
        messages.append(
            "The strongest baseline still beats the model at horizons: "
            + ", ".join(f"{value}d" for value in strongest_baseline_wins)
            + "."
        )
    if undercovered:
        messages.append(
            "Nominal 80% intervals under-cover on the later holdout at horizons: "
            + ", ".join(f"{value}d" for value in undercovered)
            + "."
        )
    stale_sources = [item.source for item in freshness if item.stale]
    if stale_sources:
        messages.append("Stale or unavailable signals: " + ", ".join(stale_sources) + ".")
    training_age = (current_date - metadata.training_cutoff).days
    if training_age > 14:
        messages.append(f"Training data is {training_age} days old.")

    return ModelHealth(
        status="warning" if messages else "healthy",
        model_version=metadata.model_version,
        checked_at=checked_at,
        training_cutoff=metadata.training_cutoff,
        training_data_age_days=training_age,
        strongest_baseline_wins=strongest_baseline_wins,
        undercovered_horizons=undercovered,
        signals=freshness,
        messages=messages,
    )
