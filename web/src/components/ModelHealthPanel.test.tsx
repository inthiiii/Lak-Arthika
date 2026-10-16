import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ModelHealthPanel } from './ModelHealthPanel'

describe('ModelHealthPanel', () => {
  it('shows honest champion and freshness warnings', () => {
    render(<ModelHealthPanel isLoading={false} health={{
      status: 'warning', model_version: 'candidate-v2', checked_at: '2026-01-02T00:00:00Z',
      training_cutoff: '2026-01-01', training_data_age_days: 1,
      strongest_baseline_wins: [7], undercovered_horizons: [30],
      signals: [{ source: 'cbsl', latest_effective_date: null, observation_count: 0, age_days: null, stale: true }],
      messages: ['The baseline still wins.'],
    }} />)
    expect(screen.getByText('Forecast caution active')).toBeInTheDocument()
    expect(screen.getByText('Not passed')).toBeInTheDocument()
    expect(screen.getByText(/CBSL exchange rate · stale/)).toBeInTheDocument()
  })
})
