import type { Catalog, MarketPricePoint, PriceHistoryRecord, QualityStatus, StressSignal } from '../api/types'

export const catalogFixture: Catalog = {
  commodities: ['Tomato', 'Carrot'],
  markets: [
    {
      market_id: 'dambulla',
      market_name: 'Dambulla',
      district: 'Matale',
      province: 'Central',
      latitude: 7.8742,
      longitude: 80.6511,
      market_type: 'Wholesale',
    },
    {
      market_id: 'kandy',
      market_name: 'Kandy',
      district: 'Kandy',
      province: 'Central',
      latitude: 7.2906,
      longitude: 80.6337,
      market_type: 'Wholesale',
    },
  ],
  minimum_date: '2025-01-01',
  maximum_date: '2025-12-31',
}

export const qualityFixture: QualityStatus = {
  total_bulletins: 340,
  processed_bulletins: 340,
  quarantined_bulletins: 0,
  failed_bulletins: 0,
  pending_bulletins: 0,
  latest_error: null,
}

export const pricePointsFixture: MarketPricePoint[] = [
  {
    market_id: 'dambulla',
    market_name: 'Dambulla',
    district: 'Matale',
    province: 'Central',
    latitude: 7.8742,
    longitude: 80.6511,
    commodity: 'Tomato',
    category: 'Vegetable',
    minimum_price_lkr: 280,
    maximum_price_lkr: 320,
    midpoint_price_lkr: 300,
    previous_price_lkr: 280,
    change_percentage: 7.14,
    observation_date: '2025-12-31',
    source_url: 'https://example.test/dambulla.pdf',
  },
  {
    market_id: 'kandy',
    market_name: 'Kandy',
    district: 'Kandy',
    province: 'Central',
    latitude: 7.2906,
    longitude: 80.6337,
    commodity: 'Tomato',
    category: 'Vegetable',
    minimum_price_lkr: 230,
    maximum_price_lkr: 270,
    midpoint_price_lkr: 250,
    previous_price_lkr: 270,
    change_percentage: -7.41,
    observation_date: '2025-12-31',
    source_url: 'https://example.test/kandy.pdf',
  },
]

export const historyFixture: PriceHistoryRecord[] = [
  {
    observation_date: '2025-12-30',
    market: 'Dambulla',
    commodity: 'Tomato',
    price_min_lkr: 260,
    price_max_lkr: 300,
    price_midpoint_lkr: 280,
    moving_average_7: 275,
    moving_average_30: 265,
    source_url: 'https://example.test/previous.pdf',
  },
  {
    observation_date: '2025-12-31',
    market: 'Dambulla',
    commodity: 'Tomato',
    price_min_lkr: 280,
    price_max_lkr: 320,
    price_midpoint_lkr: 300,
    moving_average_7: 282,
    moving_average_30: 270,
    source_url: 'https://example.test/latest.pdf',
  },
]

export const stressFixture: StressSignal[] = [
  {
    market_id: 'dambulla', market_name: 'Dambulla', district: 'Matale', province: 'Central',
    latitude: 7.8742, longitude: 80.6511, commodity: 'Tomato', observation_date: '2025-12-31',
    price_midpoint_lkr: 300, score: 78, severity: 'warning', confidence: 0.9,
    components: { anomaly: 90, momentum: 80, forecast_surprise: 70, spatial_pressure: 60 },
    evidence_observations: 30, stale: false, methodology_version: 'economic-stress-v1',
  },
]
