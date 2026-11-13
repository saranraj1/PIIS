import React, { useState } from 'react'
import {
  X,
  Hash,
  Shield,
  Key,
  Calendar,
  User,
  FileText,
  CheckCircle2,
  AlertTriangle,
  Code2,
  Copy,
  Check,
} from 'lucide-react'
import type { AuditRecordItem } from '../../api/types'
import { EpistemicBadge } from '../epistemic/EpistemicBadge'

interface AuditRecordDetailDrawerProps {
  record: AuditRecordItem | null
  isOpen: boolean
  onClose: () => void
}

export const AuditRecordDetailDrawer: React.FC<AuditRecordDetailDrawerProps> = ({
  record,
  isOpen,
  onClose,
}) => {
  const [copiedField, setCopiedField] = useState<string | null>(null)
  const [showCanonicalJson, setShowCanonicalJson] = useState<boolean>(true)

  if (!isOpen || !record) return null

  const handleCopy = (text: string, fieldName: string) => {
    navigator.clipboard.writeText(text)
    setCopiedField(fieldName)
    setTimeout(() => setCopiedField(null), 2000)
  }

  const isGenesis =
    record.sequence_number === 1 || record.prev_hash === 'GENESIS_CHECKPOINT'

  // Construct a preview of the canonical fields
  const canonicalPayload = {
    action: record.action || record.decision,
    audit_id: record.audit_id || `AUD-${record.sequence_number}`,
    incident_id: record.incident_id || null,
    key_id: record.key_id || 'piis-dev-key',
    new_status: record.new_status || record.decision,
    notes: record.notes || null,
    operator_id: record.operator_id,
    previous_entry_sha256: record.prev_hash,
    previous_status: record.previous_status || null,
    principal_type: record.principal_type || 'HUMAN',
    recommendation_content_hash: record.recommendation_content_hash || null,
    recommendation_id: record.recommendation_id || null,
    reviewer_auth_hash: record.reviewer_auth_hash || null,
    reviewer_role: record.reviewer_role || null,
    schema_version: record.schema_version,
    sequence_number: record.sequence_number,
    timestamp_utc: record.timestamp,
  }

  return (
    <div
      className="fixed inset-0 z-50 overflow-hidden bg-black/60 backdrop-blur-xs flex justify-end animate-in fade-in duration-200"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Audit Record Details"
    >
      <div
        className="w-full max-w-2xl bg-[var(--bg-surface)] border-l border-[var(--border-subtle)] h-full overflow-y-auto flex flex-col shadow-2xl p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[var(--border-subtle)]">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xs bg-[var(--bg-subtle)] text-[var(--text-muted)] border border-[var(--border-subtle)]">
              <Hash className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-[var(--text-primary)] font-mono">
                  Audit Block #{record.sequence_number}
                </h2>
                {record.action === 'APPROVED' ? (
                  <EpistemicBadge category="HUMAN_APPROVED_DECISION" size="sm" />
                ) : record.action === 'SUBMITTED' ? (
                  <EpistemicBadge category="MODEL_PREDICTION" size="sm" />
                ) : (
                  <EpistemicBadge category="OBSERVED_FACT" size="sm" />
                )}
              </div>
              <p className="text-xs text-[var(--text-muted)] font-mono mt-0.5">
                ID: {record.audit_id || 'AUD-UNSPECIFIED'} • Schema {record.schema_version}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-subtle)] transition-colors cursor-pointer"
            aria-label="Close detail drawer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="space-y-6 py-4 flex-1">
          {/* Metadata Grid */}
          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)]">
              <span className="text-xs font-mono uppercase text-[var(--text-muted)] flex items-center gap-1 mb-1">
                <Calendar className="w-3 h-3 text-[var(--text-muted)]" /> Timestamp (UTC)
              </span>
              <span className="text-xs font-mono font-medium text-[var(--text-primary)]">
                {record.timestamp}
              </span>
            </div>

            <div className="p-3 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)]">
              <span className="text-xs font-mono uppercase text-[var(--text-muted)] flex items-center gap-1 mb-1">
                <User className="w-3 h-3 text-[var(--text-muted)]" /> Reviewer Principal
              </span>
              <span className="text-xs font-mono font-medium text-[var(--text-primary)] truncate block">
                {record.operator_id}{' '}
                <span className="text-[var(--text-muted)] text-xs">
                  ({record.reviewer_role || record.principal_type || 'ROLE_UNSPECIFIED'})
                </span>
              </span>
            </div>

            <div className="p-3 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)]">
              <span className="text-xs font-mono uppercase text-[var(--text-muted)] flex items-center gap-1 mb-1">
                <FileText className="w-3 h-3 text-[var(--text-muted)]" /> Action / Decision
              </span>
              <span className="text-xs font-bold text-[var(--text-primary)]">
                {record.action || record.decision}
              </span>
            </div>

            <div className="p-3 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)]">
              <span className="text-xs font-mono uppercase text-[var(--text-muted)] flex items-center gap-1 mb-1">
                <Hash className="w-3 h-3 text-[var(--text-muted)]" /> Incident Reference
              </span>
              <span className="text-xs font-mono font-medium text-[var(--text-primary)]">
                {record.incident_id || <span className="text-[var(--text-muted)] italic">N/A</span>}
              </span>
            </div>
          </div>

          {/* Review Notes / Rationale */}
          {record.notes && (
            <div className="p-3.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)]">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-mono uppercase text-[var(--text-muted)]">
                  Operator Review Notes & Rationale
                </span>
                <span className="inline-flex items-center gap-1 text-xs font-mono text-[var(--text-secondary)]">
                  <CheckCircle2 className="w-3 h-3 text-emerald-500" /> Integrity Protected in Digest
                </span>
              </div>
              <p className="text-xs text-[var(--text-primary)] leading-relaxed italic">
                "{record.notes}"
              </p>
            </div>
          )}

          {/* Cryptographic Linkage Hashes */}
          <div className="rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] p-4 space-y-3">
            <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-1.5">
              <Shield className="w-4 h-4 text-[var(--text-muted)]" />
              Cryptographic Integrity & Chain Continuity
            </h4>

            {/* Current Record Hash */}
            <div>
              <div className="flex items-center justify-between text-xs font-mono text-[var(--text-muted)] mb-1">
                <span>Current SHA-256 Digest (RFC 8785 JCS)</span>
                <button
                  onClick={() => handleCopy(record.entry_hash, 'entry_hash')}
                  className="flex items-center gap-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] cursor-pointer"
                >
                  {copiedField === 'entry_hash' ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-500" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" /> Copy Hash
                    </>
                  )}
                </button>
              </div>
              <div className="p-2 rounded-xs bg-[var(--bg-canvas)] border border-[var(--border-subtle)] font-mono text-xs text-[var(--text-primary)] break-all">
                {record.entry_hash}
              </div>
            </div>

            {/* Previous Record Hash */}
            <div>
              <div className="flex items-center justify-between text-xs font-mono text-[var(--text-muted)] mb-1">
                <span>Previous SHA-256 Digest</span>
                <button
                  onClick={() => handleCopy(record.prev_hash, 'prev_hash')}
                  className="flex items-center gap-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] cursor-pointer"
                >
                  {copiedField === 'prev_hash' ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-500" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" /> Copy Hash
                    </>
                  )}
                </button>
              </div>
              <div className="p-2 rounded-xs bg-[var(--bg-canvas)] border border-[var(--border-subtle)] font-mono text-xs text-[var(--text-muted)] break-all">
                {isGenesis ? (
                  <span className="text-[var(--text-primary)] font-semibold">GENESIS_CHECKPOINT</span>
                ) : (
                  record.prev_hash
                )}
              </div>
            </div>

            {/* HMAC Signature */}
            <div>
              <div className="flex items-center justify-between text-xs font-mono text-[var(--text-muted)] mb-1">
                <span className="flex items-center gap-1">
                  <Key className="w-3 h-3 text-[var(--text-muted)]" />
                  HMAC-SHA256 Authentication Tag
                </span>
                <span className="text-xs text-[var(--text-muted)]">
                  Key: {record.key_id || 'piis-audit-key'}
                </span>
              </div>
              <div className="p-2 rounded-xs bg-[var(--bg-canvas)] border border-[var(--border-subtle)] font-mono text-xs text-[var(--text-primary)] break-all">
                {record.hmac_signature || (
                  <span className="text-[var(--text-muted)] italic">
                    HMAC Present: {record.has_hmac ? 'YES' : 'NO'}
                  </span>
                )}
              </div>
            </div>

            {/* Reviewer Auth Hash */}
            {record.reviewer_auth_hash && (
              <div>
                <span className="text-xs font-mono text-[var(--text-muted)] block mb-1">
                  Reviewer Token Thumbprint (Truncated SHA-256)
                </span>
                <div className="p-2 rounded-xs bg-[var(--bg-canvas)] border border-[var(--border-subtle)] font-mono text-xs text-[var(--text-primary)] truncate">
                  {record.reviewer_auth_hash}
                </div>
              </div>
            )}
          </div>

          {/* RFC 8785 Canonical JSON Serialization View */}
          <div className="rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-1.5">
                <Code2 className="w-4 h-4 text-[var(--text-muted)]" />
                RFC 8785 Canonical JSON Serialization (JCS)
              </span>
              <button
                onClick={() => setShowCanonicalJson(!showCanonicalJson)}
                className="text-xs font-mono text-[var(--text-secondary)] hover:text-[var(--text-primary)] cursor-pointer"
              >
                {showCanonicalJson ? 'Hide JCS' : 'Show JCS'}
              </button>
            </div>
            {showCanonicalJson && (
              <pre className="p-3 rounded-xs bg-[var(--bg-canvas)] border border-[var(--border-subtle)] font-mono text-xs text-[var(--text-secondary)] overflow-x-auto leading-relaxed">
                {JSON.stringify(canonicalPayload, null, 2)}
              </pre>
            )}
            <p className="text-xs text-[var(--text-muted)] mt-2 italic">
              Keys are sorted deterministically and encoded per RFC 8785. Whitespace in canonical hash computation is stripped. Secret keys and credentials are never included.
            </p>
          </div>

          {/* Security & Boundary Notice */}
          <div className="p-3.5 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-xs text-[var(--text-secondary)] space-y-1">
            <div className="font-semibold flex items-center gap-1.5 text-[var(--text-primary)]">
              <AlertTriangle className="w-4 h-4 text-[var(--text-muted)]" /> Cryptographic Trust Boundary
            </div>
            <p className="text-xs leading-normal text-[var(--text-muted)]">
              HMAC-SHA256 provides symmetric authentication with local host key material. It does not provide asymmetric digital signatures or external third-party non-repudiation.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="pt-3 border-t border-[var(--border-subtle)] flex items-center justify-between">
          <span className="text-xs font-mono text-[var(--text-muted)]">
            Read-Only Audit Ledger Record
          </span>
          <button
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-xs text-xs font-medium bg-[var(--bg-card)] hover:bg-[var(--bg-canvas)] border border-[var(--border-subtle)] transition-colors cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
