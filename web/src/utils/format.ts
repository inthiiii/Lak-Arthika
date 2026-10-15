import { format, parseISO } from 'date-fns'

export const formatLkr = (value: number) =>
  new Intl.NumberFormat('en-LK', {
    style: 'currency', currency: 'LKR', maximumFractionDigits: 0,
  }).format(value)

export const formatDate = (value: string) => format(parseISO(value), 'd MMM yyyy')

export function calculatePercentageChange(current: number, previous: number | null) {
  if (previous === null || previous === 0) return null
  return ((current - previous) / previous) * 100
}

export function movementLabel(change: number | null) {
  if (change === null) return { label: 'No prior signal', tone: 'neutral', arrow: '—' }
  if (change > 2) return { label: 'Rising', tone: 'rising', arrow: '↑' }
  if (change < -2) return { label: 'Falling', tone: 'falling', arrow: '↓' }
  return { label: 'Stable', tone: 'stable', arrow: '→' }
}
