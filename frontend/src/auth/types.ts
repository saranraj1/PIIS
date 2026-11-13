export interface AuthenticatedPrincipal {
  principal_id: string
  sub: string
  username?: string
  is_service_principal: boolean
  roles: string[]
  permissions: string[]
  issuer?: string
  expires_at?: string
}

export interface AuthContextType {
  token: string | null
  principal: AuthenticatedPrincipal | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  setToken: (token: string | null) => void
  logout: () => void
  clearError: () => void
  loginWithDemoSession?: (role?: string) => Promise<boolean>
}
