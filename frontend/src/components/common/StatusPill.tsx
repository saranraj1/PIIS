import React from 'react'

export type OperationalStateType =
  | 'HEALTHY'
  | 'READY'
  | 'DEGRADED'
  | 'UNAVAILABLE'
  | 'UNKNOWN'
  | 'SIMULATED'
  | 'EXTERNALLY_UNVERIFIED'
  | 'PENDING_REVIEW'
  | 'APPROVED'
  | 'REJECTED'
  | 'MODIFIED'

interface StatusPillProps {
  state: OperationalStateType | string
  label?: string
  size?: 'sm' | 'md'
}

const STATE_CONFIG: Record<
  string,
  { label: string; dotClass: string }
> = {
  HEALTHY: {
    label: 'HEALTHY',
    dotClass: 'bg-emerald-500',
  },
  READY: {
    label: 'READY',
    dotClass: 'bg-emerald-500',
  },
  DEGRADED: {
    label: 'DEGRADED',
    dotClass: 'bg-amber-500',
  },
  UNAVAILABLE: {
    label: 'UNAVAILABLE',
    dotClass: 'bg-rose-500',
  },
  SIMULATED: {
    label: 'SIMULATED',
    dotClass: 'bg-zinc-400',
  },
  EXTERNALLY_UNVERIFIED: {
    label: 'EXTERNALLY UNVERIFIED',
    dotClass: 'bg-zinc-400',
  },
  PENDING_REVIEW: {
    label: 'PENDING REVIEW',
    dotClass: 'bg-amber-500',
  },
  APPROVED: {
    label: 'APPROVED',
    dotClass: 'bg-emerald-500',
  },
  REJECTED: {
    label: 'REJECTED',
    dotClass: 'bg-rose-500',
  },
  MODIFIED: {
    label: 'MODIFIED',
    dotClass: 'bg-zinc-400',
  },
  UNKNOWN: {
    label: 'UNKNOWN',
    dotClass: 'bg-zinc-400',
  },
}

export const StatusPill: React.FC<StatusPillProps> = ({ state, label, size = 'sm' }) => {
  const norm = (state || 'UNKNOWN').toUpperCase().replace(/[\s-]/g, '_')
  const cfg = STATE_CONFIG[norm] || STATE_CONFIG.UNKNOWN

  const displayLabel = label || cfg.label
  const sizeClasses =
    size === 'sm'
      ? 'text-xs px-2 py-0.5 tracking-wider'
      : 'text-xs px-2.5 py-1 tracking-wide'

  return (
    <span
      role="status"
      aria-label={`Operational state: ${displayLabel}`}
      className={`inline-flex items-center gap-1.5 font-mono font-medium uppercase rounded-xs border border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[var(--text-primary)] transition-colors ${sizeClasses}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dotClass}`} aria-hidden="true" />
      <span>{displayLabel}</span>
    </span>
  )
}
