import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { useDashboardFilters } from './useDashboardFilters'

describe('useDashboardFilters', () => {
  beforeEach(() => window.history.replaceState({}, '', '/'))

  it('reads filters from the URL', () => {
    window.history.replaceState({}, '', '/?commodity=Tomato&province=Central&direction=rising')
    const { result } = renderHook(() => useDashboardFilters())

    expect(result.current.filters).toMatchObject({
      commodity: 'Tomato',
      province: 'Central',
      direction: 'rising',
    })
  })

  it('writes updates to the URL and resets them', () => {
    const { result } = renderHook(() => useDashboardFilters())

    act(() => result.current.updateFilters({ commodity: 'Carrot', district: 'Kandy' }))
    expect(window.location.search).toBe('?commodity=Carrot&district=Kandy')

    act(() => result.current.resetFilters())
    expect(window.location.search).toBe('')
    expect(result.current.filters.commodity).toBe('')
  })
})
