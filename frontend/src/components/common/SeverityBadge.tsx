import React from 'react'
import type { IncidentSeverity } from '../../api/types'

interface SeverityBadgeProps {
  severity: IncidentSeverity | string
  size?: 'sm' | 'md'
  showIcon?: boolean
}

const SEVERITY_CONFIG: Record<
  string,
  { label: string; dotClass: string }
> = {
  CRITICAL: {
    label: 'CRITICAL',
    dotClass: 'bg-rose-500',
  },
  MAJOR: {
    label: 'MAJOR',
    dotClass: 'bg-amber-500',
  },
  MINOR: {
    label: 'MINOR',
    dotClass: 'bg-sky-500',
  },
  WARNING: {
    label: 'WARNING',
    dotClass: 'bg-yellow-500',
  },
  UNKNOWN: {
    label: 'UNKNOWN',
    dotClass: 'bg-zinc-400',
  },
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({
  severity,
  size = 'sm',
  showIcon = true,
}) => {
  const norm = (severity || 'UNKNOWN').toUpperCase()
  const cfg = SEVERITY_CONFIG[norm] || SEVERITY_CONFIG.UNKNOWN

  const sizeClasses =
    size === 'sm'
      ? 'text-xs px-2 py-0.5 tracking-wider'
      : 'text-xs px-2.5 py-1 tracking-wide'

  return (
    <span
      role="status"
      aria-label={`Severity: ${cfg.label}`}
      className={`inline-flex items-center gap-1.5 font-mono font-medium uppercase rounded-xs border border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[var(--text-primary)] transition-colors ${sizeClasses}`}
    >
      {showIcon && <span className={`w-1.5 h-1.5 rounded-full ${cfg.dotClass}`} aria-hidden="true" />}
      <span>{cfg.label}</span>
    </span>
  )
}
