import { describe, expect, it } from 'vitest'
import { calculatePercentageChange, formatDate, formatLkr, movementLabel } from './format'

describe('format utilities', () => {
  it('formats Sri Lankan rupee prices', () => {
    expect(formatLkr(1250)).toContain('1,250')
  })

  it('formats ISO observation dates', () => {
    expect(formatDate('2025-12-31')).toBe('31 Dec 2025')
  })

  it('calculates percentage movement and handles a missing baseline', () => {
    expect(calculatePercentageChange(330, 300)).toBeCloseTo(10)
    expect(calculatePercentageChange(270, 300)).toBeCloseTo(-10)
    expect(calculatePercentageChange(300, 0)).toBeNull()
    expect(calculatePercentageChange(300, null)).toBeNull()
  })

  it('maps movement thresholds to marker tones', () => {
    expect(movementLabel(2.1)).toMatchObject({ label: 'Rising', tone: 'rising' })
    expect(movementLabel(-2.1)).toMatchObject({ label: 'Falling', tone: 'falling' })
    expect(movementLabel(2)).toMatchObject({ label: 'Stable', tone: 'stable' })
    expect(movementLabel(null)).toMatchObject({ label: 'No prior signal', tone: 'neutral' })
  })
})
