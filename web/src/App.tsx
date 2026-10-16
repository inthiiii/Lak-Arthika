import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { format, parseISO, subDays } from 'date-fns'
import { DashboardHeader } from './components/DashboardHeader'
import { FilterPanel } from './components/FilterPanel'
import { PriceSummary } from './components/PriceSummary'
import { QualityBanner } from './components/QualityBanner'
import { ModelHealthPanel } from './components/ModelHealthPanel'
import {
  useCatalog,
  useForecastQuality,
  useForecasts,
  useMapPrices,
  useMarketHistory,
  useModelHealth,
  useQualityStatus,
} from './api/queries'
import { useDashboardFilters } from './hooks/useDashboardFilters'
import type { MarketPricePoint } from './api/types'
import './App.css'

const MarketMap = lazy(() =>
  import('./components/MarketMap').then((module) => ({ default: module.MarketMap })),
)
const MarketPanel = lazy(() =>
  import('./components/MarketPanel').then((module) => ({ default: module.MarketPanel })),
)

function App() {
  const catalog = useCatalog()
  const quality = useQualityStatus()
  const { filters, updateFilters, resetFilters } = useDashboardFilters()
  const [selectedMarketId, setSelectedMarketId] = useState<string | null>(null)

  const defaultCommodity = catalog.data?.commodities.includes('Tomato')
    ? 'Tomato'
    : (catalog.data?.commodities[0] ?? '')
  const commodity = filters.commodity || defaultCommodity
  const selectedDate = filters.date || catalog.data?.maximum_date || ''

  useEffect(() => {
    if (!filters.commodity && defaultCommodity) {
      updateFilters({ commodity: defaultCommodity }, true)
    }
    if (!filters.date && catalog.data?.maximum_date) {
      updateFilters({ date: catalog.data.maximum_date }, true)
    }
  }, [catalog.data, defaultCommodity, filters.commodity, filters.date, updateFilters])

  const prices = useMapPrices(commodity, selectedDate)
  const filteredPoints = useMemo(() => {
    return (prices.data ?? []).filter((point) => {
      const change = point.change_percentage ?? 0
      const directionMatches =
        filters.direction === 'all' ||
        (filters.direction === 'rising' && change > 2) ||
        (filters.direction === 'falling' && change < -2) ||
        (filters.direction === 'stable' && Math.abs(change) <= 2)
      return (
        (!filters.province || point.province === filters.province) &&
        (!filters.district || point.district === filters.district) &&
        (!filters.market || point.market_id === filters.market) &&
        directionMatches
      )
    })
  }, [prices.data, filters])

  const effectiveSelectedMarketId = filteredPoints.some(
    (point) => point.market_id === selectedMarketId,
  )
    ? selectedMarketId
    : (filteredPoints[0]?.market_id ?? null)
  const selectedPoint: MarketPricePoint | undefined = filteredPoints.find(
    (point) => point.market_id === effectiveSelectedMarketId,
  )
  const historyStart = selectedDate
    ? format(subDays(parseISO(selectedDate), 365), 'yyyy-MM-dd')
    : undefined
  const history = useMarketHistory(
    effectiveSelectedMarketId,
    commodity,
    historyStart,
    selectedDate || undefined,
  )
  const forecasts = useForecasts(effectiveSelectedMarketId, commodity)
  const forecastQuality = useForecastQuality()
  const modelHealth = useModelHealth()

  const loading = catalog.isLoading || prices.isLoading
  const error = catalog.error ?? prices.error

  return (
    <div className="app-shell">
      <DashboardHeader latestDate={catalog.data?.maximum_date} />
      <main>
        <section className="hero" aria-labelledby="page-title">
          <div>
            <p className="eyebrow">Sri Lanka market intelligence</p>
            <h1 id="page-title">See the country’s food economy move.</h1>
          </div>
          <p className="hero-copy">
            Explore official wholesale price signals across key markets, compare movement,
            and follow the evidence behind every number.
          </p>
        </section>

        <QualityBanner quality={quality.data} isLoading={quality.isLoading} />
        <ModelHealthPanel health={modelHealth.data} isLoading={modelHealth.isLoading} />
        <FilterPanel
          catalog={catalog.data}
          filters={{ ...filters, commodity, date: selectedDate }}
          points={prices.data ?? []}
          onChange={updateFilters}
          onReset={resetFilters}
        />

        {error ? (
          <section className="state-card state-card--error" role="alert">
            <span className="state-icon">!</span>
            <div>
              <h2>We could not load the market data</h2>
              <p>{error.message} Check that the LakArthika API is running on port 8000.</p>
            </div>
          </section>
        ) : loading ? (
          <section className="dashboard-skeleton" aria-label="Loading market dashboard">
            <div />
            <div />
            <div />
          </section>
        ) : (
          <>
            <PriceSummary points={filteredPoints} selectedDate={selectedDate} />
            <Suspense fallback={<section className="dashboard-skeleton"><div /><div /><div /></section>}>
              <section className="workspace-grid" aria-label="Market map and selected market">
                <MarketMap
                  points={filteredPoints}
                  selectedMarketId={effectiveSelectedMarketId}
                  onSelect={setSelectedMarketId}
                />
                <MarketPanel
                  point={selectedPoint}
                  history={history.data ?? []}
                  isLoading={history.isLoading}
                  forecasts={forecasts.data ?? []}
                  forecastQuality={forecastQuality.data}
                  forecastUnavailable={forecasts.isError || forecastQuality.isError}
                />
              </section>
            </Suspense>
          </>
        )}

        <section className="method-note">
          <span className="method-number">01</span>
          <div>
            <h2>Read the signal, not a promise.</h2>
            <p>
              LakArthika reports historical HARTI wholesale prices and clearly labelled
              experimental forecasts. These are decision-support signals—not retail prices,
              guarantees, or official government forecasts. Evidence remains linked.
            </p>
          </div>
        </section>
      </main>
      <footer>
        <span>LakArthika · Experimental public-interest infrastructure</span>
        <span>Built from official HARTI daily bulletins</span>
      </footer>
    </div>
  )
}

export default App
