import React, { useState } from 'react'
import {
  FileText,
  Activity,
  Bell,
  Network,
  BookOpen,
  History,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  Clock,
  Filter,
} from 'lucide-react'
import type { InvestigationEvidenceItem } from '../../api/types'
import { EpistemicBadge } from '../epistemic/EpistemicBadge'

export interface EvidenceRegisterCardProps {
  evidenceItems: InvestigationEvidenceItem[]
  highlightedEvidenceId?: string | null
}

export const EvidenceRegisterCard: React.FC<EvidenceRegisterCardProps> = ({
  evidenceItems,
  highlightedEvidenceId,
}) => {
  const [selectedType, setSelectedType] = useState<string>('ALL')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id)
  }

  // Filter evidence by type
  const filteredItems =
    selectedType === 'ALL'
      ? evidenceItems
      : evidenceItems.filter((item) => item.evidence_type === selectedType)

  const getEvidenceIcon = (type: string) => {
    switch (type) {
      case 'TELEMETRY_ANOMALY':
        return <Activity className="w-4 h-4 text-[var(--text-muted)]" />
      case 'ALARM_CLUSTER':
        return <Bell className="w-4 h-4 text-[var(--text-muted)]" />
      case 'TOPOLOGY_IMPACT':
        return <Network className="w-4 h-4 text-[var(--text-muted)]" />
      case 'APPROVED_RUNBOOK':
        return <BookOpen className="w-4 h-4 text-[var(--text-muted)]" />
      case 'HISTORICAL_CASE':
        return <History className="w-4 h-4 text-[var(--text-muted)]" />
      default:
        return <FileText className="w-4 h-4 text-[var(--text-muted)]" />
    }
  }

  const getTrustBadge = (trust: string) => {
    switch (trust) {
      case 'HIGH_TRUST_APPROVED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs text-xs font-mono font-medium bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> HIGH TRUST
          </span>
        )
      case 'MEDIUM_TRUST_VERIFIED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs text-xs font-mono font-medium bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500" /> VERIFIED
          </span>
        )
      case 'BENCHMARK_ONLY':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs text-xs font-mono font-medium bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
            <span className="w-1.5 h-1.5 rounded-full bg-zinc-400" /> BENCHMARK ONLY
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs text-xs font-mono font-medium bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" /> UNVERIFIED
          </span>
        )
    }
  }

  const getEpistemicCategory = (type: string) => {
    if (type === 'TELEMETRY_ANOMALY' || type === 'ALARM_CLUSTER' || type === 'TICKET_METADATA') {
      return 'OBSERVED_FACT'
    }
    if (type === 'ML_CLASSIFICATION' || type === 'SEVERITY_PREDICTION') {
      return 'MODEL_PREDICTION'
    }
    if (type === 'APPROVED_RUNBOOK') {
      return 'APPROVED_POLICY'
    }
    return 'CORROBORATED_FINDING'
  }

  // Extract unique types for filter bar
  const uniqueTypes = Array.from(new Set(evidenceItems.map((e) => e.evidence_type)))

  if (evidenceItems.length === 0) {
    return (
      <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-8 text-center">
        <FileText className="w-6 h-6 text-[var(--text-muted)] mx-auto mb-2" />
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">
          No Correlated Evidence Registered
        </h3>
        <p className="text-xs text-[var(--text-muted)] max-w-md mx-auto mt-1 font-mono">
          No telemetry anomaly time-series, alarm events, or approved runbooks match this incident context.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Evidence Integrity Axiom Notice */}
      <div className="rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] p-3 text-xs text-[var(--text-muted)] flex items-center justify-between gap-3 font-mono">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-3.5 h-3.5 text-[var(--text-muted)] shrink-0" />
          <span>
            Integrity Guard: Do not infer verification from the mere presence of an evidence record. Every item requires source validation.
          </span>
        </div>
        <EpistemicBadge category="OBSERVED_FACT" size="sm" />
      </div>

      {/* Filter Chips Bar */}
      <div className="flex flex-wrap items-center gap-2 pb-1 border-b border-[var(--border-subtle)] text-xs">
        <span className="font-mono text-xs text-[var(--text-muted)] uppercase flex items-center gap-1 mr-1">
          <Filter className="w-3 h-3 text-[var(--text-muted)]" /> Type:
        </span>
        <button
          onClick={() => setSelectedType('ALL')}
          className={`px-2.5 py-1 rounded-xs text-xs font-mono font-medium transition-colors cursor-pointer ${
            selectedType === 'ALL'
              ? 'bg-[var(--text-primary)] text-[var(--bg-surface)] font-semibold'
              : 'bg-[var(--bg-card)] text-[var(--text-muted)] hover:text-[var(--text-primary)] border border-[var(--border-subtle)]'
          }`}
        >
          ALL ({evidenceItems.length})
        </button>
        {uniqueTypes.map((type) => (
          <button
            key={type}
            onClick={() => setSelectedType(type)}
            className={`px-2.5 py-1 rounded-xs text-xs font-mono font-medium transition-colors cursor-pointer ${
              selectedType === type
                ? 'bg-[var(--text-primary)] text-[var(--bg-surface)] font-semibold'
                : 'bg-[var(--bg-card)] text-[var(--text-muted)] hover:text-[var(--text-primary)] border border-[var(--border-subtle)]'
            }`}
          >
            {type} ({evidenceItems.filter((e) => e.evidence_type === type).length})
          </button>
        ))}
      </div>

      {/* Evidence Cards List */}
      <div className="space-y-3">
        {filteredItems.map((item) => {
          const isHighlighted = highlightedEvidenceId === item.evidence_id
          const isExpanded = expandedId === item.evidence_id
          const epistemicCat = getEpistemicCategory(item.evidence_type)

          return (
            <div
              key={item.evidence_id}
              id={`evidence-${item.evidence_id}`}
              className={`rounded-xs bg-[var(--bg-surface)] border transition-all ${
                isHighlighted
                  ? 'border-[var(--text-primary)] ring-1 ring-[var(--text-primary)]/20'
                  : 'border-[var(--border-subtle)] hover:border-[var(--border-subtle)]/80'
              }`}
            >
              <div
                onClick={() => toggleExpand(item.evidence_id)}
                className="p-3.5 cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-3 select-none"
              >
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] shrink-0 mt-0.5">
                    {getEvidenceIcon(item.evidence_type)}
                  </div>

                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-[var(--text-primary)]">
                        {item.evidence_id}
                      </span>
                      <span className="text-xs font-mono px-2 py-0.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-muted)]">
                        {item.evidence_type}
                      </span>
                      {getTrustBadge(item.trust_classification)}
                      <EpistemicBadge category={epistemicCat} size="sm" />
                    </div>

                    <p className="text-xs font-medium text-[var(--text-primary)]">
                      {item.content_summary}
                    </p>

                    <div className="flex items-center gap-3 text-xs text-[var(--text-muted)] font-mono">
                      <span>Ref: {item.source_ref}</span>
                      <span>•</span>
                      <span>Domain: {item.domain}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 self-end sm:self-center">
                  <div className="text-right text-xs font-mono text-[var(--text-muted)] flex items-center gap-1">
                    <Clock className="w-3 h-3 text-[var(--text-muted)]" />
                    <span>{item.observed_at ? new Date(item.observed_at).toLocaleTimeString() : 'N/A'}</span>
                  </div>

                  <button
                    aria-label={`Toggle raw metadata for ${item.evidence_id}`}
                    className="p-1 rounded-xs hover:bg-[var(--bg-card)] text-[var(--text-muted)] transition-colors"
                  >
                    {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Collapsible Metadata Drawer */}
              {isExpanded && (
                <div className="p-4 border-t border-[var(--border-subtle)] bg-[var(--bg-card)]/50 space-y-2">
                  <div className="flex items-center justify-between text-xs font-mono text-[var(--text-muted)] uppercase">
                    <span>Raw Metadata &amp; Cryptographic Provenance</span>
                    <span>Source: {item.source_ref}</span>
                  </div>
                  <pre className="p-3 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] font-mono text-xs text-[var(--text-primary)] overflow-x-auto leading-relaxed">
                    {JSON.stringify(item.raw_metadata || {}, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
