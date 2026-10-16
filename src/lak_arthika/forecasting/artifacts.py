"""Read versioned forecast artifacts for serving."""

import json
from pathlib import Path
from typing import Any

from lak_arthika.models.forecast import ForecastQuality, ForecastRecord, ModelMetadata


def current_version(model_root: Path) -> str:
    """Resolve the atomically promoted model version."""

    pointer = model_root / "current.json"
    if not pointer.exists():
        raise FileNotFoundError(pointer)
    return str(json.loads(pointer.read_text())["model_version"])


def _load_json(model_root: Path, filename: str) -> Any:
    version = current_version(model_root)
    path = model_root / version / filename
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text())


def load_forecasts(model_root: Path) -> list[ForecastRecord]:
    return [
        ForecastRecord.model_validate(item) for item in _load_json(model_root, "forecasts.json")
    ]


def load_quality(model_root: Path) -> ForecastQuality:
    return ForecastQuality.model_validate(_load_json(model_root, "metrics.json"))


def load_metadata(model_root: Path) -> ModelMetadata:
    return ModelMetadata.model_validate(_load_json(model_root, "metadata.json"))
