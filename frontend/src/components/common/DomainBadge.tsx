import React from 'react'
import type { NetworkDomain } from '../../api/types'

interface DomainBadgeProps {
  domain: NetworkDomain | string
  size?: 'sm' | 'md'
}

const DOMAIN_CONFIG: Record<
  string,
  { label: string; dotClass: string }
> = {
  RAN: {
    label: 'RAN',
    dotClass: 'bg-sky-500',
  },
  '5G_CORE': {
    label: '5G CORE',
    dotClass: 'bg-purple-500',
  },
  TRANSPORT: {
    label: 'TRANSPORT',
    dotClass: 'bg-emerald-500',
  },
  SERVICE: {
    label: 'SERVICE',
    dotClass: 'bg-zinc-400',
  },
  CROSS_DOMAIN: {
    label: 'CROSS-DOMAIN',
    dotClass: 'bg-amber-500',
  },
  UNKNOWN: {
    label: 'UNKNOWN',
    dotClass: 'bg-zinc-400',
  },
}

export const DomainBadge: React.FC<DomainBadgeProps> = ({ domain, size = 'sm' }) => {
  const norm = (domain || 'UNKNOWN').toUpperCase()
  const cfg = DOMAIN_CONFIG[norm] || DOMAIN_CONFIG.UNKNOWN

  const sizeClasses =
    size === 'sm'
      ? 'text-[0.65rem] px-1.5 py-0.5 tracking-wider'
      : 'text-xs px-2 py-1 tracking-wide'

  return (
    <span
      role="status"
      aria-label={`Network Domain: ${cfg.label}`}
      className={`inline-flex items-center gap-1.5 font-mono font-medium uppercase rounded-xs border border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[var(--text-primary)] transition-colors ${sizeClasses}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dotClass}`} aria-hidden="true" />
      <span>{cfg.label}</span>
    </span>
  )
}
