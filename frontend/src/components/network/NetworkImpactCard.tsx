import React from 'react'
import { Activity, ShieldAlert, Users, AlertCircle } from 'lucide-react'
import { EpistemicBadge } from '../epistemic/EpistemicBadge'
import { DomainBadge } from '../common/DomainBadge'
import type { NetworkImpactResponse } from '../../api/types'

interface NetworkImpactCardProps {
  impact?: NetworkImpactResponse
  isLoading: boolean
  targetElement: string | null
  onSelectElement?: (elementId: string) => void
}

export const NetworkImpactCard: React.FC<NetworkImpactCardProps> = ({
  impact,
  isLoading,
  targetElement,
  onSelectElement,
}) => {
  if (isLoading) {
    return (
      <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-6 space-y-4 animate-pulse">
        <div className="h-6 w-48 bg-[var(--bg-card)] rounded-xs" />
        <div className="h-20 bg-[var(--bg-card)] rounded-xs" />
      </div>
    )
  }

  if (!impact) {
    return (
      <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-6 text-center space-y-2">
        <ShieldAlert className="w-8 h-8 text-[var(--text-muted)] mx-auto opacity-50" />
        <h4 className="text-sm font-semibold text-[var(--text-primary)]">No Impact Assessment Loaded</h4>
        <p className="text-xs text-[var(--text-muted)] max-w-sm mx-auto">
          Select an element in the topology graph or specify an incident to evaluate cascading blast radius.
        </p>
      </div>
    )
  }

  const renderRiskBadge = (level: string, score: number) => {
    let dotColor = 'bg-emerald-500'
    const lvl = level.toUpperCase()
    if (lvl === 'CRITICAL' || lvl === 'MAJOR') dotColor = 'bg-rose-500'
    else if (lvl === 'MODERATE') dotColor = 'bg-amber-500'

    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-mono font-medium rounded-xs border border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[var(--text-primary)]">
        <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
        {level} RISK ({(score * 100).toFixed(0)}%)
      </span>
    )
  }

  return (
    <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-[var(--text-muted)]" />
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            Network Impact & Blast Radius Assessment
          </h3>
          {targetElement && (
            <span className="font-mono text-xs px-2 py-0.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-primary)]">
              {targetElement}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {renderRiskBadge(impact.severity_risk_level, impact.risk_score)}
          <EpistemicBadge category="DERIVED_ESTIMATE" size="sm" />
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {/* Total Impacted Elements */}
        <div className="p-3 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)]">
          <div className="text-xs text-[var(--text-muted)] font-medium">Total Blast Radius</div>
          <div className="mt-1 text-xl font-mono font-bold text-[var(--text-primary)]">
            {impact.total_element_count} <span className="text-xs font-normal text-[var(--text-muted)]">elements</span>
          </div>
          <div className="mt-1 flex items-center gap-1.5 text-xs text-[var(--text-muted)] font-mono">
            <span>{impact.direct_elements.length} direct</span>
            <span>•</span>
            <span>{impact.inferred_elements.length} cascading</span>
          </div>
        </div>

        {/* Affected Domains */}
        <div className="p-3 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)]">
          <div className="text-xs text-[var(--text-muted)] font-medium">Cross-Domain Spread</div>
          <div className="mt-1 text-xl font-mono font-bold text-[var(--text-primary)]">
            {impact.affected_domains.length} <span className="text-xs font-normal text-[var(--text-muted)]">domains</span>
          </div>
          <div className="mt-1 flex flex-wrap gap-1">
            {impact.affected_domains.map((dom) => (
              <DomainBadge key={dom} domain={dom} size="sm" />
            ))}
          </div>
        </div>

        {/* Estimated Affected Subscribers */}
        <div className="p-3 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)]">
          <div className="text-xs text-[var(--text-muted)] font-medium">Subscribers at Risk</div>
          <div className="mt-1 text-xl font-mono font-bold text-[var(--text-primary)] tabular-nums">
            {impact.estimated_affected_subscribers !== null && impact.estimated_affected_subscribers !== undefined
              ? (impact.estimated_affected_subscribers === 0
                  ? '0'
                  : impact.estimated_affected_subscribers.toLocaleString())
              : 'NOT AVAILABLE (UNKNOWN)'}
          </div>
          <div className="mt-1 flex items-center gap-1 text-xs text-[var(--text-muted)] font-mono">
            <Users className="w-3 h-3 text-[var(--text-muted)]" />
            <span>
              {impact.estimated_affected_subscribers !== null && impact.estimated_affected_subscribers !== undefined
                ? (impact.estimated_affected_subscribers === 0
                    ? 'Zero nominal capacity modeled'
                    : 'Nominal Topology Capacity')
                : 'No subscriber mapping registered'}
            </span>
          </div>
        </div>
      </div>

      {/* Cascading Elements List */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs font-medium text-[var(--text-muted)]">
          <span>Cascading Impact Breakdown:</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
          {/* Direct Elements */}
          <div className="p-3 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-[var(--text-primary)]">Direct Affected Elements</span>
              <EpistemicBadge category="OBSERVED_FACT" size="sm" />
            </div>
            <div className="flex flex-wrap gap-1">
              {impact.direct_elements.map((el) => (
                <button
                  key={el}
                  onClick={() => onSelectElement?.(el)}
                  className="px-2 py-0.5 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] font-mono text-xs text-[var(--text-primary)] hover:border-[var(--text-primary)] cursor-pointer"
                >
                  {el}
                </button>
              ))}
            </div>
          </div>

          {/* Inferred Cascading Elements */}
          <div className="p-3 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-[var(--text-primary)]">Inferred Downstream Cascade</span>
              <EpistemicBadge category="DERIVED_ESTIMATE" size="sm" />
            </div>
            <div className="flex flex-wrap gap-1">
              {impact.inferred_elements.length === 0 ? (
                <span className="text-xs text-[var(--text-muted)] italic">No downstream cascade detected</span>
              ) : (
                impact.inferred_elements.map((el) => (
                  <button
                    key={el}
                    onClick={() => onSelectElement?.(el)}
                    className="px-2 py-0.5 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] font-mono text-xs text-[var(--text-primary)] hover:border-[var(--text-primary)] cursor-pointer"
                  >
                    {el}
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Epistemic Grounding Disclaimer */}
      {impact.subscriber_impact_basis ? (
        <div className="p-2.5 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] flex items-start gap-2 text-xs text-[var(--text-secondary)]">
          <AlertCircle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <EpistemicBadge category="DERIVED_ESTIMATE" size="sm" />
              <span className="font-semibold text-[var(--text-primary)]">Epistemic Grounding Notice</span>
            </div>
            <div className="text-[var(--text-muted)] leading-relaxed">{impact.subscriber_impact_basis}</div>
          </div>
        </div>
      ) : (
        <div className="p-2.5 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] flex items-start gap-2 text-xs text-[var(--text-muted)]">
          <AlertCircle className="w-4 h-4 text-zinc-400 shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <EpistemicBadge category="UNKNOWN" size="sm" />
              <span className="font-semibold text-[var(--text-primary)]">Epistemic Limitation Notice</span>
            </div>
            <div className="leading-relaxed">Direct subscriber-to-element mapping is not monitored for this element type. Subscriber impact is not available.</div>
          </div>
        </div>
      )}
    </div>
  )
}
