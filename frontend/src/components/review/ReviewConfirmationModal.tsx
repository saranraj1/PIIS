import React, { useEffect } from 'react'
import { ShieldCheck, AlertTriangle, FileCheck2, X } from 'lucide-react'
import { EpistemicBadge } from '../epistemic/EpistemicBadge'

interface ReviewConfirmationModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  isSubmitting: boolean
  recommendationId: string
  incidentId: string
  decision: 'APPROVED' | 'REJECTED'
  reviewerId: string
  reviewerRole?: string
  reviewNotes: string
}

export const ReviewConfirmationModal: React.FC<ReviewConfirmationModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  isSubmitting,
  recommendationId,
  incidentId,
  decision,
  reviewerId,
  reviewerRole,
  reviewNotes,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isSubmitting && isOpen) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, isSubmitting, onClose])

  if (!isOpen) return null

  const isApproved = decision === 'APPROVED'

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="review-confirmation-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150"
    >
      <div
        className="w-full max-w-lg rounded-xl border bg-[var(--bg-card)] border-[var(--border-subtle)] shadow-xl overflow-hidden space-y-0"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 border-b border-[var(--border-subtle)] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div
              className={`p-2 rounded-lg ${
                isApproved
                  ? 'bg-emerald-500/10 text-emerald-500'
                  : 'bg-rose-500/10 text-rose-500'
              }`}
            >
              <FileCheck2 className="w-5 h-5" />
            </div>
            <div>
              <h3
                id="review-confirmation-title"
                className="text-sm font-bold text-[var(--text-primary)]"
              >
                Confirm Human Review Decision
              </h3>
              <p className="text-xs text-[var(--text-muted)]">
                Reviewer sign-off will be cryptographically sealed into the RFC 8785 audit ledger.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close dialog"
            className="p-1 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors disabled:opacity-50"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 space-y-4 text-xs">
          {/* Summary Details */}
          <div className="p-3.5 rounded-lg bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[var(--text-muted)] font-mono uppercase text-[0.7rem]">
                Recommendation ID
              </span>
              <span className="font-mono font-semibold text-[var(--text-primary)]">{recommendationId}</span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-[var(--text-muted)] font-mono uppercase text-[0.7rem]">
                Incident ID
              </span>
              <span className="font-mono text-[var(--text-primary)]">{incidentId}</span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-[var(--text-muted)] font-mono uppercase text-[0.7rem]">
                Decision
              </span>
              <span
                className={`font-mono font-bold px-2 py-0.5 rounded ${
                  isApproved
                    ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20'
                    : 'bg-rose-500/10 text-rose-500 border border-rose-500/20'
                }`}
              >
                {decision}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-[var(--text-muted)] font-mono uppercase text-[0.7rem]">
                Reviewer Identity
              </span>
              <span className="font-mono font-semibold text-[var(--text-primary)]">
                {reviewerId} {reviewerRole ? `[${reviewerRole}]` : ''}
              </span>
            </div>
          </div>

          {/* Review Notes Preview */}
          <div className="space-y-1.5">
            <label className="text-[var(--text-muted)] font-mono uppercase text-[0.7rem]">
              Recorded Technical Justification Notes
            </label>
            <div className="p-3 rounded-lg bg-[var(--bg-surface)] border border-[var(--border-subtle)] font-mono text-xs text-[var(--text-primary)] max-h-32 overflow-y-auto whitespace-pre-wrap">
              {reviewNotes}
            </div>
          </div>

          {/* Epistemic & Read-Only Disclosure */}
          <div className="p-3.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-500 dark:text-amber-400 space-y-1.5">
            <div className="flex items-center gap-1.5 font-bold text-xs">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>Operational Boundary & Non-Execution Assurance</span>
            </div>
            <p className="text-[0.72rem] leading-relaxed text-[var(--text-muted)]">
              PIIS is strictly a read-only decision support system. Submitting an approval records your operator evaluation in the audit trail, but <strong>never</strong> triggers automated production remediation, script execution, network mutation, or ticket closure.
            </p>
            <div className="pt-1">
              <EpistemicBadge category="HUMAN_APPROVED_DECISION" size="sm" />
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 bg-[var(--bg-surface)] border-t border-[var(--border-subtle)] flex items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="px-3.5 py-1.5 rounded-md border border-[var(--border-subtle)] text-xs font-semibold text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isSubmitting}
            className={`px-4 py-1.5 rounded-md text-xs font-bold text-white shadow-xs transition-opacity flex items-center gap-2 ${
              isApproved
                ? 'bg-emerald-600 hover:bg-emerald-500'
                : 'bg-rose-600 hover:bg-rose-500'
            } disabled:opacity-50`}
          >
            {isSubmitting ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Signing...</span>
              </>
            ) : (
              <>
                <ShieldCheck className="w-4 h-4" />
                <span>Confirm & Sign Cryptographically</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
