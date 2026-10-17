export interface MarketReference {
  market_id: string
  market_name: string
  district: string
  province: string
  latitude: number
  longitude: number
  market_type: string
}

export interface Catalog {
  commodities: string[]
  markets: MarketReference[]
  minimum_date: string | null
  maximum_date: string | null
}

export interface MarketPricePoint {
  market_id: string
  market_name: string
  district: string
  province: string
  latitude: number
  longitude: number
  commodity: string
  category: string
  minimum_price_lkr: number
  maximum_price_lkr: number
  midpoint_price_lkr: number
  previous_price_lkr: number | null
  change_percentage: number | null
  observation_date: string
  source_url: string
}

export interface PriceHistoryRecord {
  observation_date: string
  market: string
  commodity: string
  price_min_lkr: number
  price_max_lkr: number
  price_midpoint_lkr: number
  moving_average_7: number | null
  moving_average_30: number | null
  source_url: string
}

export interface QualityStatus {
  total_bulletins: number
  processed_bulletins: number
  quarantined_bulletins: number
  failed_bulletins: number
  pending_bulletins: number
  latest_error: string | null
}

export interface ForecastRecord {
  market_id: string
  market_name: string
  commodity: string
  category: string
  generated_at: string
  origin_date: string
  training_cutoff: string
  forecast_date: string
  horizon_days: 7 | 14 | 30
  point_forecast_lkr: number
  lower_80_lkr: number
  upper_80_lkr: number
  lower_95_lkr: number
  upper_95_lkr: number
  model_version: string
  feature_version: string
  model_type: string
  experimental: true
}

export interface HorizonQuality {
  horizon_days: 7 | 14 | 30
  samples: number
  folds: number
  model_metrics: Record<string, number | null>
  baseline_metrics: Record<string, Record<string, number | null>>
  interval_coverage_80: number
  interval_coverage_95: number
  interval_radius_80_lkr: number
  interval_radius_95_lkr: number
  beats_seasonal_baseline: boolean
  beats_strongest_baseline: boolean
}

export interface ForecastQuality {
  model_version: string
  evaluated_at: string
  horizons: HorizonQuality[]
}

export interface SignalFreshness {
  source: string
  latest_effective_date: string | null
  observation_count: number
  age_days: number | null
  stale: boolean
}

export interface ModelHealth {
  status: 'healthy' | 'warning' | 'blocked'
  model_version: string | null
  checked_at: string
  training_cutoff: string | null
  training_data_age_days: number | null
  strongest_baseline_wins: number[]
  undercovered_horizons: number[]
  signals: SignalFreshness[]
  messages: string[]
}

export type StressSeverity = 'normal' | 'watch' | 'warning' | 'critical'

export interface StressComponents {
  anomaly: number
  momentum: number
  forecast_surprise: number
  spatial_pressure: number
}

export interface StressSignal {
  market_id: string
  market_name: string
  district: string
  province: string
  latitude: number
  longitude: number
  commodity: string
  observation_date: string
  price_midpoint_lkr: number
  score: number
  severity: StressSeverity
  confidence: number
  components: StressComponents
  evidence_observations: number
  stale: boolean
  methodology_version: string
}

export interface EconomicAlert {
  alert_id: string
  market_id: string
  market_name: string
  commodity: string
  status: 'active' | 'resolved'
  severity: StressSeverity
  opened_at: string
  last_observed_at: string
  resolved_at: string | null
  peak_score: number
  latest_score: number
  observation_count: number
  summary: string
}

export type Direction = 'all' | 'rising' | 'stable' | 'falling'
export type MapMode = 'prices' | 'stress'

export interface DashboardFilters {
  commodity: string
  date: string
  province: string
  district: string
  market: string
  direction: Direction
  mode: MapMode
}
