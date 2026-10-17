import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { stressFixture } from '../test/fixtures'
import { StressPanel } from './StressPanel'

describe('StressPanel', () => {
  it('explains components, confidence and safety limits', () => {
    render(<StressPanel signal={stressFixture[0]} alerts={[]} unavailable={false} />)
    expect(screen.getByLabelText('Economic pressure explanation')).toHaveTextContent('warning pressure')
    expect(screen.getByText('Robust anomaly')).toBeInTheDocument()
    expect(screen.getByText(/not a shortage prediction/)).toBeInTheDocument()
  })

  it('fails safely when artifacts are unavailable', () => {
    render(<StressPanel alerts={[]} unavailable />)
    expect(screen.getByRole('status')).toHaveTextContent('Economic-pressure layer unavailable')
  })
})
