import React from 'react'
import { AlertCircle, Key, RefreshCw, WifiOff, ShieldAlert } from 'lucide-react'
import { ApiClientError } from '../../api/client'

interface ErrorStateProps {
  error: unknown
  onRetry?: () => void
  title?: string
  endpointName?: string
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  error,
  onRetry,
  title = 'API Query Failed',
  endpointName,
}) => {
  const isApiClientError = error instanceof ApiClientError
  const status = isApiClientError ? error.status : 0
  const message = error instanceof Error ? error.message : 'An unexpected network error occurred'

  const isAuthError = status === 401
  const isForbidden = status === 403
  const isNetworkError = status === 0 || status === 408

  return (
    <div
      role="alert"
      className="p-6 rounded-sm bg-[var(--bg-surface)] border border-rose-500/30 flex flex-col items-center justify-center text-center gap-3 transition-colors"
    >
      <div className="p-3 rounded-xs bg-rose-500/10 text-rose-500 border border-rose-500/20">
        {isAuthError ? (
          <Key className="w-6 h-6" />
        ) : isForbidden ? (
          <ShieldAlert className="w-6 h-6" />
        ) : isNetworkError ? (
          <WifiOff className="w-6 h-6" />
        ) : (
          <AlertCircle className="w-6 h-6" />
        )}
      </div>

      <div className="space-y-1">
        <h3 className="text-sm font-bold text-rose-500 font-mono">
          {isAuthError
            ? 'Authentication Required'
            : isForbidden
            ? 'Permission Denied (403 Forbidden)'
            : isNetworkError
            ? 'Backend Service Unreachable'
            : title}
        </h3>
        <p className="text-xs text-[var(--text-primary)] font-medium max-w-md">{message}</p>

        {isAuthError && (
          <p className="text-[0.72rem] text-[var(--text-muted)] max-w-md pt-1">
            Endpoint requires a verified Bearer token with appropriate operator roles. Open the Key modal in the top header to enter an in-memory session token.
          </p>
        )}

        {isNetworkError && (
          <p className="text-[0.72rem] text-[var(--text-muted)] max-w-md pt-1">
            Ensure FastAPI backend is running (<code className="font-mono text-rose-400">http://127.0.0.1:8000</code>).
          </p>
        )}

        {endpointName && (
          <div className="text-[0.68rem] font-mono text-[var(--text-muted)] mt-1">
            Endpoint: {endpointName}
          </div>
        )}
      </div>

      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs text-xs font-semibold bg-rose-500/10 hover:bg-rose-500/20 text-rose-500 border border-rose-500/30 transition-colors mt-1 font-mono"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry Request</span>
        </button>
      )}
    </div>
  )
}
