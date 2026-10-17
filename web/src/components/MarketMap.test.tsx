import type { ReactNode } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { pricePointsFixture, stressFixture } from '../test/fixtures'
import { MarketMap } from './MarketMap'

vi.mock('maplibre-gl', () => ({ setWorkerUrl: vi.fn() }))
vi.mock('maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url', () => ({ default: 'worker.js' }))
vi.mock('react-map-gl/maplibre', () => ({
  default: ({ children }: { children: ReactNode }) => <div data-testid="map">{children}</div>,
  Marker: ({ children }: { children: ReactNode }) => <>{children}</>,
  NavigationControl: () => null,
  Popup: ({ children }: { children: ReactNode }) => <div role="dialog">{children}</div>,
}))

describe('MarketMap', () => {
  it('renders an understandable empty state', () => {
    render(<MarketMap points={[]} selectedMarketId={null} onSelect={vi.fn()} />)
    expect(screen.getByText('No markets match these filters')).toBeInTheDocument()
  })

  it('colours markers by movement and reports market selection', () => {
    const onSelect = vi.fn()
    render(
      <MarketMap
        points={pricePointsFixture}
        selectedMarketId="dambulla"
        onSelect={onSelect}
      />,
    )

    const rising = screen.getByRole('button', { name: /Dambulla, Rising/ })
    const falling = screen.getByRole('button', { name: /Kandy, Falling/ })
    expect(rising).toHaveClass('market-marker--rising', 'is-selected')
    expect(falling).toHaveClass('market-marker--falling')

    fireEvent.click(falling)
    expect(onSelect).toHaveBeenCalledWith('kandy')
  })

  it('colours and labels markers by economic-pressure severity', () => {
    render(
      <MarketMap
        points={pricePointsFixture.slice(0, 1)} selectedMarketId="dambulla"
        onSelect={vi.fn()} mode="stress" stressSignals={stressFixture}
      />,
    )
    const marker = screen.getByRole('button', { name: /Dambulla, warning pressure, score 78/ })
    expect(marker).toHaveClass('stress-warning')
    expect(screen.getByText('Pressure score 78 / 100')).toBeInTheDocument()
  })
})
