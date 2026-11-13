import React from 'react'
import { EpistemicBadge } from './EpistemicBadge'

export const EpistemicLegend: React.FC = () => {
  return (
    <div
      aria-label="Epistemic Classification Standards"
      className="bg-[var(--bg-subtle)] border-b border-[var(--border-subtle)] px-4 py-1 flex items-center justify-between text-xs font-mono"
    >
      <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
        <span className="text-[var(--text-muted)] font-semibold text-[0.65rem] uppercase shrink-0">
          Standards:
        </span>
        <div className="flex items-center gap-1.5 shrink-0">
          <EpistemicBadge category="OBSERVED_FACT" size="sm" />
          <EpistemicBadge category="MODEL_PREDICTION" size="sm" />
          <EpistemicBadge category="HYPOTHESIS" size="sm" />
          <EpistemicBadge category="RECOMMENDATION" size="sm" />
          <EpistemicBadge category="HUMAN_APPROVED_DECISION" size="sm" />
          <EpistemicBadge category="CONFIRMED_ROOT_CAUSE" size="sm" />
        </div>
      </div>
    </div>
  )
}
