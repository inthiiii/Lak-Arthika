# External signals and champion governance

Phase 2B adds weather and national economic context without weakening LakArthika's temporal
evaluation rules. Every signal has an effective date, an availability date, a retrieval time,
a content digest, a source URL and a vintage. Feature joins reject records that were not yet
available at the forecast origin.

## Reviewed sources

- NASA POWER daily point API: rainfall, two-metre mean temperature and relative humidity for
  each market coordinate. A conservative three-day publication lag is enforced. Near-real-time
  values may later be revised, so the retrieval vintage remains part of the identity.
- Central Bank of Sri Lanka: normalized reviewed imports for `usd_lkr`, with a one-day
  availability lag.
- Ceylon Petroleum Corporation: normalized reviewed imports for `auto_diesel_lkr`, effective
  on the official price-change date.

CBSL and Ceypetco data are not scraped speculatively. Their public formats can change, so a
human-reviewed normalized CSV is ingested through the versioned contract in
`data/reference/external_signal_template.csv`. This is safer than silently mapping a changed
table to the wrong economic variable.

## Feature contract

The v2 feature schema adds trailing 7/30-day rainfall, 7-day temperature and humidity,
national diesel and USD/LKR levels, source-age features, weekend and month-end indicators.
Missing values are explicit: numeric levels use zero and age uses a 999-day sentinel. This
lets the estimator learn missingness while preserving a stable matrix.

## Champion–challenger gate

Every candidate is fully trained and written to its immutable version directory. Promotion is
a separate decision: model MAE must be lower than every registered baseline at all 7, 14 and
30-day horizons. The decision is stored in `promotion.json` and appended to the experiment
registry. `current.json` changes only when the gate passes or an operator explicitly supplies
`--force-promote` after review.

The `external-signals-v1` experiment improved MAE relative to forecasting-engine-v1, but did
not beat last-value persistence at any horizon. It was therefore correctly rejected and the
existing champion remained active. This is the intended production behavior.

| Horizon | External model MAE | Last-value MAE | Seasonal MAE | Later 80% coverage |
|---:|---:|---:|---:|---:|
| 7 days | 46.88 | 41.80 | 62.18 | 46.2% |
| 14 days | 60.76 | 59.20 | 86.49 | 55.6% |
| 30 days | 102.06 | 90.43 | 126.34 | 56.1% |

These values come from the local 73,075-observation experiment. Generated artifacts and data
remain outside Git, so another environment must reproduce the run before relying on them.

## Monitoring

`lak-arthika forecast health` and `GET /v1/models/health` combine:

- strongest-baseline comparison;
- later-holdout interval coverage;
- training-data age;
- NASA POWER, CBSL and Ceypetco freshness.

The public dashboard shows the same warnings. Operational status does not imply forecast
accuracy, and a healthy pipeline cannot override a failed statistical promotion gate.
