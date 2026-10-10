```markdown
# ADR 0001: Geospatial stack

- Status: Accepted
- Date: 2026-10-10

## Context

LakArthika needs to visualize commodity prices, forecast uncertainty,
market relationships and economic pressure across Sri Lanka.

The project begins as a local analytical application but should support
a production web interface later.

## Decision

The geospatial stack will evolve in stages.

### Prototype

- Sri Lankan district boundaries in GeoJSON
- Plotly choropleth maps
- Streamlit interface
- Geographic files validated before use

### Production

- MapLibre GL JS for the interactive browser map
- FastAPI endpoints returning GeoJSON
- PostgreSQL with PostGIS for spatial queries
- Precomputed map layers for frequently requested views

## Initial map layers

- District boundaries
- Major wholesale markets
- Current commodity prices
- Forecast price movement
- Price-spike probability
- Forecast uncertainty
- Data freshness
- Market relationship or propagation edges

## Rationale

This stack is open, avoids dependence on a proprietary map provider
and supports both a rapid prototype and a scalable production product.

## Consequences

- Geographic identifiers must be standardized early.
- Boundary sources and licenses must be documented.
- Predictions must not imply precision below the source data's
  geographic resolution.
- Maps must remain usable for color-vision deficiencies.
```
