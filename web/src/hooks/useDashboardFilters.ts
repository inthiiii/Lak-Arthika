import { useCallback, useState } from 'react'
import type { DashboardFilters, Direction, MapMode } from '../api/types'

const defaults: DashboardFilters = {
  commodity: '', date: '', province: '', district: '', market: '', direction: 'all', mode: 'prices',
}

function readFilters(): DashboardFilters {
  const params = new URLSearchParams(window.location.search)
  const direction = params.get('direction')
  return {
    commodity: params.get('commodity') ?? '',
    date: params.get('date') ?? '',
    province: params.get('province') ?? '',
    district: params.get('district') ?? '',
    market: params.get('market') ?? '',
    direction: ['rising', 'stable', 'falling'].includes(direction ?? '')
      ? (direction as Direction)
      : 'all',
    mode: params.get('mode') === 'stress' ? ('stress' as MapMode) : 'prices',
  }
}

export function useDashboardFilters() {
  const [filters, setFilters] = useState<DashboardFilters>(readFilters)

  const updateFilters = useCallback((changes: Partial<DashboardFilters>, replace = false) => {
    setFilters((current) => {
      const next = { ...current, ...changes }
      const params = new URLSearchParams()
      Object.entries(next).forEach(([key, value]) => {
        if (value && value !== 'all' && value !== 'prices') params.set(key, value)
      })
      const url = `${window.location.pathname}${params.size ? `?${params}` : ''}`
      window.history[replace ? 'replaceState' : 'pushState']({}, '', url)
      return next
    })
  }, [])

  const resetFilters = useCallback(() => {
    setFilters(defaults)
    window.history.pushState({}, '', window.location.pathname)
  }, [])

  return { filters, updateFilters, resetFilters }
}
