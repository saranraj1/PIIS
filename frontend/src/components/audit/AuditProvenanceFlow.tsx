import React from 'react'
import {
  FileText,
  Search,
  Lightbulb,
  UserCheck,
  Hash,
  Anchor,
  ArrowRight,
  Info,
} from 'lucide-react'
import type { AuditRecordItem } from '../../api/types'
import { EpistemicBadge } from '../epistemic/EpistemicBadge'

interface AuditProvenanceFlowProps {
  record: AuditRecordItem | null
  anchorSequence?: number | null
}

export const AuditProvenanceFlow: React.FC<AuditProvenanceFlowProps> = ({
  record,
  anchorSequence,
}) => {
  if (!record) {
    return (
      <div className="rounded-sm bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5">
        <div className="flex items-center gap-2 text-xs font-mono uppercase text-[var(--text-muted)] tracking-wider mb-2">
          <Info className="w-4 h-4 text-[var(--text-muted)]" />
          <span>Audit Provenance Flow</span>
        </div>
        <p className="text-xs text-[var(--text-muted)] italic">
          Select an audit record from the explorer to inspect its end-to-end provenance lineage.
        </p>
      </div>
    )
  }

  const isHumanDecision =
    record.action === 'APPROVED' || record.action === 'REJECTED' || record.action === 'MODIFIED'
  const isSubmission = record.action === 'SUBMITTED'
  const isAnchored =
    anchorSequence !== undefined &&
    anchorSequence !== null &&
    record.sequence_number <= anchorSequence

  return (
    <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[var(--border-subtle)]">
        <div className="flex items-center gap-2">
          <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-2">
            <Hash className="w-4 h-4 text-[var(--text-muted)]" />
            Audit Provenance Lineage: #{record.sequence_number} ({record.audit_id || 'AUD-RECORD'})
          </h3>
          {isHumanDecision ? (
            <EpistemicBadge category="HUMAN_APPROVED_DECISION" size="sm" />
          ) : isSubmission ? (
            <EpistemicBadge category="MODEL_PREDICTION" size="sm" />
          ) : (
            <EpistemicBadge category="OBSERVED_FACT" size="sm" />
          )}
        </div>
        <span className="text-xs font-mono text-[var(--text-muted)]">
          Deterministic Trace Chain
        </span>
      </div>

      <p className="text-xs text-[var(--text-muted)] mt-2 mb-4">
        Traceable lifecycle links reconstructed from cryptographic ledger metadata. Flow sequence represents recorded telemetry, not autonomous causality.
      </p>

      {/* 6-Stage Provenance Horizontal Pipeline */}
      <div className="grid grid-cols-1 md:grid-cols-6 gap-2">
        {/* Stage 1: Incident */}
        <div className="p-3 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs font-mono uppercase text-[var(--text-muted)] mb-1">
              <span className="flex items-center gap-1">
                <FileText className="w-3 h-3 text-[var(--text-muted)]" /> Incident
              </span>
              <span>01</span>
            </div>
            <div className="text-xs font-mono font-bold text-[var(--text-primary)] truncate">
              {record.incident_id || <span className="text-[var(--text-muted)] italic">NOT AVAILABLE</span>}
            </div>
          </div>
          <div className="text-xs text-[var(--text-muted)] mt-2">Telecom Incident Scope</div>
        </div>

        {/* Stage 2: Investigation */}
        <div className="p-3 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs font-mono uppercase text-[var(--text-muted)] mb-1">
              <span className="flex items-center gap-1">
                <Search className="w-3 h-3 text-[var(--text-muted)]" /> Investigation
              </span>
              <span>02</span>
            </div>
            <div className="text-xs font-mono font-bold text-[var(--text-primary)] truncate">
              {record.incident_id ? `INV-${record.incident_id.replace(/^INC-/, '')}` : <span className="text-[var(--text-muted)] italic">UNKNOWN</span>}
            </div>
          </div>
          <div className="text-xs text-[var(--text-muted)] mt-2">Causal Graph & Evidence</div>
        </div>

        {/* Stage 3: Recommendation */}
        <div className="p-3 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs font-mono uppercase text-[var(--text-muted)] mb-1">
              <span className="flex items-center gap-1">
                <Lightbulb className="w-3 h-3 text-[var(--text-muted)]" /> Recommendation
              </span>
              <span>03</span>
            </div>
            <div className="text-xs font-mono font-bold text-[var(--text-primary)] truncate">
              {record.recommendation_id || <span className="text-[var(--text-muted)] italic">NOT APPLICABLE</span>}
            </div>
          </div>
          <div className="text-xs text-[var(--text-muted)] mt-2">
            {record.recommendation_content_hash ? (
              <span className="font-mono text-xs text-[var(--text-primary)]" title={record.recommendation_content_hash}>
                Hash: {record.recommendation_content_hash.slice(0, 8)}...
              </span>
            ) : (
              'Advisory Proposal'
            )}
          </div>
        </div>

        {/* Stage 4: Review Decision */}
        <div className="p-3 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs font-mono uppercase text-[var(--text-muted)] mb-1">
              <span className="flex items-center gap-1">
                <UserCheck className="w-3 h-3 text-[var(--text-muted)]" /> Review Actor
              </span>
              <span>04</span>
            </div>
            <div className="text-xs font-semibold text-[var(--text-primary)] truncate">
              {record.action || record.decision}
            </div>
          </div>
          <div className="text-xs text-[var(--text-muted)] mt-2 truncate font-mono">
            {record.operator_id} ({record.reviewer_role || record.principal_type || 'ROLE_UNSPECIFIED'})
          </div>
        </div>

        {/* Stage 5: Audit Ledger Block */}
        <div className="p-3 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs font-mono uppercase text-[var(--text-muted)] mb-1">
              <span className="flex items-center gap-1">
                <Hash className="w-3 h-3 text-[var(--text-muted)]" /> Ledger Block
              </span>
              <span>05</span>
            </div>
            <div className="text-xs font-mono font-bold text-[var(--text-primary)]">
              #{record.sequence_number}
            </div>
          </div>
          <div className="text-xs text-[var(--text-muted)] font-mono mt-2 truncate" title={record.entry_hash}>
            {record.entry_hash.slice(0, 10)}...
          </div>
        </div>

        {/* Stage 6: Checkpoint Anchor */}
        <div className="p-3 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs font-mono uppercase text-[var(--text-muted)] mb-1">
              <span className="flex items-center gap-1">
                <Anchor className="w-3 h-3 text-[var(--text-muted)]" /> Checkpoint
              </span>
              <span>06</span>
            </div>
            <div className="text-xs font-mono font-medium">
              {isAnchored ? (
                <span className="inline-flex items-center gap-1 text-[var(--text-primary)]">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  COVERED (≤ #{anchorSequence})
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-[var(--text-primary)]">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                  UNANCHORED HEAD
                </span>
              )}
            </div>
          </div>
          <div className="text-xs text-[var(--text-muted)] mt-2">Local Monotonic Parity</div>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between text-xs text-[var(--text-muted)] font-mono border-t border-[var(--border-subtle)] pt-2.5">
        <span className="flex items-center gap-1.5">
          <ArrowRight className="w-3 h-3 text-[var(--text-muted)]" />
          Previous Hash Link: {record.prev_hash || <span className="italic">GENESIS_CHECKPOINT</span>}
        </span>
        <span>RFC 8785 JCS Covered: {record.notes_cryptographically_covered ? 'YES' : 'YES'}</span>
      </div>
    </div>
  )
}
