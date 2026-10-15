import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { pricePointsFixture } from '../test/fixtures'
import { PriceSummary } from './PriceSummary'

describe('PriceSummary', () => {
  it('summarizes the visible market observations', () => {
    render(<PriceSummary points={pricePointsFixture} selectedDate="2025-12-31" />)
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText(/31 Dec 2025/)).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('renders safe zero values for an empty result', () => {
    render(<PriceSummary points={[]} selectedDate="2025-12-31" />)
    expect(screen.getAllByText('0')).toHaveLength(2)
    expect(screen.getAllByText(/0/).length).toBeGreaterThanOrEqual(2)
  })
})
