import React from 'react'
import { ShieldCheck, CheckCircle2, Hash, Calendar, User, FileCheck2 } from 'lucide-react'
import type { ReviewResponse } from '../../api/types'
import { EpistemicBadge } from '../epistemic/EpistemicBadge'

interface ReviewReceiptCardProps {
  receipt: ReviewResponse
  onDismiss?: () => void
}

export const ReviewReceiptCard: React.FC<ReviewReceiptCardProps> = ({ receipt, onDismiss }) => {
  const isApproved = receipt.decision === 'APPROVED'

  return (
    <div
      role="region"
      aria-label="Cryptographic Review Audit Receipt"
      className="p-5 rounded-lg border bg-[var(--bg-card)] border-emerald-500/30 dark:border-emerald-500/40 shadow-sm space-y-4"
    >
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-[var(--border-subtle)]">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-md bg-emerald-500/10 text-emerald-500">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="text-sm font-bold text-[var(--text-primary)]">
                Review Decision Cryptographically Sealed
              </h4>
              <EpistemicBadge category="HUMAN_APPROVED_DECISION" size="sm" />
            </div>
            <p className="text-xs text-[var(--text-muted)] font-mono">
              Receipt ID: <span className="font-bold text-emerald-500">{receipt.receipt_id}</span>
            </p>
          </div>
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="text-xs font-mono text-[var(--text-muted)] hover:text-[var(--text-primary)] px-2 py-1 rounded border border-[var(--border-subtle)]"
          >
            Close Receipt
          </button>
        )}
      </div>

      {/* Grid of Key Metadata */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
        <div className="p-3 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
          <div className="flex items-center gap-1.5 text-[var(--text-muted)] font-mono text-[0.7rem] uppercase">
            <FileCheck2 className="w-3.5 h-3.5 text-[var(--text-muted)]" />
            <span>Decision</span>
          </div>
          <div className="font-mono text-sm">
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)] font-medium">
              <span className={`w-1.5 h-1.5 rounded-full ${isApproved ? 'bg-emerald-500' : 'bg-rose-500'}`} />
              {receipt.decision}
            </span>
          </div>
        </div>

        <div className="p-3 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
          <div className="flex items-center gap-1.5 text-[var(--text-muted)] font-mono text-[0.7rem] uppercase">
            <User className="w-3.5 h-3.5 text-[var(--text-muted)]" />
            <span>Notarized By</span>
          </div>
          <div className="font-mono font-bold text-sm text-[var(--text-primary)] truncate">
            {receipt.reviewed_by}
          </div>
        </div>

        <div className="p-3 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
          <div className="flex items-center gap-1.5 text-[var(--text-muted)] font-mono text-[0.7rem] uppercase">
            <Hash className="w-3.5 h-3.5 text-[var(--text-muted)]" />
            <span>Ledger Sequence</span>
          </div>
          <div className="font-mono font-bold text-sm text-[var(--text-primary)]">
            #{receipt.ledger_sequence}
          </div>
        </div>

        <div className="p-3 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1">
          <div className="flex items-center gap-1.5 text-[var(--text-muted)] font-mono text-[0.7rem] uppercase">
            <Calendar className="w-3.5 h-3.5 text-[var(--text-muted)]" />
            <span>Timestamp (UTC)</span>
          </div>
          <div className="font-mono text-xs text-[var(--text-primary)] truncate">
            {receipt.review_timestamp}
          </div>
        </div>
      </div>

      {/* SHA-256 Hash Chaining Block */}
      <div className="p-3 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] space-y-1.5">
        <div className="flex items-center justify-between text-[0.7rem] font-mono text-[var(--text-muted)]">
          <span className="flex items-center gap-1.5 uppercase">
            <ShieldCheck className="w-3.5 h-3.5 text-[var(--text-muted)]" />
            RFC 8785 Canonical Entry SHA-256 Digest
          </span>
          <span className="inline-flex items-center gap-1 text-[var(--text-primary)] font-medium uppercase tracking-wider">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            Chain Linked & Notarized
          </span>
        </div>
        <div className="font-mono text-xs text-[var(--text-primary)] break-all bg-[var(--bg-card)] p-2 rounded-xs border border-[var(--border-subtle)] select-all">
          {receipt.audit_entry_hash}
        </div>
      </div>

      {/* Governance Disclosure */}
      <div className="rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] p-3 text-xs text-[var(--text-secondary)] flex items-start gap-2.5">
        <ShieldCheck className="w-4 h-4 text-[var(--text-muted)] shrink-0 mt-0.5" />
        <p className="leading-relaxed">
          <strong className="text-[var(--text-primary)]">Read-Only Operational Assurance:</strong> This review decision is cryptographically anchored in the immutable audit ledger. In accordance with PIIS safety invariants, this sign-off records operator human evaluation and does <strong>not</strong> trigger automated production changes, live network mutation, or ticket closures.
        </p>
      </div>
    </div>
  )
}
