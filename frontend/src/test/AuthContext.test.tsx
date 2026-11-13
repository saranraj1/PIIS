import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AuthProvider, useAuth } from '../auth/AuthContext'

const AuthTestComponent = () => {
  const { token, principal, isAuthenticated, setToken, logout } = useAuth()

  // Helper to generate a dummy JWT
  const handleLogin = () => {
    // Header: {"alg":"HS256","typ":"JWT"}
    const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
    // Payload: {"sub":"operator-1","username":"noc_lead","roles":["telecom_engineer"],"permissions":["read:incidents"]}
    const payload = btoa(
      JSON.stringify({
        sub: 'operator-1',
        username: 'noc_lead',
        roles: ['telecom_engineer'],
        permissions: ['read:incidents'],
      })
    )
    const mockJwt = `${header}.${payload}.mockSignature`
    setToken(mockJwt)
  }

  return (
    <div>
      <span data-testid="auth-status">{isAuthenticated ? 'authenticated' : 'unauthenticated'}</span>
      <span data-testid="principal-sub">{principal?.sub || 'none'}</span>
      <span data-testid="principal-role">{principal?.roles?.join(',') || 'none'}</span>
      <span data-testid="token-status">{token ? 'token-present' : 'token-empty'}</span>
      <button onClick={handleLogin}>Log In</button>
      <button onClick={logout}>Log Out</button>
    </div>
  )
}

describe('AuthContext - In-Memory Security Boundary', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
  })

  it('initializes in anonymous read-only unauthenticated state', () => {
    render(
      <AuthProvider>
        <AuthTestComponent />
      </AuthProvider>
    )

    expect(screen.getByTestId('auth-status').textContent).toBe('unauthenticated')
    expect(screen.getByTestId('principal-sub').textContent).toBe('none')
    expect(screen.getByTestId('token-status').textContent).toBe('token-empty')
  })

  it('decodes JWT claims in memory without writing to localStorage or sessionStorage', async () => {
    const user = userEvent.setup()

    render(
      <AuthProvider>
        <AuthTestComponent />
      </AuthProvider>
    )

    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Log In' }))
    })

    expect(screen.getByTestId('auth-status').textContent).toBe('authenticated')
    expect(screen.getByTestId('principal-sub').textContent).toBe('operator-1')
    expect(screen.getByTestId('principal-role').textContent).toBe('telecom_engineer')
    expect(screen.getByTestId('token-status').textContent).toBe('token-present')

    // CRITICAL SECURITY ASSERTION: Zero disk persistence
    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('piis_token')).toBeNull()
    expect(sessionStorage.getItem('token')).toBeNull()
  })

  it('purges memory token and claims completely on logout', async () => {
    const user = userEvent.setup()

    render(
      <AuthProvider>
        <AuthTestComponent />
      </AuthProvider>
    )

    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Log In' }))
    })
    expect(screen.getByTestId('auth-status').textContent).toBe('authenticated')

    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Log Out' }))
    })

    expect(screen.getByTestId('auth-status').textContent).toBe('unauthenticated')
    expect(screen.getByTestId('principal-sub').textContent).toBe('none')
    expect(screen.getByTestId('token-status').textContent).toBe('token-empty')
  })
})
