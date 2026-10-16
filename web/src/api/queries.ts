import { useQuery } from '@tanstack/react-query'
import { apiGet } from './client'
import type {
  Catalog,
  ForecastQuality,
  ForecastRecord,
  MarketPricePoint,
  PriceHistoryRecord,
  QualityStatus,
} from './types'

export function useCatalog() {
  return useQuery({
    queryKey: ['catalog'],
    queryFn: ({ signal }) => apiGet<Catalog>('/v1/catalog', undefined, signal),
    staleTime: 5 * 60 * 1000,
  })
}

export function useQualityStatus() {
  return useQuery({
    queryKey: ['data-quality'],
    queryFn: ({ signal }) => apiGet<QualityStatus>('/v1/data-quality/status', undefined, signal),
    staleTime: 60 * 1000,
  })
}

export function useMapPrices(commodity: string, date: string) {
  return useQuery({
    queryKey: ['map-prices', commodity, date],
    queryFn: ({ signal }) =>
      apiGet<MarketPricePoint[]>('/v1/map/prices', { commodity, date }, signal),
    enabled: Boolean(commodity),
    staleTime: 60 * 1000,
  })
}

export function useMarketHistory(
  marketId: string | null,
  commodity: string,
  startDate?: string,
  endDate?: string,
) {
  return useQuery({
    queryKey: ['market-history', marketId, commodity, startDate, endDate],
    queryFn: ({ signal }) =>
      apiGet<PriceHistoryRecord[]>(
        `/v1/markets/${marketId}/prices`,
        { commodity, start_date: startDate, end_date: endDate },
        signal,
      ),
    enabled: Boolean(marketId && commodity),
    staleTime: 60 * 1000,
    select: (rows) => [...rows].reverse(),
  })
}

export function useForecasts(marketId: string | null, commodity: string) {
  return useQuery({
    queryKey: ['forecasts', marketId, commodity],
    queryFn: ({ signal }) =>
      apiGet<ForecastRecord[]>(
        '/v1/forecasts',
        { market_id: marketId ?? undefined, commodity },
        signal,
      ),
    enabled: Boolean(marketId && commodity),
    staleTime: 10 * 60 * 1000,
    retry: false,
  })
}

export function useForecastQuality() {
  return useQuery({
    queryKey: ['forecast-quality'],
    queryFn: ({ signal }) =>
      apiGet<ForecastQuality>('/v1/forecasts/quality', undefined, signal),
    staleTime: 10 * 60 * 1000,
    retry: false,
  })
}
