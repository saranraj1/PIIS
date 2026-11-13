import React from 'react'
import type { EpistemicCategory } from '../epistemic/EpistemicBadge'

interface MetricCardProps {
  label: string
  value: React.ReactNode
  subtext?: string
  sourceEndpoint?: string
  epistemicCategory?: EpistemicCategory
  icon?: React.ReactNode
  isLoading?: boolean
  isUnavailable?: boolean
  unavailableReason?: string
  className?: string
  onClick?: () => void
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  subtext,
  sourceEndpoint,
  epistemicCategory: _epistemicCategory,
  icon,
  isLoading = false,
  isUnavailable = false,
  unavailableReason = 'Backend contract does not provide this metric',
  className = '',
  onClick,
}) => {
  return (
    <div
      onClick={onClick}
      title={sourceEndpoint ? `Source: ${sourceEndpoint}` : undefined}
      className={`rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 flex flex-col justify-between transition-colors ${
        onClick ? 'cursor-pointer hover:border-[var(--border-strong)] hover:bg-[var(--bg-subtle)]' : ''
      } ${className}`}
    >
      <div>
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-medium text-[var(--text-secondary)]">
            {label}
          </span>
          {icon && <div className="text-[var(--text-muted)]">{icon}</div>}
        </div>

        <div className="mt-2.5 flex items-baseline gap-2">
          {isLoading ? (
            <span className="text-base font-mono tabular-nums text-[var(--text-muted)] animate-pulse">Loading...</span>
          ) : isUnavailable ? (
            <div className="flex flex-col">
              <span className="text-sm font-bold font-mono text-[var(--text-muted)]">UNAVAILABLE</span>
              <span className="text-xs text-[var(--text-muted)] mt-0.5">{unavailableReason}</span>
            </div>
          ) : (
            <div className="text-2xl font-bold font-mono tabular-nums text-[var(--text-primary)] tracking-tight">
              {value}
            </div>
          )}
        </div>

        {subtext && !isUnavailable && (
          <p className="text-xs text-[var(--text-muted)] mt-1.5 leading-relaxed">{subtext}</p>
        )}
      </div>
    </div>
  )
}
