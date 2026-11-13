import { describe, it, expect, vi, beforeEach } from 'vitest'
import { apiClient, ApiClientError } from '../api/client'

describe('ApiClient', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    apiClient.setTokenProvider(null)
  })

  it('performs successful GET request and returns JSON', async () => {
    const mockData = { status: 'healthy', version: '1.0.0' }
    vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockData,
    } as Response)

    const result = await apiClient.get<typeof mockData>('/api/v1/health')
    expect(result).toEqual(mockData)
  })

  it('injects Bearer token when tokenProvider is configured', async () => {
    const mockToken = 'mock-jwt-token-xyz'
    apiClient.setTokenProvider(() => mockToken)

    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ authenticated: true }),
    } as Response)

    await apiClient.get('/api/v1/auth/me')

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    const callArgs = fetchSpy.mock.calls[0]
    expect(callArgs[0]).toBe('/api/v1/auth/me')

    const headers = callArgs[1]?.headers as Headers
    expect(headers).toBeDefined()
    expect(headers.get('Authorization')).toBe(`Bearer ${mockToken}`)
  })

  it('throws ApiClientError with status code and details on non-ok response', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 403,
      statusText: 'Forbidden',
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ detail: 'Operator signature required' }),
    } as Response)

    await expect(apiClient.get('/api/v1/incidents')).rejects.toThrow(ApiClientError)
  })
})
