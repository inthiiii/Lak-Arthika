import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { stressFixture } from '../test/fixtures'
import { StressSummary } from './StressSummary'

describe('StressSummary', () => {
  it('summarizes assessed markets and elevated signals', () => {
    render(<StressSummary signals={stressFixture} alerts={[]} />)
    expect(screen.getByLabelText('Economic pressure summary')).toHaveTextContent('Average pressure78')
    expect(screen.getByText('Elevated signals').parentElement).toHaveTextContent('1')
  })
})
