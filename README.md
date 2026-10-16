# LakArthika

LakArthika is an experimental, continuously learning digital twin for Sri Lanka's
essential economy. It provides reproducible market-price ingestion, historical analytics,
APIs and geospatial foundations for future forecasting and scenario simulation.

## Current status

- Phase 0: project and architecture foundation
- Phase 1A: one official HARTI bulletin to validated API records
- Phase 1B: resumable historical data engine, quality quarantine, DuckDB analytics and
  map-ready market references
- Phase 1C: interactive Sri Lanka market-price map and public evidence dashboard
- Phase 2 / engine-v1: leakage-safe 7, 14 and 30-day forecasts, rolling backtests,
  uncertainty intervals and versioned model artifacts

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

## Historical HARTI workflow

Discover archive links without downloading documents:

```bash
uv run lak-arthika harti discover --from 2025-01-01 --to 2025-12-31
```

Resume downloads, then validate and publish them:

```bash
uv run lak-arthika harti download --from 2025-01-01 --to 2025-12-31
uv run lak-arthika harti process --from 2025-01-01 --to 2025-12-31
```

Or run the complete workflow:

```bash
uv run lak-arthika harti backfill --from 2025-01-01 --to 2025-12-31
```

If HARTI blocks automated access, preserve a manually downloaded official PDF:

```bash
uv run lak-arthika harti ingest-history-file bulletin.pdf \
  --bulletin-date 2026-10-07 \
  --source-url "https://www.harti.gov.lk/path/to/official.pdf"
```

Query the historical analytical layer:

```bash
uv run lak-arthika harti query \
  --market Dambulla \
  --commodity Carrot \
  --from 2025-01-01
```

Inspect ingestion health:

```bash
uv run lak-arthika harti status
```

## Train forecasting-engine-v1

Training uses only observations available before each target date, evaluates expanding
time windows against persistence, moving-average and seasonal baselines, then promotes a
versioned local artifact:

```bash
uv run lak-arthika forecast train --version forecast-v1
uv run lak-arthika forecast status
```

Generated model files remain outside Git under `models/forecasting/`. The API refuses to
serve forecasts until a complete version is promoted through `current.json`.

## Data architecture

```text
Official HARTI archive
        │
        ▼
Manifest ──► immutable raw PDFs (bronze)
        │
        ▼
Versioned parser ──► interim JSONL (silver candidate)
        │
        ▼
Quality gate ──failed──► quarantine log
        │ passed
        ▼
Partitioned Parquet (gold) ──► DuckDB views ──► API / map / ML
```

Generated datasets are intentionally excluded from Git. The market reference at
`data/reference/markets.csv` is version controlled because it is reviewed application
configuration.

## Run the API

```bash
uv run uvicorn lak_arthika.api:app --reload
```

Useful endpoints:

- `GET /health`
- `GET /v1/prices/latest`
- `GET /v1/prices/history`
- `GET /v1/prices/summary`
- `GET /v1/catalog`
- `GET /v1/map/prices`
- `GET /v1/markets`
- `GET /v1/markets/{market_id}/prices`
- `GET /v1/data-quality/status`
- `GET /v1/forecasts`
- `GET /v1/forecasts/quality`
- `GET /v1/models/current`
- Interactive documentation: <http://127.0.0.1:8000/docs>

## Run the public dashboard

The dashboard uses React, TypeScript, MapLibre and the FastAPI service. In a second
terminal, after starting the API, run:

```bash
cd web
corepack enable
pnpm install
cp .env.example .env.local
pnpm dev
```

Open <http://127.0.0.1:5173>. Dashboard filter choices are stored in the URL so a
specific commodity, date and region can be shared.

The frontend is a pnpm project. Do not run `npm install` or `npm init` inside `web/`;
mixing package managers can corrupt the pnpm-linked dependency tree.

Run its automated checks with:

```bash
cd web
pnpm lint
pnpm typecheck
pnpm test:run
pnpm build
pnpm exec playwright install chromium
pnpm test:e2e
```

Browser tests intercept the API and map style with deterministic fixtures, so CI does not
depend on HARTI availability, local historical data, or a third-party map-tile service.

## Run checks

```bash
make check
```

## Project principles

- Evidence before complexity
- Reproducible data lineage
- Honest temporal evaluation
- Visible uncertainty
- Safe failure behaviour
- Clear separation of forecasts and causal claims

## Disclaimer

LakArthika is an experimental research and decision-support platform. Its forecasts and
simulations must not be treated as guaranteed economic outcomes or automatic policy
recommendations.
