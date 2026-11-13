import type { ApiErrorResponse } from './types'

export class ApiClientError extends Error {
  public status: number
  public errorData?: ApiErrorResponse
  public errorCode?: string | null

  constructor(
    message: string,
    status: number,
    errorData?: ApiErrorResponse,
    errorCode?: string | null
  ) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
    this.errorData = errorData
    this.errorCode = errorCode || errorData?.code || null
  }
}

export interface RequestOptions extends RequestInit {
  token?: string | null
  timeoutMs?: number
}

const DEFAULT_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

type TokenProvider = () => string | null
let globalTokenProvider: TokenProvider | null = null

export async function apiClient<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const {
    token = globalTokenProvider ? globalTokenProvider() : null,
    timeoutMs = 15000,
    headers: customHeaders,
    ...fetchOptions
  } = options

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  const headers = new Headers(customHeaders)
  headers.set('Accept', 'application/json')
  if (fetchOptions.body && !(fetchOptions.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const url = `${DEFAULT_BASE_URL}${endpoint}`

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      headers,
      signal: fetchOptions.signal || controller.signal,
    })

    if (!response.ok) {
      let errorData: ApiErrorResponse | undefined
      try {
        errorData = (await response.json()) as ApiErrorResponse
      } catch {
        // Non-JSON response
      }

      const message =
        errorData?.detail ||
        errorData?.error ||
        `HTTP Error ${response.status}: ${response.statusText}`

      const headerCode = response.headers.get('x-piis-error-code')
      const errorCode = headerCode || errorData?.code || null

      throw new ApiClientError(message, response.status, errorData, errorCode)
    }

    if (response.status === 204) {
      return {} as T
    }

    return (await response.json()) as T
  } catch (err) {
    if (err instanceof ApiClientError) {
      throw err
    }
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiClientError('Request timed out or was cancelled', 408)
    }
    throw new ApiClientError(
      err instanceof Error ? err.message : 'Unknown network error occurred',
      0
    )
  } finally {
    clearTimeout(timeoutId)
  }
}

apiClient.get = function <T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  return apiClient<T>(endpoint, { ...options, method: 'GET' })
}

apiClient.post = function <T>(
  endpoint: string,
  body?: unknown,
  options: RequestOptions = {}
): Promise<T> {
  return apiClient<T>(endpoint, {
    ...options,
    method: 'POST',
    body: body !== undefined ? (typeof body === 'string' ? body : JSON.stringify(body)) : undefined,
  })
}

apiClient.setTokenProvider = function (provider: TokenProvider | null): void {
  globalTokenProvider = provider
}
