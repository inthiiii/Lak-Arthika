# LakArthika Product Requirements

## Mission

LakArthika is a continuously learning digital twin for Sri Lanka's
essential economy.

It forecasts economic pressure, explains how that pressure propagates
through commodities and markets, and provides carefully qualified
scenario simulations.

## Primary problem

Households, businesses and policymakers often react after essential
commodity prices have already increased.

LakArthika aims to provide earlier, measurable and uncertainty-aware
signals.

## Initial users

### Public

A household wants to understand how the cost of its essential basket
may change and what affordable alternatives exist.

### Government

A policymaker wants to identify emerging price pressure and test
possible responses before implementing them.

### Businesses

A retailer or supplier wants to improve procurement, inventory and
regional demand planning.

## V1 scope

- 10 to 15 essential commodities
- Selected major wholesale markets
- 7-day, 14-day and 30-day forecasts
- Price-spike probabilities
- Forecast intervals
- Household basket forecast
- Inventory-planning demonstration
- Fuel and exchange-rate scenario
- Geographic risk map
- Daily data-ingestion checks

## V1 exclusions

- Automatic government policy decisions
- Claims of guaranteed causal impact
- Automatic buying, selling or price setting
- Individual credit decisions
- Medical or emergency predictions
- Nationwide production deployment without review

## Success measures

- Better forecast performance than seasonal-naive baselines
- Reliable forecast-interval coverage
- Useful warning lead time
- Reproducible data lineage
- Detectable and recoverable pipeline failures
- Clear communication of uncertainty
- Accessible public experience

## Product principles

1. Evidence before model complexity.
2. Uncertainty must be visible.
3. Forecasts and causal claims must be separated.
4. Every prediction must be traceable to data and model versions.
5. The system must fail safely.
6. Public value and accessibility are first-class requirements.
