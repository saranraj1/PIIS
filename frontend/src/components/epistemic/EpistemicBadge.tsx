import React from 'react'

export type EpistemicCategory =
  | 'OBSERVED_FACT'
  | 'MODEL_PREDICTION'
  | 'HYPOTHESIS'
  | 'RECOMMENDATION'
  | 'HUMAN_APPROVED_DECISION'
  | 'CONFIRMED_ROOT_CAUSE'
  | 'DERIVED_ESTIMATE'
  | 'COMPUTED_TOPOLOGY'
  | 'APPROVED_POLICY'
  | 'STATISTICAL_INFERENCE'
  | 'HISTORICAL_EVIDENCE'
  | 'REFERENCE_DATA'
  | 'UNKNOWN'

export interface EpistemicBadgeProps {
  category: EpistemicCategory
  label?: string
  suffix?: string
  className?: string
  size?: 'sm' | 'md' | 'lg'
  showIcon?: boolean
}

export const EPISTEMIC_CONFIG: Record<
  EpistemicCategory,
  { label: string; ariaRole: string; icon: string; iconColor: string; styleClass?: string }
> = {
  OBSERVED_FACT: {
    label: '[OBSERVED FACT]',
    ariaRole: 'Empirical observed telemetry or alarm evidence',
    icon: '●',
    iconColor: 'text-emerald-500',
    styleClass: 'bg-[var(--bg-subtle)] text-[var(--text-primary)] border-[var(--border-subtle)]',
  },
  MODEL_PREDICTION: {
    label: '[MODEL PREDICTION]',
    ariaRole: 'Machine learning model predicted classification',
    icon: '◆',
    iconColor: 'text-indigo-400',
    styleClass: 'bg-[var(--bg-subtle)] text-[var(--text-primary)] border-[var(--border-subtle)]',
  },
  HYPOTHESIS: {
    label: '[HYPOTHESIS]',
    ariaRole: 'RAG synthesized candidate root cause (not confirmed)',
    icon: '▲',
    iconColor: 'text-amber-500',
    styleClass: 'bg-[var(--bg-subtle)] text-[var(--text-primary)] border-[var(--border-subtle)]',
  },
  RECOMMENDATION: {
    label: '[RECOMMENDATION]',
    ariaRole: 'Retrieved diagnostic standard operating procedure',
    icon: '▶',
    iconColor: 'text-sky-400',
    styleClass: 'bg-[var(--bg-subtle)] text-[var(--text-primary)] border-[var(--border-subtle)]',
  },
  HUMAN_APPROVED_DECISION: {
    label: '[HUMAN-APPROVED DECISION]',
    ariaRole: 'Authenticated human operator cryptographic approval',
    icon: '✓',
    iconColor: 'text-teal-500',
    styleClass: 'bg-[var(--bg-subtle)] text-[var(--text-primary)] border-[var(--border-subtle)]',
  },
  CONFIRMED_ROOT_CAUSE: {
    label: '[CONFIRMED ROOT CAUSE]',
    ariaRole: 'Post-incident postmortem ground truth (never autonomous)',
    icon: '■',
    iconColor: 'text-rose-500',
    styleClass: 'bg-[var(--bg-subtle)] text-[var(--text-primary)] border-[var(--border-subtle)]',
  },
  DERIVED_ESTIMATE: {
    label: '[DERIVED ESTIMATE]',
    ariaRole: 'Statistically or topologically derived estimation (not directly observed)',
    icon: '≈',
    iconColor: 'text-amber-400',
    styleClass: 'bg-[var(--bg-subtle)] text-[var(--text-primary)] border-[var(--border-subtle)]',
  },
  COMPUTED_TOPOLOGY: {
    label: '[COMPUTED TOPOLOGY]',
    ariaRole: 'Algorithmic topological dependency graph traversal',
    icon: '☊',
    iconColor: 'text-zinc-400',
    styleClass: 'bg-[var(--bg-subtle)] text-[var(--text-primary)] border-[var(--border-subtle)]',
  },
  APPROVED_POLICY: {
    label: '[APPROVED POLICY]',
    ariaRole: 'Deterministic operational policy or standard operating procedure',
    icon: '§',
    iconColor: 'text-zinc-400',
    styleClass: 'bg-[var(--bg-subtle)] text-[var(--text-primary)] border-[var(--border-subtle)]',
  },
  STATISTICAL_INFERENCE: {
    label: '[STATISTICAL INFERENCE]',
    ariaRole: 'Dynamic threshold or ML statistical anomaly inference',
    icon: '∿',
    iconColor: 'text-zinc-400',
    styleClass: 'bg-[var(--bg-subtle)] text-[var(--text-primary)] border-[var(--border-subtle)]',
  },
  HISTORICAL_EVIDENCE: {
    label: '[HISTORICAL EVIDENCE]',
    ariaRole: 'Retrieved historical incident record or runbook',
    icon: '◷',
    iconColor: 'text-zinc-400',
    styleClass: 'bg-[var(--bg-subtle)] text-[var(--text-primary)] border-[var(--border-subtle)]',
  },
  REFERENCE_DATA: {
    label: '[REFERENCE DATA]',
    ariaRole: 'Standardized reference topology (not live carrier infrastructure)',
    icon: '⚙',
    iconColor: 'text-zinc-400',
    styleClass: 'bg-[var(--bg-subtle)] text-[var(--text-primary)] border-[var(--border-subtle)]',
  },
  UNKNOWN: {
    label: '[UNKNOWN]',
    ariaRole: 'Unverified or missing epistemic classification',
    icon: '?',
    iconColor: 'text-zinc-400',
    styleClass: 'bg-[var(--bg-subtle)] text-[var(--text-primary)] border-[var(--border-subtle)]',
  },
}

export const EpistemicBadge: React.FC<EpistemicBadgeProps> = ({
  category,
  label,
  suffix,
  className = '',
  size = 'sm',
  showIcon = true,
}) => {
  const item = EPISTEMIC_CONFIG[category] || EPISTEMIC_CONFIG.OBSERVED_FACT
  const sizeClasses =
    size === 'sm'
      ? 'text-[0.65rem] px-2 py-0.5 tracking-wider'
      : size === 'lg'
      ? 'text-xs px-3 py-1.5 tracking-wide'
      : 'text-xs px-2.5 py-1 tracking-wide'

  const displayLabel = label || item.label

  return (
    <span
      role="status"
      aria-label={`${item.label}: ${item.ariaRole}`}
      className={`inline-flex items-center gap-1 font-mono font-bold uppercase rounded-xs border transition-colors ${sizeClasses} ${item.styleClass} ${className}`}
    >
      {showIcon && (
        <span aria-hidden="true" className={`text-[0.8em] ${item.iconColor}`}>
          {item.icon}
        </span>
      )}
      <span className="text-[var(--text-primary)]">{displayLabel}</span>
      {suffix && (
        <span className="text-[var(--text-muted)] font-sans font-normal lowercase tracking-normal">
          — {suffix}
        </span>
      )}
    </span>
  )
}
