import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { qualityFixture } from '../test/fixtures'
import { QualityBanner } from './QualityBanner'

describe('QualityBanner', () => {
  it('shows a verified state for a clean pipeline', () => {
    render(<QualityBanner quality={qualityFixture} isLoading={false} />)
    expect(screen.getByText('Source pipeline verified')).toBeInTheDocument()
    expect(screen.getByText(/340 of 340 bulletins processed/)).toBeInTheDocument()
  })

  it('shows a warning when source records have failed', () => {
    render(
      <QualityBanner
        quality={{ ...qualityFixture, failed_bulletins: 2, processed_bulletins: 338 }}
        isLoading={false}
      />,
    )
    expect(screen.getByText('Some source records need review')).toBeInTheDocument()
    expect(screen.getByText(/2 failed/)).toBeInTheDocument()
  })
})
