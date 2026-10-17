import type { EconomicAlert, StressSignal } from '../api/types'

interface Props {
  signal?: StressSignal
  alerts: EconomicAlert[]
  unavailable: boolean
}

const labels: Record<keyof StressSignal['components'], string> = {
  anomaly: 'Robust anomaly',
  momentum: '7-day momentum',
  forecast_surprise: 'Expected-price surprise',
  spatial_pressure: 'Nearby-market pressure',
}

export function StressPanel({ signal, alerts, unavailable }: Props) {
  if (unavailable) {
    return <section className="stress-panel stress-panel--empty" role="status">
      <strong>Economic-pressure layer unavailable</strong>
      <span>Build the local stress artifacts to enable this experimental view.</span>
    </section>
  }
  if (!signal) return <section className="stress-panel stress-panel--empty">No stress signal matches this market.</section>
  const marketAlerts = alerts.filter((alert) => alert.market_id === signal.market_id && alert.commodity === signal.commodity)
  return <section className={`stress-panel stress-panel--${signal.severity}`} aria-label="Economic pressure explanation">
    <header>
      <div><span>Experimental early warning</span><h2>{signal.market_name} · {signal.commodity}</h2></div>
      <strong>{Math.round(signal.score)}<small>/100</small></strong>
    </header>
    <p className="stress-verdict"><b>{signal.severity}</b> pressure · {Math.round(signal.confidence * 100)}% evidence confidence{signal.stale ? ' · stale data' : ''}</p>
    <div className="stress-components">
      {(Object.entries(signal.components) as [keyof StressSignal['components'], number][]).map(([key, value]) =>
        <div key={key}><span>{labels[key]}</span><progress max="100" value={value} /><b>{Math.round(value)}</b></div>
      )}
    </div>
    {marketAlerts.map((alert) => <p className="active-alert" key={alert.alert_id}>Active since {alert.opened_at} · peak {Math.round(alert.peak_score)}</p>)}
    <p className="stress-disclaimer">This detects unusual price pressure. It is not a shortage prediction or causal conclusion.</p>
  </section>
}
