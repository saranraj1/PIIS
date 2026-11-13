import React, { useState } from 'react'
import { Sun, Moon, Key, UserCheck, ShieldCheck, LogOut, Menu, X } from 'lucide-react'
import { useTheme } from '../../theme/ThemeContext'
import { useAuth } from '../../auth/AuthContext'

interface AppHeaderProps {
  onToggleSidebar?: () => void
  isSidebarOpen?: boolean
}

export const AppHeader: React.FC<AppHeaderProps> = ({ onToggleSidebar, isSidebarOpen }) => {
  const { theme, toggleTheme } = useTheme()
  const { principal, isAuthenticated, setToken, logout, loginWithDemoSession } = useAuth()
  const [showTokenInput, setShowTokenInput] = useState(false)
  const [tempToken, setTempToken] = useState('')
  const [isDemoLoading, setIsDemoLoading] = useState(false)

  const handleSaveToken = (e: React.FormEvent) => {
    e.preventDefault()
    if (tempToken.trim()) {
      setToken(tempToken.trim())
      setTempToken('')
      setShowTokenInput(false)
    }
  }

  const handleQuickDemoLogin = async () => {
    if (!loginWithDemoSession) return
    setIsDemoLoading(true)
    try {
      await loginWithDemoSession('INCIDENT_MANAGER')
    } finally {
      setIsDemoLoading(false)
    }
  }

  const handleFetchDemoTokenForInput = async () => {
    try {
      const res = await fetch('/api/v1/auth/demo-token?role=INCIDENT_MANAGER')
      if (res.ok) {
        const data = await res.json()
        if (data.access_token) {
          setTempToken(data.access_token)
        }
      }
    } catch {
      // Quiet fallback
    }
  }

  return (
    <header className="bg-[var(--bg-surface)] text-[var(--text-primary)] border-b border-[var(--border-subtle)] px-4 py-2.5 flex items-center justify-between gap-4 sticky top-0 z-30 transition-colors">
      <div className="flex items-center gap-3">
        {onToggleSidebar && (
          <button
            type="button"
            onClick={onToggleSidebar}
            aria-label={isSidebarOpen ? 'Close Navigation Menu' : 'Open Navigation Menu'}
            className="md:hidden p-1.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-subtle)] rounded-xs focus:outline-none focus:ring-1 focus:ring-[var(--border-strong)]"
          >
            {isSidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        )}

        <div className="flex items-center gap-2.5">
          <span className="bg-[var(--text-primary)] text-[var(--bg-surface)] font-extrabold text-xs px-2 py-0.5 rounded-xs tracking-wider font-mono">
            PIIS
          </span>
          <div className="flex flex-col">
            <span className="font-bold text-sm tracking-tight text-[var(--text-primary)] leading-tight">
              Production Incident Intelligence System
            </span>
            <span className="text-xs font-mono text-[var(--text-muted)] leading-none mt-0.5">
              Telecom Operations Console
            </span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <span className="hidden lg:inline-flex items-center gap-1.5 text-xs font-medium font-mono px-2 py-0.5 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--text-secondary)]">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
          STRICT READ-ONLY BOUNDARY
        </span>

        {/* Theme Toggle */}
        <button
          type="button"
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Switch to Light Theme' : 'Switch to Dark Theme'}
          className="p-1.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-subtle)] rounded-xs transition-colors focus:outline-none focus:ring-1 focus:ring-[var(--border-strong)]"
        >
          {theme === 'dark' ? (
            <Sun className="w-4 h-4 text-amber-400" aria-hidden="true" />
          ) : (
            <Moon className="w-4 h-4 text-[var(--text-secondary)]" aria-hidden="true" />
          )}
        </button>

        {/* User Identity / Token Trigger */}
        {isAuthenticated && principal ? (
          <div className="flex items-center gap-2 bg-[var(--bg-subtle)] border border-[var(--border-subtle)] rounded-xs px-2.5 py-1 text-xs">
            <UserCheck className="w-3.5 h-3.5 text-emerald-500 dark:text-emerald-400" aria-hidden="true" />
            <span className="font-mono text-[var(--text-primary)]">{principal.principal_id}</span>
            <span className="text-xs font-mono font-bold uppercase px-2 py-0.5 rounded-xs bg-[var(--bg-surface)] text-[var(--text-secondary)] border border-[var(--border-subtle)]">
              {principal.roles[0] || 'OPERATOR'}
            </span>
            <button
              type="button"
              onClick={logout}
              title="Logout (Purge in-memory token)"
              aria-label="Logout"
              className="text-[var(--text-muted)] hover:text-rose-500 dark:hover:text-rose-400 ml-1 transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleQuickDemoLogin}
              disabled={isDemoLoading}
              title="Quickly authenticate as Incident Manager for testing"
              className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-2.5 py-1 rounded-xs transition-colors focus:outline-none focus:ring-1 focus:ring-emerald-400 font-mono disabled:opacity-50"
            >
              <ShieldCheck className="w-3.5 h-3.5" aria-hidden="true" />
              <span>{isDemoLoading ? 'Authenticating...' : 'Demo Login'}</span>
            </button>

            <button
              type="button"
              onClick={() => setShowTokenInput(true)}
              className="flex items-center gap-1.5 bg-[var(--text-primary)] text-[var(--bg-surface)] hover:opacity-90 text-xs font-semibold px-2.5 py-1 rounded-xs transition-opacity focus:outline-none focus:ring-1 focus:ring-[var(--border-strong)] font-mono"
            >
              <Key className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Set Bearer Token</span>
            </button>
          </div>
        )}
      </div>

      {/* Modal for In-Memory Token Input */}
      {showTokenInput && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="token-modal-title"
          className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50"
        >
          <div className="bg-[var(--bg-surface)] border border-[var(--border-strong)] rounded-sm max-w-md w-full p-5 shadow-2xl text-[var(--text-primary)]">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-500 dark:text-emerald-400" />
                <h2 id="token-modal-title" className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider">
                  In-Memory Bearer Authentication
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setShowTokenInput(false)}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                aria-label="Close dialog"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-[var(--text-secondary)] mb-4 leading-relaxed">
              Paste an authenticated OIDC Bearer JWT or auto-load standard demonstration credentials.
              The token is verified independently on every request by the backend API.
            </p>

            <div className="mb-3">
              <button
                type="button"
                onClick={handleFetchDemoTokenForInput}
                className="w-full py-1.5 px-3 rounded-xs border border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-xs font-mono font-medium flex items-center justify-center gap-1.5 transition-colors"
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                Auto-Fill Incident Manager Token
              </button>
            </div>

            <form onSubmit={handleSaveToken}>
              <label htmlFor="modal-token-input" className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                Bearer JWT:
              </label>
              <textarea
                id="modal-token-input"
                rows={4}
                required
                value={tempToken}
                onChange={(e) => setTempToken(e.target.value)}
                placeholder="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
                className="w-full bg-[var(--bg-subtle)] border border-[var(--border-subtle)] rounded-xs p-2 text-xs font-mono text-[var(--text-primary)] focus:outline-none focus:border-[var(--text-primary)] mb-4"
              />

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowTokenInput(false)}
                  className="px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] rounded-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 text-xs font-semibold bg-[var(--text-primary)] text-[var(--bg-surface)] hover:opacity-90 rounded-xs transition-opacity font-mono"
                >
                  Apply Token
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </header>
  )
}
