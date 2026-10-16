import type { ModelHealth } from '../api/types'
import { formatDate } from '../utils/format'

interface Props {
  health?: ModelHealth
  isLoading: boolean
}

const sourceLabels: Record<string, string> = {
  nasa_power: 'NASA weather',
  cbsl: 'CBSL exchange rate',
  ceypetco: 'Ceypetco fuel price',
}

export function ModelHealthPanel({ health, isLoading }: Props) {
  if (isLoading) {
    return <section className="model-health model-health--loading">Checking model health…</section>
  }
  if (!health) return null

  return (
    <section className={`model-health model-health--${health.status}`} aria-label="Forecast model health">
      <div className="model-health__heading">
        <div>
          <span className="section-index">Model operations / live</span>
          <h2>{health.status === 'healthy' ? 'Forecast systems healthy' : 'Forecast caution active'}</h2>
        </div>
        <strong>{health.model_version ?? 'No champion'}</strong>
      </div>
      <div className="model-health__grid">
        <article><span>Training cutoff</span><strong>{health.training_cutoff ? formatDate(health.training_cutoff) : 'Unavailable'}</strong><small>{health.training_data_age_days == null ? '—' : `${health.training_data_age_days} days old`}</small></article>
        <article><span>Baseline gate</span><strong>{health.strongest_baseline_wins.length ? 'Not passed' : 'Passed'}</strong><small>{health.strongest_baseline_wins.length ? `${health.strongest_baseline_wins.join(', ')} day horizons` : 'All horizons'}</small></article>
        <article><span>Interval calibration</span><strong>{health.undercovered_horizons.length ? 'Under-covering' : 'On target'}</strong><small>{health.undercovered_horizons.length ? `${health.undercovered_horizons.join(', ')} day horizons` : 'Later holdout'}</small></article>
      </div>
      <div className="signal-health">
        {health.signals.map((signal) => (
          <span key={signal.source} className={signal.stale ? 'is-stale' : ''}>
            {sourceLabels[signal.source] ?? signal.source} · {signal.stale ? 'stale' : 'current'}
          </span>
        ))}
      </div>
      {health.messages.length > 0 && <p>{health.messages.join(' ')}</p>}
    </section>
  )
}
