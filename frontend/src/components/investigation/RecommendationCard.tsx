import React from 'react'
import { useNavigate } from 'react-router-dom'
import {
  FileCheck2,
  ExternalLink,
  UserCheck,
  Lock,
} from 'lucide-react'
import type { DiagnosticRecommendationItem } from '../../api/types'
import { EpistemicBadge } from '../epistemic/EpistemicBadge'

export interface RecommendationCardProps {
  recommendations: DiagnosticRecommendationItem[]
  incidentId: string
  onSelectEvidence?: (evidenceId: string) => void
}

export const RecommendationCard: React.FC<RecommendationCardProps> = ({
  recommendations,
  incidentId,
  onSelectEvidence,
}) => {
  const navigate = useNavigate()

  const handleNavigateReview = (recId: string) => {
    navigate(`/review?incident_id=${incidentId}&recommendation_id=${recId}`)
  }

  const getRiskBadge = (risk: string) => {
    switch (risk) {
      case 'READ_ONLY_SAFE':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs text-xs font-mono font-medium bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> READ ONLY SAFE
          </span>
        )
      case 'LOW_OBSERVABILITY':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs text-xs font-mono font-medium bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500" /> LOW OBSERVABILITY
          </span>
        )
      case 'DISRUPTIVE_AUDIT':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs text-xs font-mono font-medium bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" /> DISRUPTIVE AUDIT
          </span>
        )
      case 'HIGH_RISK_MANUAL':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs text-xs font-mono font-medium bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500" /> HIGH RISK MANUAL
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs text-xs font-mono font-medium bg-[var(--bg-subtle)] text-[var(--text-muted)] border border-[var(--border-subtle)]">
            {risk}
          </span>
        )
    }
  }

  const getApprovalStatusBadge = (status: string) => {
    switch (status) {
      case 'APPROVED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs text-xs font-mono font-medium bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> APPROVED
          </span>
        )
      case 'REJECTED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs text-xs font-mono font-medium bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500" /> REJECTED
          </span>
        )
      case 'MODIFIED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs text-xs font-mono font-medium bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-500" /> MODIFIED
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs text-xs font-mono font-medium bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" /> PENDING REVIEW
          </span>
        )
    }
  }

  if (recommendations.length === 0) {
    return (
      <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-8 text-center">
        <FileCheck2 className="w-6 h-6 text-[var(--text-muted)] mx-auto mb-2" />
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">
          No Diagnostic Recommendations Generated
        </h3>
        <p className="text-xs text-[var(--text-muted)] max-w-md mx-auto mt-1 font-mono">
          No runbook procedures mapped to this incident. Safe abstention enforced.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Read-Only Safety Strip */}
      <div className="rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] p-3 text-xs text-[var(--text-muted)] flex items-center justify-between gap-3 font-mono">
        <div className="flex items-center gap-2">
          <Lock className="w-3.5 h-3.5 text-amber-500 shrink-0" />
          <span>
            Advisory Boundary: PIIS provides evidence-grounded recommendations. Existing authorized operational workflows remain responsible for execution. PIIS cannot execute commands or mutate network configurations.
          </span>
        </div>
        <EpistemicBadge category="APPROVED_POLICY" size="sm" />
      </div>

      {/* Recommendations Cards List */}
      <div className="space-y-3">
        {recommendations.map((rec) => {
          const isPending = rec.approval_status === 'PENDING_REVIEW'
          const isApproved = rec.approval_status === 'APPROVED'

          return (
            <div
              key={rec.recommendation_id}
              className={`rounded-xs bg-[var(--bg-surface)] border p-4 space-y-3 transition-colors ${
                isPending
                  ? 'border-amber-500/30'
                  : isApproved
                  ? 'border-emerald-500/30'
                  : 'border-[var(--border-subtle)]'
              }`}
            >
              {/* Header: ID + Runbook + Status */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 pb-2.5 border-b border-[var(--border-subtle)]">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs font-semibold text-[var(--text-primary)]">
                    {rec.recommendation_id}
                  </span>
                  <span className="font-mono text-xs px-2 py-0.5 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--text-primary)]">
                    Runbook: {rec.source_runbook_id}
                  </span>
                  {getRiskBadge(rec.risk_classification)}
                  {getApprovalStatusBadge(rec.approval_status)}
                </div>

                <div className="flex items-center gap-2 self-end sm:self-center">
                  <EpistemicBadge category="APPROVED_POLICY" size="sm" />
                </div>
              </div>

              {/* Action Description */}
              <div className="space-y-1">
                <h4 className="text-xs sm:text-sm font-bold text-[var(--text-primary)]">
                  {rec.description}
                </h4>
                <p className="text-xs text-[var(--text-muted)]">
                  <strong className="text-[var(--text-primary)]">Reason:</strong> {rec.reason}
                </p>
                {rec.source_section && (
                  <p className="text-xs font-mono text-[var(--text-muted)]">
                    Section: {rec.source_section}
                  </p>
                )}
              </div>

              {/* Supporting Evidence Chips & Review Button */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 border-t border-[var(--border-subtle)] text-xs">
                <div className="flex flex-wrap items-center gap-1.5 font-mono text-xs">
                  <span className="text-[var(--text-muted)]">Supporting Signals:</span>
                  {rec.supporting_evidence_ids.map((evId) => (
                    <button
                      key={evId}
                      onClick={() => onSelectEvidence?.(evId)}
                      className="px-1.5 py-0.5 rounded-xs bg-[var(--bg-subtle)] hover:bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-primary)] transition-colors inline-flex items-center gap-1 cursor-pointer"
                    >
                      <span>{evId}</span>
                      <ExternalLink className="w-2.5 h-2.5 text-[var(--text-muted)]" />
                    </button>
                  ))}
                </div>

                <div className="flex items-center gap-2 self-end sm:self-auto">
                  <button
                    onClick={() => handleNavigateReview(rec.recommendation_id)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs text-xs font-mono font-semibold bg-[var(--text-primary)] text-[var(--bg-surface)] hover:opacity-90 transition-colors cursor-pointer"
                  >
                    <span>Inspect / Review</span>
                    <ExternalLink className="w-3 h-3" />
                  </button>
                </div>
              </div>

              {/* Review History / Human Review Record if reviewed */}
              {rec.reviewed_by && (
                <div className="p-2.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs font-mono space-y-1">
                  <div className="text-emerald-500 font-bold flex items-center justify-between gap-1">
                    <div className="flex items-center gap-1">
                      <UserCheck className="w-3.5 h-3.5" />
                      <span>Human Reviewer Sign-Off Record</span>
                    </div>
                    <span className="text-xs text-[var(--text-muted)] font-normal">
                      Decision support sign-off only
                    </span>
                  </div>
                  <div className="text-[var(--text-muted)]">
                    Reviewed By: <span className="text-[var(--text-primary)]">{rec.reviewed_by}</span> |{' '}
                    Timestamp: <span className="text-[var(--text-primary)]">{rec.review_timestamp ? new Date(rec.review_timestamp).toLocaleString() : 'N/A'}</span>
                  </div>
                  {rec.review_notes && (
                    <div className="text-[var(--text-muted)]">
                      Notes: <span className="text-[var(--text-primary)]">{rec.review_notes}</span>
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
