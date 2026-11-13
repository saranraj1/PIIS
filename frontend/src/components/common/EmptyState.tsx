import React from 'react'
import { Inbox } from 'lucide-react'

interface EmptyStateProps {
  title?: string
  description?: string
  actionLabel?: string
  onAction?: () => void
  icon?: React.ReactNode
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = 'No Data Found',
  description = 'No operational records matched the query parameters.',
  actionLabel,
  onAction,
  icon,
}) => {
  return (
    <div
      role="status"
      className="p-8 text-center rounded-sm bg-[var(--bg-surface)] border border-[var(--border-subtle)] flex flex-col items-center justify-center gap-2 transition-colors"
    >
      <div className="p-3 rounded-xs bg-[var(--bg-subtle)] text-[var(--text-muted)] border border-[var(--border-subtle)]">
        {icon || <Inbox className="w-6 h-6" />}
      </div>
      <h3 className="text-sm font-semibold text-[var(--text-primary)] mt-1">{title}</h3>
      <p className="text-xs text-[var(--text-muted)] max-w-sm">{description}</p>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="mt-3 px-3 py-1.5 rounded-xs text-xs font-medium bg-[var(--bg-subtle)] hover:bg-[var(--border-subtle)] border border-[var(--border-subtle)] text-[var(--text-primary)] transition-colors font-mono"
        >
          {actionLabel}
        </button>
      )}
    </div>
  )
}
