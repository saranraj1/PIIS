import React, { useState } from 'react'
import {
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  ShieldAlert,
  Flame,
} from 'lucide-react'
import type { IncidentHypothesisItem } from '../../api/types'
import { EpistemicBadge } from '../epistemic/EpistemicBadge'

export interface HypothesisAnalysisCardProps {
  hypotheses: IncidentHypothesisItem[]
  onSelectEvidence?: (evidenceId: string) => void
}

export const HypothesisAnalysisCard: React.FC<HypothesisAnalysisCardProps> = ({
  hypotheses = [],
  onSelectEvidence,
}) => {
  const safeHypotheses = Array.isArray(hypotheses) ? hypotheses : []
  const [expandedHypothesisId, setExpandedHypothesisId] = useState<string | null>(
    safeHypotheses.length > 0 ? safeHypotheses[0].hypothesis_id : null
  )

  const toggleExpand = (id: string) => {
    setExpandedHypothesisId(expandedHypothesisId === id ? null : id)
  }

  if (safeHypotheses.length === 0) {
    return (
      <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-8 text-center">
        <div className="inline-flex p-3 rounded-full bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-muted)] mb-3">
          <BrainCircuit className="w-6 h-6" />
        </div>
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">
          No Confident Root Cause Hypothesis
        </h3>
        <p className="text-xs text-[var(--text-muted)] max-w-md mx-auto mt-1 font-mono">
          Engine safely abstained from candidate ranking due to insufficient or contradictory telemetry. Manual NOC diagnostics required.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Supervisory Disclaimer */}
      <div className="flex items-center justify-between text-xs text-[var(--text-muted)] bg-[var(--bg-card)] px-3 py-2 rounded-xs border border-[var(--border-subtle)] font-mono">
        <div className="flex items-center gap-1.5">
          <ShieldAlert className="w-3.5 h-3.5 text-amber-500" />
          <span>Notice: Scores represent heuristic ranking proxies (0.00–1.00), not calibrated probabilities or confirmed root causes.</span>
        </div>
        <EpistemicBadge category="HYPOTHESIS" size="sm" />
      </div>

      {/* Ranked Hypotheses List */}
      <div className="space-y-3">
        {safeHypotheses.map((hyp, index) => {
          const isExpanded = expandedHypothesisId === hyp.hypothesis_id
          const rank = index + 1
          const isPrimary = rank === 1

          const getStatusBadge = (status: string) => {
            switch (status) {
              case 'SUPPORTED':
                return (
                  <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs text-xs font-mono font-medium bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> SUPPORTED
                  </span>
                )
              case 'REJECTED':
                return (
                  <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs text-xs font-mono font-medium bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-500" /> REJECTED
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

          return (
            <div
              key={hyp.hypothesis_id}
              className={`rounded-xs bg-[var(--bg-surface)] border transition-all ${
                isPrimary
                  ? 'border-[var(--text-primary)]/40'
                  : 'border-[var(--border-subtle)] hover:border-[var(--border-subtle)]/80'
              }`}
            >
              {/* Header Accordion Bar */}
              <div
                onClick={() => toggleExpand(hyp.hypothesis_id)}
                className="p-4 cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-3 select-none"
              >
                <div className="flex items-start gap-3">
                  <div
                    className={`w-6 h-6 rounded-full flex items-center justify-center font-mono text-xs font-bold shrink-0 mt-0.5 ${
                      isPrimary
                        ? 'bg-[var(--text-primary)] text-[var(--bg-surface)]'
                        : 'bg-[var(--bg-card)] text-[var(--text-muted)] border border-[var(--border-subtle)]'
                    }`}
                  >
                    #{rank}
                  </div>

                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-[var(--text-primary)]">
                        {hyp.hypothesis_id}
                      </span>
                      {getStatusBadge(hyp.status)}
                      <EpistemicBadge category="MODEL_PREDICTION" size="sm" />
                    </div>

                    <h4 className="text-sm font-semibold text-[var(--text-primary)]">
                      {hyp.description}
                    </h4>
                  </div>
                </div>

                <div className="flex items-center gap-3 self-end sm:self-center">
                  <div
                    className="text-right font-mono"
                    title="Heuristic rank score (0.00–1.00), not a calibrated probability of root cause"
                  >
                    <div className="text-xs text-[var(--text-muted)] uppercase">
                      Heuristic Proxy
                    </div>
                    <div className="text-sm font-mono font-bold text-[var(--text-primary)]">
                      {typeof hyp.confidence_proxy === 'number'
                        ? `${(hyp.confidence_proxy * 100).toFixed(0)}%`
                        : 'N/A'}
                    </div>
                    <div className="text-xs text-[var(--text-muted)]">
                      Not a probability
                    </div>
                  </div>

                  <button
                    aria-label={`Toggle details for ${hyp.hypothesis_id}`}
                    className="p-1 rounded-xs hover:bg-[var(--bg-card)] text-[var(--text-muted)] transition-colors cursor-pointer"
                  >
                    {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Collapsible Deep Details */}
              {isExpanded && (
                <div className="p-4 border-t border-[var(--border-subtle)] bg-[var(--bg-card)]/50 space-y-3.5 text-xs">
                  {/* Confidence Rationale */}
                  <div className="p-2.5 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
                    <div className="font-mono text-xs text-[var(--text-muted)] uppercase font-semibold">
                      Mathematical Rationale & Score Origin
                    </div>
                    <p className="text-xs text-[var(--text-primary)] font-mono leading-relaxed">
                      {hyp.confidence_rationale}
                    </p>
                  </div>

                  {/* Supporting vs Contradicting Evidence Links */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {/* Supporting Evidence */}
                    <div className="p-2.5 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1.5">
                      <div className="font-mono text-xs text-[var(--text-primary)] uppercase font-semibold flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                        <span>Supporting Evidence ({hyp.supporting_evidence_ids.length})</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {hyp.supporting_evidence_ids.length > 0 ? (
                          hyp.supporting_evidence_ids.map((evId) => (
                            <button
                              key={evId}
                              onClick={(e) => {
                                e.stopPropagation()
                                onSelectEvidence?.(evId)
                              }}
                              className="font-mono text-xs px-2 py-0.5 rounded-xs bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)] hover:bg-[var(--bg-surface)] transition-colors inline-flex items-center gap-1 cursor-pointer"
                              title={`Inspect evidence ${evId}`}
                            >
                              <span>{evId}</span>
                              <ExternalLink className="w-2.5 h-2.5 text-[var(--text-muted)]" />
                            </button>
                          ))
                        ) : (
                          <span className="text-xs text-[var(--text-muted)]">
                            No direct corroborating signals linked
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Contradicting Evidence */}
                    <div className="p-2.5 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1.5">
                      <div className="font-mono text-xs text-[var(--text-primary)] uppercase font-semibold flex items-center gap-1.5">
                        <Flame className="w-3.5 h-3.5 text-rose-500" />
                        <span>Contradicting Evidence ({hyp.contradicting_evidence_ids.length})</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {hyp.contradicting_evidence_ids.length > 0 ? (
                          hyp.contradicting_evidence_ids.map((evId) => (
                            <button
                              key={evId}
                              onClick={(e) => {
                                e.stopPropagation()
                                onSelectEvidence?.(evId)
                              }}
                              className="font-mono text-xs px-2 py-0.5 rounded-xs bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)] hover:bg-[var(--bg-surface)] transition-colors inline-flex items-center gap-1 cursor-pointer"
                              title={`Inspect contradictory signal ${evId}`}
                            >
                              <span>{evId}</span>
                              <ExternalLink className="w-2.5 h-2.5 text-[var(--text-muted)]" />
                            </button>
                          ))
                        ) : (
                          <span className="text-xs text-[var(--text-muted)]">
                            Zero contradictory signals recorded
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Recommended Verification Steps */}
                  {hyp.recommended_verification_steps && hyp.recommended_verification_steps.length > 0 && (
                    <div className="space-y-1">
                      <div className="font-mono text-xs text-[var(--text-muted)] uppercase font-semibold">
                        Recommended Non-Destructive Verification Steps
                      </div>
                      <ul className="list-disc list-inside space-y-0.5 text-xs text-[var(--text-primary)]">
                        {hyp.recommended_verification_steps.map((step, idx) => (
                          <li key={idx}>{step}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Alternative Explanations */}
                  {hyp.alternative_explanations && hyp.alternative_explanations.length > 0 && (
                    <div className="space-y-1 pt-1 border-t border-[var(--border-subtle)]">
                      <div className="font-mono text-xs text-[var(--text-muted)] uppercase font-semibold">
                        Plausible Competing Explanations
                      </div>
                      <ul className="list-disc list-inside space-y-0.5 text-xs text-[var(--text-muted)]">
                        {hyp.alternative_explanations.map((alt, idx) => (
                          <li key={idx}>{alt}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
