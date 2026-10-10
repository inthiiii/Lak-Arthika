```markdown
# LakArthika

LakArthika is an experimental, continuously learning digital twin for
Sri Lanka's essential economy.

It is designed to:

- forecast essential commodity prices
- detect emerging price pressure
- model relationships between commodities and markets
- provide uncertainty-aware scenario simulations
- support households, policymakers and businesses
- communicate results through APIs, dashboards and maps

## Current status

Phase 0: project and architecture foundation.

## Requirements

- macOS or Linux
- Python 3.12
- uv
- Git

## Installation

```bash
uv sync --all-groups
cp .env.example .env
uv run pre-commit install
```

## Run the API

```bash
uv run uvicorn lak_arthika.api:app --reload
```

Open:

- API documentation: http://127.0.0.1:8000/docs
- Health endpoint: http://127.0.0.1:8000/health

## Run the checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Or:

```bash
make check
```

## Command-line interface

```bash
uv run lak-arthika info
```

## Project principles

- Evidence before complexity
- Reproducible data lineage
- Honest temporal evaluation
- Visible uncertainty
- Safe failure behaviour
- Clear separation of forecasts and causal claims

## Disclaimer

LakArthika is an experimental research and decision-support platform.
Its forecasts and simulations must not be treated as guaranteed
economic outcomes or automatic policy recommendations.
```
