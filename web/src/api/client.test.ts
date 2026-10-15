import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiGet } from './client'

describe('apiGet', () => {
  afterEach(() => vi.restoreAllMocks())

  it('returns JSON and sends query parameters', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ value: 42 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    await expect(apiGet<{ value: number }>('/v1/example', { commodity: 'Red Onion' }))
      .resolves.toEqual({ value: 42 })
    expect(fetchMock.mock.calls[0][0].toString()).toContain('commodity=Red+Onion')
  })

  it('surfaces the API detail for an unsuccessful response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Historical analytics are unavailable.' }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    await expect(apiGet('/v1/prices/history')).rejects.toEqual(
      new ApiError(503, 'Historical analytics are unavailable.'),
    )
  })

  it('uses a status-based message for a non-JSON error', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('gateway unavailable', { status: 502 }),
    )

    await expect(apiGet('/v1/catalog')).rejects.toMatchObject({
      name: 'ApiError',
      status: 502,
      message: 'The API returned 502.',
    })
  })
})
