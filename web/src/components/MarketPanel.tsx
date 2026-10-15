import {
  Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import type { MarketPricePoint, PriceHistoryRecord } from '../api/types'
import { formatDate, formatLkr, movementLabel } from '../utils/format'

interface Props {
  point?: MarketPricePoint
  history: PriceHistoryRecord[]
  isLoading: boolean
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: PriceHistoryRecord }> }) {
  if (!active || !payload?.[0]) return null
  const row = payload[0].payload
  return (
    <div className="chart-tooltip">
      <strong>{formatDate(row.observation_date)}</strong>
      <span>Range {formatLkr(row.price_min_lkr)}–{formatLkr(row.price_max_lkr)}</span>
      <span>Midpoint {formatLkr(row.price_midpoint_lkr)}</span>
    </div>
  )
}

export function MarketPanel({ point, history, isLoading }: Props) {
  if (!point) {
    return <article className="market-panel market-panel--empty"><span>02</span><h2>Select a market</h2><p>Choose a point on the map to inspect its price history.</p></article>
  }
  const movement = movementLabel(point.change_percentage)
  const meanPrice = history.length
    ? history.reduce((sum, row) => sum + row.price_midpoint_lkr, 0) / history.length
    : 0
  const volatility = history.length
    ? Math.sqrt(
        history.reduce(
          (sum, row) => sum + Math.pow(row.price_midpoint_lkr - meanPrice, 2),
          0,
        ) / history.length,
      )
    : 0

  return (
    <article className="market-panel">
      <div className="market-panel__topline"><span className="section-index">Market / 02</span><span className={`movement-chip movement-chip--${movement.tone}`}>{movement.arrow} {movement.label}</span></div>
      <h2>{point.market_name}</h2>
      <p className="market-location">{point.district} District · {point.province} Province</p>
      <div className="headline-price">
        <span>Midpoint price</span>
        <strong>{formatLkr(point.midpoint_price_lkr)}</strong>
        <small>per kilogram · observed {formatDate(point.observation_date)}</small>
      </div>
      <div className="market-metrics">
        <div><span>Published range</span><strong>{formatLkr(point.minimum_price_lkr)}–{formatLkr(point.maximum_price_lkr)}</strong></div>
        <div><span>Previous signal</span><strong>{point.previous_price_lkr ? formatLkr(point.previous_price_lkr) : 'Not available'}</strong></div>
        <div><span>Change</span><strong>{point.change_percentage === null ? '—' : `${point.change_percentage > 0 ? '+' : ''}${point.change_percentage.toFixed(1)}%`}</strong></div>
        <div><span>1-year volatility</span><strong>{formatLkr(volatility)}</strong></div>
      </div>
      <div className="chart-heading"><div><span>Historical signal</span><strong>Price midpoint and moving averages</strong></div><span>{history.length} observations</span></div>
      <div className="chart-wrap" aria-label={`Historical price chart for ${point.market_name}`}>
        {isLoading ? <div className="chart-loading">Loading history…</div> : history.length ? (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={history} margin={{ top: 10, right: 6, bottom: 0, left: -16 }}>
              <defs><linearGradient id="priceBand" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#df6c45" stopOpacity={0.28}/><stop offset="100%" stopColor="#df6c45" stopOpacity={0.02}/></linearGradient></defs>
              <CartesianGrid stroke="#dfe4df" strokeDasharray="3 4" vertical={false} />
              <XAxis dataKey="observation_date" tickFormatter={(value: string) => value.slice(5)} minTickGap={32} tickLine={false} axisLine={false} />
              <YAxis tickFormatter={(value: number) => `${Math.round(value / 100) * 100}`} tickLine={false} axisLine={false} />
              <Tooltip content={<ChartTooltip />} />
              <Area type="monotone" dataKey="price_midpoint_lkr" stroke="#df6c45" strokeWidth={2.5} fill="url(#priceBand)" />
              <Line type="monotone" dataKey="moving_average_7" stroke="#153e3b" strokeWidth={1.6} dot={false} />
              <Line type="monotone" dataKey="moving_average_30" stroke="#7a8881" strokeWidth={1.2} strokeDasharray="5 4" dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        ) : <div className="chart-loading">No history is available for this selection.</div>}
      </div>
      <div className="source-row"><span>Source · HARTI daily wholesale bulletin</span><a href={point.source_url} target="_blank" rel="noreferrer">View evidence ↗</a></div>
    </article>
  )
}
