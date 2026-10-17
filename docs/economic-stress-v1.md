# Economic Stress Engine v1

LakArthika's economic-stress engine is an experimental early-warning system for unusual
wholesale food-price pressure. It is not a shortage prediction, causal model, or automatic
policy recommendation.

## Signal contract

Every market/commodity/date signal publishes a 0–100 score, a separate 0–1 confidence
value, a severity band, data freshness, evidence count, and four auditable components:

| Component | Weight | Evidence |
| --- | ---: | --- |
| Robust anomaly | 35% | Current price against trailing 30-observation median/MAD |
| Momentum | 25% | Change against the seventh prior observation |
| Expected-price surprise | 20% | Difference from the trailing 14-observation median |
| Spatial pressure | 20% | Distance-weighted anomaly in correlated nearby markets |

Normal is below 50, watch begins at 50, warning at 70, and critical at 85. Confidence is
not folded into severity: it reports historical depth and connected-neighbour coverage.

## Leakage controls

- Features at date `t` use values available at or before `t`.
- Market links require at most 175 km distance and correlation of at least 0.35.
- Correlations are estimated only from the first 60% of available dates.
- The evaluation label—20% price growth within the following 14 calendar days—is never a
  model input.
- Threshold selection uses the middle 20% of dates; final metrics use the last 20%.

## Alert lifecycle

An alert opens after two consecutive observations at or above watch. One alert represents
the full market/commodity episode. It resolves after three observations below 40 and cannot
reopen for seven days. This reduces notification noise without concealing the underlying
daily score.

## Operations

```bash
uv run lak-arthika stress build
uv run lak-arthika stress status
```

Generated Parquet/JSON files remain under `data/processed/stress/` and are intentionally
ignored by Git. Rebuild them after the historical HARTI analytics store is refreshed.

## Known limitations

- HARTI publication gaps reduce timing precision and confidence.
- The v1 expected-price component uses a trailing seasonal expectation rather than a
  historical archive of point-in-time model forecasts.
- Correlation describes co-movement, not supply-chain causality.
- Backtest results can degrade under changing inflation, policy, weather, or market regimes.
- Wholesale price pressure does not directly represent retail affordability or availability.
