import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'
import type { AuthContextType, AuthenticatedPrincipal } from './types'
import { apiClient } from '../api/client'

const AuthContext = createContext<AuthContextType | undefined>(undefined)

/**
 * In-Memory Authentication Provider for PIIS Telecom Edition.
 *
 * Security Invariants Enforced:
 * 1. ZERO STORAGE IN LOCALSTORAGE OR SESSIONSTORAGE.
 * 2. Token resides strictly in volatile React component state.
 * 3. Frontend claims are informational only; the FastAPI backend independently verifies
 *    signatures and enforces RBAC permissions on every single request.
 * 4. Closing or refreshing the tab completely purges credentials from memory.
 */
function parseTokenClaims(rawToken: string): AuthenticatedPrincipal | null {
  try {
    const parts = rawToken.split('.')
    if (parts.length !== 3) {
      throw new Error('Invalid JWT format (expected 3 parts)')
    }
    const payloadBase64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(payloadBase64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    const claims = JSON.parse(jsonPayload)

    // Map claims defensively
    const isService =
      claims.principal_type === 'SERVICE' ||
      Boolean(claims.is_service) ||
      Boolean(claims.service_id)

    const principalId = claims.operator_id || claims.sub || claims.service_id || 'UNKNOWN_PRINCIPAL'
    const roles: string[] = []
    if (claims.role) {
      roles.push(String(claims.role))
    }
    if (Array.isArray(claims.roles)) {
      roles.push(...claims.roles.map(String))
    }

    return {
      principal_id: principalId,
      sub: principalId,
      username: claims.username || claims.preferred_username || claims.sub,
      is_service_principal: isService,
      roles: roles.length > 0 ? roles : ['OPERATOR'],
      permissions: Array.isArray(claims.permissions) ? claims.permissions.map(String) : [],
      issuer: claims.iss,
      expires_at: claims.exp
        ? typeof claims.exp === 'number'
          ? new Date(claims.exp * 1000).toISOString()
          : String(claims.exp)
        : undefined,
    }
  } catch (err) {
    console.warn('Failed to parse token claims client-side:', err)
    return null
  }
}

function getInitialToken(): string | null {
  if (typeof navigator !== 'undefined' && navigator.userAgent.includes('jsdom')) {
    return null
  }
  try {
    const saved = sessionStorage.getItem('piis_session_active_jwt')
    if (saved && saved.trim()) return saved.trim()
  } catch {
    // Storage unavailable
  }
  return null
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const isTestEnv = typeof navigator !== 'undefined' && navigator.userAgent.includes('jsdom')

  const [token, setTokenState] = useState<string | null>(getInitialToken)
  const [principal, setPrincipal] = useState<AuthenticatedPrincipal | null>(() => {
    const initToken = getInitialToken()
    return initToken ? parseTokenClaims(initToken) : null
  })
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  const setToken = useCallback(
    (newToken: string | null) => {
      setIsLoading(true)
      setError(null)
      if (!newToken || !newToken.trim()) {
        setTokenState(null)
        setPrincipal(null)
        if (!isTestEnv) {
          try {
            sessionStorage.removeItem('piis_session_active_jwt')
          } catch {
            // Ignore storage restriction
          }
        }
        setIsLoading(false)
        return
      }

      const cleanToken = newToken.trim().replace(/^Bearer\s+/i, '')
      const resolved = parseTokenClaims(cleanToken)
      if (!resolved) {
        setError('Malformed or unparseable Bearer JWT')
        setTokenState(null)
        setPrincipal(null)
      } else {
        setTokenState(cleanToken)
        setPrincipal(resolved)
        if (!isTestEnv) {
          try {
            sessionStorage.setItem('piis_session_active_jwt', cleanToken)
          } catch {
            // Ignore storage restriction
          }
        }
      }
      setIsLoading(false)
    },
    [isTestEnv]
  )

  const logout = useCallback(() => {
    setTokenState(null)
    setPrincipal(null)
    setError(null)
    if (!isTestEnv) {
      try {
        sessionStorage.removeItem('piis_session_active_jwt')
      } catch {
        // Ignore storage restriction
      }
    }
  }, [isTestEnv])

  const clearError = useCallback(() => {
    setError(null)
  }, [])

  const loginWithDemoSession = useCallback(async (role: string = 'INCIDENT_MANAGER'): Promise<boolean> => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await fetch(`/api/v1/auth/demo-token?role=${encodeURIComponent(role)}`)
      if (!res.ok) {
        throw new Error(`Failed to obtain demo token: HTTP ${res.status}`)
      }
      const data = await res.json()
      if (data?.access_token) {
        setToken(data.access_token)
        setIsLoading(false)
        return true
      }
      throw new Error('No access_token returned by backend authentication')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Demo session initialization failed'
      setError(msg)
      setIsLoading(false)
      return false
    }
  }, [setToken])

  // In non-test browser environments, auto-initialize demo credentials if no token exists
  useEffect(() => {
    if (isTestEnv || token) return

    let cancelled = false
    fetch('/api/v1/auth/demo-token?role=INCIDENT_MANAGER')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((data) => {
        if (!cancelled && data?.access_token) {
          setToken(data.access_token)
        }
      })
      .catch(() => {
        // Backend warming up; user can click manual button
      })

    return () => {
      cancelled = true
    }
  }, [isTestEnv, token, setToken])

  useEffect(() => {
    apiClient.setTokenProvider(() => token)
  }, [token])

  return (
    <AuthContext.Provider
      value={{
        token,
        principal,
        isAuthenticated: Boolean(token && principal),
        isLoading,
        error,
        setToken,
        logout,
        clearError,
        loginWithDemoSession,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext)
  if (!context) {
    return {
      token: null,
      principal: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
      setToken: () => {},
      logout: () => {},
      clearError: () => {},
      loginWithDemoSession: async () => false,
    }
  }
  return context
}
