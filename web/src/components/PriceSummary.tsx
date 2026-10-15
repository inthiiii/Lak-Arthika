import type { MarketPricePoint } from '../api/types'
import { formatDate, formatLkr } from '../utils/format'

export function PriceSummary({ points, selectedDate }: { points: MarketPricePoint[]; selectedDate: string }) {
  const average = points.length
    ? points.reduce((sum, point) => sum + point.midpoint_price_lkr, 0) / points.length
    : 0
  const rising = points.filter((point) => (point.change_percentage ?? 0) > 2).length
  const spread = points.length
    ? Math.max(...points.map((point) => point.midpoint_price_lkr)) - Math.min(...points.map((point) => point.midpoint_price_lkr))
    : 0

  return (
    <section className="summary-grid" aria-label="Price summary">
      <article><span>Visible markets</span><strong>{points.length}</strong><small>with a verified observation</small></article>
      <article><span>Average midpoint</span><strong>{formatLkr(average)}</strong><small>per kilogram</small></article>
      <article><span>Markets rising</span><strong>{rising}</strong><small>more than 2% from prior signal</small></article>
      <article><span>Market spread</span><strong>{formatLkr(spread)}</strong><small>{selectedDate ? `selected ${formatDate(selectedDate)}` : 'latest data'}</small></article>
    </section>
  )
}
