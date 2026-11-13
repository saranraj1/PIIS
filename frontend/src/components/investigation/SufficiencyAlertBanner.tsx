import React from 'react'
import {
  ShieldCheck,
  AlertTriangle,
  ClockAlert,
  Flame,
  Info,
} from 'lucide-react'
import { EpistemicBadge } from '../epistemic/EpistemicBadge'

export interface SufficiencyAlertBannerProps {
  isSufficient: boolean
  isTransientEvent?: boolean
  missingEvidence?: string[]
  contradictions?: string[]
  staleEvidence?: string[]
}

export const SufficiencyAlertBanner: React.FC<SufficiencyAlertBannerProps> = ({
  isSufficient,
  isTransientEvent = false,
  missingEvidence = [],
  contradictions = [],
  staleEvidence = [],
}) => {
  const hasDefects =
    !isSufficient ||
    isTransientEvent ||
    missingEvidence.length > 0 ||
    contradictions.length > 0 ||
    staleEvidence.length > 0

  if (!hasDefects && isSufficient) {
    return (
      <div className="rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] p-3.5 flex items-center justify-between gap-3 text-xs transition-colors">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] text-emerald-500">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div>
            <div className="font-bold text-[var(--text-primary)] flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                EVIDENCE SUFFICIENT & FRESH
              </span>
              <span className="text-xs font-mono font-normal text-[var(--text-muted)]">
                (All required telemetry, alarms, and topology signals present)
              </span>
            </div>
            <p className="text-xs text-[var(--text-muted)] mt-0.5 leading-relaxed">
              Engine has verified cross-correlation across telemetry and alarms. Safe for decision-support analysis.
            </p>
          </div>
        </div>
        <EpistemicBadge category="OBSERVED_FACT" size="sm" />
      </div>
    )
  }

  return (
    <div className="rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] p-4 space-y-3 text-xs">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <div className="p-1.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] text-amber-500 mt-0.5 shrink-0">
            <AlertTriangle className="w-4 h-4" />
          </div>
          <div className="space-y-1">
            <div className="font-semibold text-[var(--text-primary)] flex items-center gap-2">
              <span>SAFE ABSTENTION ENFORCED — EVIDENCE LIMITATIONS DETECTED</span>
              <EpistemicBadge category="HYPOTHESIS" size="sm" />
            </div>
            <p className="text-xs text-[var(--text-muted)] leading-relaxed">
              The investigation engine identifies data sufficiency, staleness, or contradictory signals. Hypotheses below are provisional and unconfirmed.
            </p>
          </div>
        </div>
      </div>

      {/* Granular Warning Badges & Lists */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2 border-t border-[var(--border-subtle)] font-mono text-xs">
        {/* Missing Evidence Details */}
        {missingEvidence.length > 0 && (
          <div className="space-y-1 bg-[var(--bg-card)] p-2.5 rounded-xs border border-[var(--border-subtle)]">
            <div className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
              <Info className="w-3.5 h-3.5 text-amber-500" />
              <span>Missing Signals ({missingEvidence.length})</span>
            </div>
            <ul className="list-disc list-inside space-y-0.5 text-[var(--text-secondary)]">
              {missingEvidence.map((item, idx) => (
                <li key={idx} className="truncate" title={item}>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Stale Telemetry Details */}
        {staleEvidence.length > 0 && (
          <div className="space-y-1 bg-[var(--bg-card)] p-2.5 rounded-xs border border-[var(--border-subtle)]">
            <div
              className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5"
              title="Evaluated against backend freshness policy (default UI alert threshold: 3600s for probe telemetry)"
            >
              <ClockAlert className="w-3.5 h-3.5 text-rose-500" />
              <span>Stale Telemetry (Policy &gt;3600s) ({staleEvidence.length})</span>
            </div>
            <ul className="list-disc list-inside space-y-0.5 text-[var(--text-secondary)]">
              {staleEvidence.map((item, idx) => (
                <li key={idx} className="truncate" title={item}>
                  {item}
                </li>
              ))}
            </ul>
            <div className="text-[0.62rem] text-[var(--text-muted)] mt-0.5 font-mono">
              * Evaluated per-source policy (3600s real-time probe baseline)
            </div>
          </div>
        )}

        {/* Contradictory Signals */}
        {contradictions.length > 0 && (
          <div className="space-y-1 bg-[var(--bg-card)] p-2.5 rounded-xs border border-[var(--border-subtle)]">
            <div className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
              <Flame className="w-3.5 h-3.5 text-rose-500" />
              <span>Contradictory Signals ({contradictions.length})</span>
            </div>
            <ul className="list-disc list-inside space-y-0.5 text-[var(--text-secondary)]">
              {contradictions.map((item, idx) => (
                <li key={idx} className="truncate" title={item}>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {isTransientEvent && (
        <div className="text-[0.7rem] font-mono text-[var(--text-primary)] bg-[var(--bg-subtle)] px-2.5 py-1 rounded-xs border border-[var(--border-subtle)]">
          * Notice: Anomaly engine flags this incident pattern as a potential self-clearing transient spike.
        </div>
      )}
    </div>
  )
}
