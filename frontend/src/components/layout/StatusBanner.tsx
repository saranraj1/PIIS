import React from 'react'
import { ShieldAlert } from 'lucide-react'

export const StatusBanner: React.FC = () => {
  return (
    <aside
      aria-label="Operational Boundary Status"
      className="bg-[var(--bg-subtle)] border-b border-[var(--border-subtle)] px-4 py-1 text-[0.75rem] text-[var(--text-secondary)] flex flex-wrap items-center justify-between gap-2 transition-colors"
    >
      <div className="flex items-center gap-2">
        <ShieldAlert className="w-3.5 h-3.5 text-[var(--text-muted)] shrink-0" aria-hidden="true" />
        <span>
          <strong className="text-[var(--text-primary)] font-semibold">Operational Boundary:</strong> Read-Only
          Decision Support
        </span>
        <span className="hidden sm:inline text-[var(--border-strong)]">|</span>
        <span className="hidden sm:inline">
          <strong className="text-[var(--text-primary)] font-semibold">Autonomous Production Mutations:</strong>{' '}
          <span className="inline-flex items-center gap-1 font-mono font-bold text-[var(--text-primary)]">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500 inline-block" />
            STRICTLY PROHIBITED
          </span>{' '}
          (Hard-Locked)
        </span>
      </div>
      <div className="flex items-center gap-2 font-mono text-xs text-[var(--text-muted)]">
        <span>Deterministic Controls Active</span>
      </div>
    </aside>
  )
}
