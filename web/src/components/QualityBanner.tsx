import type { QualityStatus } from '../api/types'

interface Props { quality?: QualityStatus; isLoading: boolean }

export function QualityBanner({ quality, isLoading }: Props) {
  if (isLoading) return <div className="quality-banner quality-banner--loading">Checking source quality…</div>
  if (!quality) return null
  const healthy = quality.failed_bulletins === 0 && quality.quarantined_bulletins === 0
  return (
    <aside className={`quality-banner ${healthy ? '' : 'quality-banner--warning'}`} role="status">
      <span className="quality-icon" aria-hidden="true">{healthy ? '✓' : '!'}</span>
      <div>
        <strong>{healthy ? 'Source pipeline verified' : 'Some source records need review'}</strong>
        <span>
          {quality.processed_bulletins.toLocaleString()} of {quality.total_bulletins.toLocaleString()} bulletins processed
          {quality.failed_bulletins > 0 ? ` · ${quality.failed_bulletins} failed` : ''}
        </span>
      </div>
    </aside>
  )
}
