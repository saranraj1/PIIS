import React, { useState } from 'react'
import {
  FileText,
  AlertTriangle,
  ExternalLink,
  ShieldAlert,
  Send,
  Info,
} from 'lucide-react'
import type { ReviewQueueItem, InvestigationResponse, ReviewResponse } from '../../api/types'
import { EpistemicBadge } from '../epistemic/EpistemicBadge'
import { SeverityBadge } from '../common/SeverityBadge'
import { DomainBadge } from '../common/DomainBadge'
import { StatusPill } from '../common/StatusPill'
import { ReviewConfirmationModal } from './ReviewConfirmationModal'
import { ReviewReceiptCard } from './ReviewReceiptCard'
import { useAuth } from '../../auth/AuthContext'

interface ReviewWorkspaceProps {
  selectedItem: ReviewQueueItem | null
  investigation?: InvestigationResponse | null
  isLoadingInvestigation?: boolean
  onSubmitReview: (decision: 'APPROVED' | 'REJECTED', notes: string) => Promise<void>
  isSubmitting: boolean
  lastReceipt?: ReviewResponse | null
  onDismissReceipt?: () => void
  onOpenInvestigation?: (incidentId: string) => void
  error?: string | null
}

export const ReviewWorkspace: React.FC<ReviewWorkspaceProps> = ({
  selectedItem,
  investigation,
  isLoadingInvestigation = false,
  onSubmitReview,
  isSubmitting,
  lastReceipt,
  onDismissReceipt,
  onOpenInvestigation,
  error,
}) => {
  const { principal } = useAuth()
  const [decision, setDecision] = useState<'APPROVED' | 'REJECTED'>('APPROVED')
  const [notes, setNotes] = useState('')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)

  if (!selectedItem) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-8 text-center rounded-xs border border-dashed border-[var(--border-subtle)] bg-[var(--bg-surface)]">
        <FileText className="w-10 h-10 text-[var(--text-muted)] opacity-50 mb-3" />
        <h4 className="text-sm font-semibold text-[var(--text-primary)]">No Recommendation Selected</h4>
        <p className="text-xs text-[var(--text-muted)] max-w-sm mt-1">
          Select an actionable recommendation from the review queue on the left to inspect evidence, evaluate hypotheses, and record decisions.
        </p>
      </div>
    )
  }

  const isPending = selectedItem.approval_status === 'PENDING_REVIEW'

  const handleOpenConfirm = () => {
    if (
      decision === 'APPROVED' &&
      (selectedItem.source_runbook_id === 'RESTORED_LEDGER' ||
        selectedItem.has_missing_evidence ||
        !selectedItem.is_sufficient)
    ) {
      setValidationError(
        'Approval blocked: Evidence is missing or unavailable. Re-run investigation with verified telemetry or select REJECT.'
      )
      return
    }

    if (!notes.trim()) {
      setValidationError(
        decision === 'REJECTED'
          ? 'Rejection justification reason is mandatory.'
          : 'Operator technical rationale notes are mandatory.'
      )
      return
    }
    setValidationError(null)
    setIsModalOpen(true)
  }

  const handleConfirmSubmission = async () => {
    try {
      await onSubmitReview(decision, notes.trim())
      setIsModalOpen(false)
      setNotes('')
    } catch {
      // Error handled by parent hook
    }
  }

  return (
    <div className="space-y-5" role="region" aria-label="Recommendation Review Workspace">
      {/* 1. Cryptographic Receipt Card (if fresh receipt) */}
      {lastReceipt && (
        <ReviewReceiptCard
          receipt={lastReceipt}
          onDismiss={onDismissReceipt}
          onViewInvestigation={
            selectedItem.incident_id
              ? () => onOpenInvestigation?.(selectedItem.incident_id)
              : undefined
          }
        />
      )}

      {/* 2. Top Banner: Title & Primary Context Header */}
      <div className="p-4 rounded-xs border bg-[var(--bg-surface)] border-[var(--border-subtle)] space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border-subtle)] pb-2.5">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-bold text-[var(--text-primary)]">
              {selectedItem.recommendation_id}
            </span>
            <span className="text-xs text-[var(--text-muted)]">|</span>
            <button
              onClick={() => onOpenInvestigation?.(selectedItem.incident_id)}
              className="font-mono text-xs text-[var(--text-primary)] hover:underline inline-flex items-center gap-1 cursor-pointer"
              title="Open full investigation workspace for this incident"
            >
              <span>Incident: {selectedItem.incident_id}</span>
              <ExternalLink className="w-3 h-3 text-[var(--text-muted)]" />
            </button>
          </div>

          <div className="flex items-center gap-2">
            <SeverityBadge severity={selectedItem.incident_severity} size="sm" />
            <DomainBadge domain={selectedItem.network_domain} size="sm" />
            <StatusPill state={selectedItem.approval_status} size="sm" />
            <EpistemicBadge category="RECOMMENDATION" size="sm" />
          </div>
        </div>

        <div>
          <h2 className="text-base font-bold text-[var(--text-primary)] tracking-tight">
            {selectedItem.description}
          </h2>
          <p className="text-xs text-[var(--text-muted)] mt-1 leading-relaxed">
            {selectedItem.reason}
          </p>
        </div>

        {/* Operational Context Metadata Strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-[var(--border-subtle)] text-xs font-mono">
          <div>
            <span className="text-xs text-[var(--text-muted)] uppercase block">Runbook</span>
            <span className="font-bold text-[var(--text-primary)] truncate block">
              {selectedItem.source_runbook_id}
            </span>
          </div>

          <div>
            <span className="text-xs text-[var(--text-muted)] uppercase block">Section</span>
            <span className="text-[var(--text-secondary)] truncate block">
              {selectedItem.source_section || 'N/A'}
            </span>
          </div>

          <div>
            <span className="text-xs text-[var(--text-muted)] uppercase block">Risk Tier</span>
            <span className="font-bold text-[var(--text-primary)] truncate block">
              {selectedItem.risk_classification}
            </span>
          </div>

          <div>
            <span className="text-xs text-[var(--text-muted)] uppercase block">Human Auth Required</span>
            <span className="text-[var(--text-secondary)]">
              {selectedItem.human_approval_required ? 'YES (MANDATORY)' : 'NO'}
            </span>
          </div>
        </div>
      </div>

      {/* 3. Sufficiency & Contradiction Alerts */}
      <div className="space-y-3">
        {selectedItem.has_contradictions && (
          <div
            role="alert"
            className="p-3.5 rounded-xs bg-amber-500/10 border border-amber-500/30 text-amber-500 dark:text-amber-400 space-y-1 text-xs"
          >
            <div className="flex items-center gap-2 font-bold">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>Contradictory Telemetry Signals Detected</span>
            </div>
            <p className="text-xs text-[var(--text-muted)] leading-relaxed">
              Conflicting evidence exists in the incident evidence register. Telemetry signals diverge from typical runbook fault signatures. Reviewers must inspect contradictory evidence before authorizing diagnostic tests.
            </p>
          </div>
        )}

        {selectedItem.has_missing_evidence && (
          <div
            role="alert"
            className="p-3.5 rounded-xs bg-amber-500/10 border border-amber-500/20 text-amber-500 dark:text-amber-400 flex items-start gap-2.5 text-xs"
          >
            <Info className="w-4 h-4 shrink-0 mt-0.5" />
            <p className="text-[var(--text-muted)] leading-relaxed">
              <strong>Incomplete Telemetry Windows:</strong> Key telemetry series exhibit missing intervals or unmapped sensor points. Grounding is derived from partial observations.
            </p>
          </div>
        )}

        {(selectedItem.source_runbook_id === 'RESTORED_LEDGER' || selectedItem.supporting_evidence_ids.length === 0) && (
          <div
            role="alert"
            className="p-4 rounded-xs bg-rose-500/10 border border-rose-500/30 text-rose-500 dark:text-rose-400 space-y-1.5"
          >
            <div className="flex items-center gap-2 font-bold text-xs">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>Restored Evidence Context Unavailable</span>
            </div>
            <p className="text-xs text-[var(--text-muted)] leading-relaxed">
              This recommendation was restored from a persistent audit ledger checkpoint following a process restart. Original raw telemetry time-series, alarms, and runbook source text are not retained in the audit ledger and cannot be independently verified from historical metadata alone. A fresh investigation must be executed before approval can be granted.
            </p>
          </div>
        )}
      </div>

      {/* 4. Supporting Evidence & Hypotheses */}
      {isLoadingInvestigation ? (
        <div className="p-6 rounded-xs border bg-[var(--bg-card)] border-[var(--border-subtle)] text-center text-xs text-[var(--text-muted)]">
          <span className="animate-pulse">Loading linked investigation evidence register...</span>
        </div>
      ) : investigation ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Hypotheses Card */}
          <div className="p-4 rounded-xs border bg-[var(--bg-card)] border-[var(--border-subtle)] space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-[var(--border-subtle)]">
              <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                Ranked Hypotheses ({investigation.hypotheses?.length || 0})
              </h4>
              <EpistemicBadge category="HYPOTHESIS" size="sm" />
            </div>

            <div className="space-y-2.5 max-h-60 overflow-y-auto">
              {investigation.hypotheses && investigation.hypotheses.length > 0 ? (
                investigation.hypotheses.map((hyp) => (
                  <div
                    key={hyp.hypothesis_id}
                    className="p-3 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1.5"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-mono font-bold text-amber-500">{hyp.hypothesis_id}</span>
                      <span className="text-xs font-mono px-1.5 py-0.5 rounded-xs bg-amber-500/10 text-amber-500 font-bold">
                        {Math.round(hyp.confidence_proxy * 100)}% Affinity Proxy
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text-primary)] font-medium">
                      {hyp.description}
                    </p>
                    <div className="text-xs text-[var(--text-muted)] font-mono truncate">
                      Source: {hyp.evidence_source}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-xs text-[var(--text-muted)] p-2">
                  No ranked hypotheses generated for this incident.
                </div>
              )}
            </div>
          </div>

          {/* Evidence Items Card */}
          <div className="p-4 rounded-xs border bg-[var(--bg-card)] border-[var(--border-subtle)] space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-[var(--border-subtle)]">
              <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                Supporting Evidence ({selectedItem.supporting_evidence_ids.length})
              </h4>
              <EpistemicBadge category="OBSERVED_FACT" size="sm" />
            </div>

            <div className="space-y-2 max-h-60 overflow-y-auto">
              {selectedItem.supporting_evidence_ids.length > 0 ? (
                selectedItem.supporting_evidence_ids.map((evId) => (
                  <div
                    key={evId}
                    className="p-2.5 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] flex items-center justify-between text-xs"
                  >
                    <span className="font-mono font-semibold text-[var(--text-primary)]">{evId}</span>
                    <span className="text-xs font-mono text-[var(--text-muted)]">
                      Referenced by runbook
                    </span>
                  </div>
                ))
              ) : (
                <div className="text-xs text-[var(--text-muted)] p-2 font-mono">
                  {selectedItem.source_runbook_id === 'RESTORED_LEDGER'
                    ? 'Restored from persistent ledger: raw telemetry and runbook evidence unavailable without fresh investigation.'
                    : 'No supporting evidence IDs explicitly mapped.'}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : null}

      {/* 5. Human Decision Gateway */}
      <div className="p-5 rounded-xs border bg-[var(--bg-card)] border-[var(--border-subtle)] space-y-4">
        <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-emerald-500" />
            <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
              Human Review & Operator Sign-Off Gateway
            </h4>
          </div>
          <EpistemicBadge category="HUMAN_APPROVED_DECISION" size="sm" />
        </div>

        {error && (
          <div
            role="alert"
            className="p-3 rounded-xs bg-rose-500/10 border border-rose-500/30 text-rose-500 text-xs space-y-1"
          >
            <div className="font-bold">Submission Rejected by Backend</div>
            <p className="text-[var(--text-muted)]">{error}</p>
          </div>
        )}

        {isPending ? (
          <div className="space-y-4">
            {/* Decision Radio/Toggle */}
            <div className="space-y-1.5">
              <label className="text-xs font-mono font-bold uppercase text-[var(--text-muted)]">
                Select Decision
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setDecision('APPROVED')
                    setValidationError(null)
                  }}
                  className={`p-3 rounded-xs border font-mono font-bold text-xs flex items-center justify-center gap-2 transition-all cursor-pointer ${
                    decision === 'APPROVED'
                      ? 'bg-[var(--bg-surface)] border-[var(--text-primary)] text-[var(--text-primary)] ring-1 ring-[var(--text-primary)]'
                      : 'bg-[var(--bg-surface)] border-[var(--border-subtle)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span>APPROVE RECOMMENDATION</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setDecision('REJECTED')
                    setValidationError(null)
                  }}
                  className={`p-3 rounded-xs border font-mono font-bold text-xs flex items-center justify-center gap-2 transition-all cursor-pointer ${
                    decision === 'REJECTED'
                      ? 'bg-[var(--bg-surface)] border-[var(--text-primary)] text-[var(--text-primary)] ring-1 ring-[var(--text-primary)]'
                      : 'bg-[var(--bg-surface)] border-[var(--border-subtle)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  <span className="w-2 h-2 rounded-full bg-rose-500" />
                  <span>REJECT RECOMMENDATION</span>
                </button>
              </div>

              {decision === 'APPROVED' &&
                (selectedItem.source_runbook_id === 'RESTORED_LEDGER' ||
                  selectedItem.has_missing_evidence ||
                  !selectedItem.is_sufficient) && (
                  <div
                    role="alert"
                    className="p-3 rounded-xs bg-rose-500/10 border border-rose-500/30 text-rose-500 text-xs flex items-start gap-2"
                  >
                    <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                    <div>
                      <strong className="block font-bold">Approval Blocked by Evidence Policy</strong>
                      <span className="text-[var(--text-muted)]">
                        This recommendation lacks complete, verified live telemetry evidence. Approving diagnostic actions based solely on restored or incomplete metadata is prohibited. Please reject this recommendation or conduct a fresh investigation.
                      </span>
                    </div>
                  </div>
                )}
            </div>

            {/* Operator Decision Guidance & Invariants */}
            <div className="p-3 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1.5 text-xs text-[var(--text-muted)]">
              <div className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5 text-xs">
                <Info className="w-3.5 h-3.5 text-[var(--text-muted)] shrink-0" />
                <span>Decision Semantics & Operational Invariants</span>
              </div>
              <ul className="list-disc list-inside space-y-0.5 text-xs leading-relaxed">
                <li>
                  <strong className="text-[var(--text-primary)]">Terminal Decisions:</strong> Both <code>APPROVED</code> and <code>REJECTED</code> are permanent, immutable actions recorded in the cryptographic audit ledger. Replays and re-evaluations are strictly rejected.
                </li>
                <li>
                  <strong className="text-[var(--text-primary)]">Awaiting Evidence:</strong> Requesting additional evidence is <em>not</em> a separate terminal state. If telemetry is inconclusive, leave this recommendation in <code>PENDING_REVIEW</code> while awaiting observations, or reject it with documented rationale.
                </li>
                <li>
                  <strong className="text-[var(--text-primary)]">Non-Execution Guarantee:</strong> Human approval records operator intent for manual NOC field execution; it does <em>not</em> trigger automated CLI execution, network configuration changes, or ticket mutations.
                </li>
              </ul>
            </div>

            {/* Notes Textarea */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label
                  htmlFor="review-notes-input"
                  className="text-xs font-mono font-bold uppercase text-[var(--text-muted)]"
                >
                  {decision === 'REJECTED'
                    ? 'Mandatory Rejection Explanation / Reason *'
                    : 'Mandatory Technical Rationale / Justification *'}
                </label>
                <span className="text-xs font-mono text-[var(--text-muted)]">
                  {notes.length} characters (cryptographically covered)
                </span>
              </div>
              <textarea
                id="review-notes-input"
                rows={3}
                value={notes}
                onChange={(e) => {
                  setNotes(e.target.value)
                  if (validationError) setValidationError(null)
                }}
                placeholder={
                  decision === 'REJECTED'
                    ? 'Explain why this recommendation is rejected (e.g. high customer traffic window; contradictory fiber telemetry; awaiting further observation).'
                    : 'Record technical rationale (e.g. verified antenna VSWR telemetry spike; read-only feeder sweep authorized per SOP-RAN-VSWR-001).'
                }
                className={`w-full p-3 rounded-xs bg-[var(--bg-surface)] border font-mono text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-hidden focus:ring-1 ${
                  validationError
                    ? 'border-rose-500 focus:ring-rose-500'
                    : 'border-[var(--border-subtle)] focus:ring-[var(--border-strong)]'
                }`}
              />
              {validationError && (
                <div className="text-xs text-rose-500 font-mono">{validationError}</div>
              )}
            </div>

            {/* Reviewer Identity Notice */}
            <div className="text-xs font-mono text-[var(--text-muted)] flex items-center justify-between">
              <span>
                Signing Principal: <strong className="text-[var(--text-primary)]">{principal?.principal_id || 'AUTHENTICATED_OPERATOR'}</strong>
              </span>
              <span className="text-emerald-500">Service accounts barred</span>
            </div>

            {/* Submit Button */}
            <div className="flex items-center justify-end pt-2">
              <button
                type="button"
                onClick={handleOpenConfirm}
                disabled={isSubmitting}
                className="px-5 py-2.5 rounded-xs text-xs font-bold font-mono bg-[var(--text-primary)] text-[var(--bg-surface)] hover:opacity-90 transition-opacity flex items-center gap-2 disabled:opacity-50 cursor-pointer"
              >
                <Send className="w-4 h-4" />
                <span>Review & Notarize Decision</span>
              </button>
            </div>
          </div>
        ) : (
          /* Terminal State Panel */
          <div className="p-4 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-bold text-[var(--text-muted)] uppercase">
                Terminal State Recorded
              </span>
              <StatusPill state={selectedItem.approval_status} size="sm" />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <div>
                <span className="text-[var(--text-muted)] font-mono text-xs uppercase">
                  Reviewed By
                </span>
                <div className="font-mono font-bold text-[var(--text-primary)]">
                  {selectedItem.reviewed_by || 'UNKNOWN_OPERATOR'}
                </div>
              </div>

              <div>
                <span className="text-[var(--text-muted)] font-mono text-xs uppercase">
                  Review Timestamp (UTC)
                </span>
                <div className="font-mono text-[var(--text-primary)]">
                  {selectedItem.review_timestamp || 'N/A'}
                </div>
              </div>
            </div>

            {selectedItem.review_notes && (
              <div className="space-y-1">
                <span className="text-[var(--text-muted)] font-mono text-xs uppercase">
                  Recorded Operator Notes
                </span>
                <div className="p-2.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] font-mono text-xs text-[var(--text-primary)] whitespace-pre-wrap">
                  {selectedItem.review_notes}
                </div>
              </div>
            )}

            <div className="text-xs text-[var(--text-muted)] font-mono pt-1">
              Immutable state machine rule: recommendations in terminal states ({selectedItem.approval_status}) cannot be re-approved, re-rejected, or overwritten.
            </div>
          </div>
        )}
      </div>

      {/* Confirmation Dialog Modal */}
      <ReviewConfirmationModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onConfirm={handleConfirmSubmission}
        isSubmitting={isSubmitting}
        recommendationId={selectedItem.recommendation_id}
        incidentId={selectedItem.incident_id}
        decision={decision}
        reviewerId={principal?.principal_id || 'AUTHENTICATED_OPERATOR'}
        reviewerRole={principal?.roles?.[0]}
        reviewNotes={notes}
      />
    </div>
  )
}
