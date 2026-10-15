import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MarketPanel } from './MarketPanel'

describe('MarketPanel', () => {
  it('prompts the user when no market is selected', () => {
    render(<MarketPanel history={[]} isLoading={false} />)
    expect(screen.getByRole('heading', { name: 'Select a market' })).toBeInTheDocument()
    expect(screen.getByText(/Choose a point on the map/)).toBeInTheDocument()
  })
})
