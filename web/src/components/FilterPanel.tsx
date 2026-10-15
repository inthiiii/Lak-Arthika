import type { Catalog, DashboardFilters, MarketPricePoint } from '../api/types'

interface Props {
  catalog?: Catalog
  filters: DashboardFilters
  points: MarketPricePoint[]
  onChange: (changes: Partial<DashboardFilters>) => void
  onReset: () => void
}

export function FilterPanel({ catalog, filters, points, onChange, onReset }: Props) {
  const provinces = [...new Set(points.map((point) => point.province))].sort()
  const districts = [...new Set(points
    .filter((point) => !filters.province || point.province === filters.province)
    .map((point) => point.district))].sort()
  const markets = points.filter((point) =>
    (!filters.province || point.province === filters.province) &&
    (!filters.district || point.district === filters.district))

  return (
    <section className="filter-panel" aria-label="Dashboard filters">
      <div className="filter-heading">
        <span>Explore the evidence</span>
        <button type="button" onClick={onReset}>Reset filters</button>
      </div>
      <div className="filter-grid">
        <label>
          Commodity
          <select value={filters.commodity} onChange={(event) => onChange({ commodity: event.target.value, market: '' })}>
            {(catalog?.commodities ?? []).map((commodity) => <option key={commodity}>{commodity}</option>)}
          </select>
        </label>
        <label>
          Date
          <input type="date" value={filters.date} min={catalog?.minimum_date ?? undefined} max={catalog?.maximum_date ?? undefined}
            onChange={(event) => onChange({ date: event.target.value })} />
        </label>
        <label>
          Province
          <select value={filters.province} onChange={(event) => onChange({ province: event.target.value, district: '', market: '' })}>
            <option value="">All provinces</option>
            {provinces.map((province) => <option key={province}>{province}</option>)}
          </select>
        </label>
        <label>
          District
          <select value={filters.district} onChange={(event) => onChange({ district: event.target.value, market: '' })}>
            <option value="">All districts</option>
            {districts.map((district) => <option key={district}>{district}</option>)}
          </select>
        </label>
        <label>
          Market
          <select value={filters.market} onChange={(event) => onChange({ market: event.target.value })}>
            <option value="">All markets</option>
            {markets.map((market) => <option key={market.market_id} value={market.market_id}>{market.market_name}</option>)}
          </select>
        </label>
        <label>
          Movement
          <select value={filters.direction} onChange={(event) => onChange({ direction: event.target.value as DashboardFilters['direction'] })}>
            <option value="all">All movement</option>
            <option value="rising">Rising</option>
            <option value="stable">Stable</option>
            <option value="falling">Falling</option>
          </select>
        </label>
      </div>
    </section>
  )
}
