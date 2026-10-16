# Forecasting engine v1

LakArthika v1 produces direct 7, 14 and 30-day experimental forecasts for each sufficiently
complete market–commodity series. It is a decision-support experiment, not an official
government forecast or automated procurement recommendation.

## Data and leakage boundary

The training view is the geocoded, validated `price_history` DuckDB relation. Each feature
row contains the current observed midpoint, price lags, rolling summaries calculated from
prior rows, calendar values, and stable market/commodity codes. Targets are matched on the
exact future calendar date. Expanding-window folds require every training target date to be
on or before the fold cutoff; validation origins are strictly later.

## Models and evaluation

One global `HistGradientBoostingRegressor` is fitted per horizon to predict change from the
latest known price; adding the predicted residual back to that price gives the level forecast.
This residual formulation gives persistence a strong inductive bias. It is compared out of time
with last-value persistence, a seven-observation moving average, and horizon-matched seasonal
naive forecasts. Reports include MAE, RMSE, WAPE, sMAPE, MASE, direction accuracy, fold counts,
sample counts and empirical interval coverage. Symmetric 80% and 95% intervals use absolute
out-of-fold residual quantiles. Earlier out-of-fold residuals calibrate the interval while a
later holdout segment measures coverage, preventing a tautological same-sample coverage score.

The current local run uses 73,075 observations across 265 series from 2024-12-31 through
2026-10-07. It beat the seasonal-naive MAE at all three horizons, but did not beat the simpler
last-value baseline. That result is exposed rather than hidden and makes external signals and
stronger temporal models the next research priority.

## Artifact contract

Each immutable `models/forecasting/<version>/` bundle contains the serialized estimators,
metadata, feature schema and category mappings, forecasts, evaluation metrics and a generated
model card. `models/forecasting/current.json` is the only serving pointer. Generated artifacts
are ignored by Git; environments must train or retrieve a reviewed artifact before serving.

## Known limitations

- HARTI availability, gaps, extraction errors and extreme prices propagate into the model.
- Price/calendar-only features cannot explain weather, fuel, exchange-rate or supply shocks.
- Category codes are simple deterministic numeric encodings in v1.
- Empirical intervals describe historical residuals and are not guarantees.
- The isolated 2026 observation means the effective continuous history is principally 2025.
