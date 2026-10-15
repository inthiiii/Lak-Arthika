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

export type Direction = 'all' | 'rising' | 'stable' | 'falling'

export interface DashboardFilters {
  commodity: string
  date: string
  province: string
  district: string
  market: string
  direction: Direction
}
