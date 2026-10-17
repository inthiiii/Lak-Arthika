import type { EconomicAlert, StressSignal } from '../api/types'

interface Props {
  signals: StressSignal[]
  alerts: EconomicAlert[]
}

export function StressSummary({ signals, alerts }: Props) {
  const average = signals.length
    ? signals.reduce((total, signal) => total + signal.score, 0) / signals.length
    : 0
  const elevated = signals.filter((signal) => signal.severity !== 'normal').length
  const confident = signals.filter((signal) => signal.confidence >= 0.75 && !signal.stale).length
  return <section className="summary-grid" aria-label="Economic pressure summary">
    <article><span>Markets assessed</span><strong>{signals.length}</strong><small>for the selected commodity</small></article>
    <article><span>Average pressure</span><strong>{Math.round(average)}</strong><small>out of 100</small></article>
    <article><span>Elevated signals</span><strong>{elevated}</strong><small>watch, warning or critical</small></article>
    <article><span>Active alerts</span><strong>{alerts.length}</strong><small>{confident} current signals have strong evidence</small></article>
  </section>
}
