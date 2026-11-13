import React from 'react'
import {
  ShieldCheck,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  Lock,
  Link as LinkIcon,
  Anchor,
  FileCheck,
} from 'lucide-react'
import type { AuditVerificationResponse } from '../../api/types'
import { EpistemicBadge } from '../epistemic/EpistemicBadge'

interface LedgerVerificationCardProps {
  verificationResult: AuditVerificationResponse | null
  isVerifying: boolean
  onTriggerVerification: () => void
  verificationError?: string | null
}

export const LedgerVerificationCard: React.FC<LedgerVerificationCardProps> = ({
  verificationResult,
  isVerifying,
  onTriggerVerification,
  verificationError,
}) => {
  const status = verificationResult
    ? verificationResult.verification_status
    : 'NOT_YET_VERIFIED'

  return (
    <div className="rounded-sm bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 space-y-4">
      {/* Card Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--border-subtle)]">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xs bg-[var(--bg-subtle)] text-[var(--text-muted)] border border-[var(--border-subtle)]">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-[var(--text-primary)]">
                Ledger Cryptographic Integrity & Monotonic Parity
              </h2>
              <EpistemicBadge category="OBSERVED_FACT" size="sm" />
            </div>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Deterministic verification across SHA-256 hash chaining, RFC 8785 canonicalization, HMAC-SHA256 authentication, and local checkpoint anchor head.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onTriggerVerification}
            disabled={isVerifying}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xs text-xs font-semibold bg-[var(--text-primary)] text-[var(--bg-surface)] hover:opacity-90 disabled:opacity-50 transition-all cursor-pointer disabled:cursor-not-allowed"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isVerifying ? 'animate-spin' : ''}`} />
            {isVerifying ? 'Verifying Entire Ledger...' : 'Run Cryptographic Verification'}
          </button>
        </div>
      </div>

      {/* Main Verification Status Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Verification Status Overall */}
        <div className="p-3.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)]">
          <span className="text-xs font-mono uppercase text-[var(--text-muted)] block mb-1">
            Verification Verdict
          </span>
          {isVerifying ? (
            <span className="text-xs font-mono font-medium text-[var(--text-primary)] flex items-center gap-1.5 animate-pulse">
              <RefreshCw className="w-4 h-4 text-[var(--text-muted)] animate-spin" /> VERIFYING BLOCKS...
            </span>
          ) : verificationError ? (
            <span className="text-xs font-mono font-medium text-[var(--text-primary)] flex items-center gap-1.5">
              <AlertCircle className="w-4 h-4 text-rose-500" /> VERIFICATION FAILED
            </span>
          ) : status === 'VERIFIED' ? (
            <span className="text-xs font-mono font-medium text-[var(--text-primary)] flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-500" /> VERIFIED & INTACT
            </span>
          ) : status === 'FAILED' ? (
            <span className="text-xs font-mono font-medium text-[var(--text-primary)] flex items-center gap-1.5">
              <AlertCircle className="w-4 h-4 text-rose-500" /> INTEGRITY FAILED
            </span>
          ) : status === 'UNAVAILABLE' ? (
            <span className="text-xs font-mono font-medium text-[var(--text-primary)] flex items-center gap-1.5">
              <HelpCircle className="w-4 h-4 text-amber-500" /> VERIFICATION UNAVAILABLE
            </span>
          ) : status === 'INCOMPLETE' ? (
            <span className="text-xs font-mono font-medium text-[var(--text-primary)] flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-amber-500" /> INCOMPLETE LEDGER
            </span>
          ) : (
            <span className="text-xs font-mono font-medium text-[var(--text-muted)] flex items-center gap-1.5">
              <Lock className="w-4 h-4 text-[var(--text-muted)]" /> NOT YET VERIFIED
            </span>
          )}
        </div>

        {/* Blocks Checked */}
        <div className="p-3.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)]">
          <span className="text-xs font-mono uppercase text-[var(--text-muted)] block mb-1">
            Blocks Inspected
          </span>
          <span className="text-sm font-mono font-bold text-[var(--text-primary)]">
            {verificationResult?.records_checked ?? 0} / {verificationResult?.total_records ?? 0}
          </span>
          <span className="text-xs text-[var(--text-muted)] block mt-0.5">
            {verificationResult?.first_sequence && verificationResult?.last_sequence
              ? `Seq #${verificationResult.first_sequence} → #${verificationResult.last_sequence}`
              : 'Zero Records Checked'}
          </span>
        </div>

        {/* SHA-256 Hash Chain Continuity */}
        <div className="p-3.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)]">
          <span className="text-xs font-mono uppercase text-[var(--text-muted)] block mb-1 flex items-center gap-1">
            <LinkIcon className="w-3 h-3 text-[var(--text-muted)]" /> Hash Chain Continuity
          </span>
          {verificationResult?.hash_chain_valid ? (
            <span className="text-xs font-mono font-medium text-[var(--text-primary)] flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> MONOTONIC & UNBROKEN
            </span>
          ) : verificationResult ? (
            <span className="text-xs font-mono font-medium text-[var(--text-primary)] flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5 text-rose-500" /> BROKEN HASH LINK
            </span>
          ) : (
            <span className="text-xs font-mono text-[var(--text-muted)]">PENDING AUDIT</span>
          )}
          <span className="text-xs text-[var(--text-muted)] block mt-0.5">
            SHA-256 sequential linking
          </span>
        </div>

        {/* Checkpoint Anchor Parity */}
        <div className="p-3.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)]">
          <span className="text-xs font-mono uppercase text-[var(--text-muted)] block mb-1 flex items-center gap-1">
            <Anchor className="w-3 h-3 text-[var(--text-muted)]" /> Checkpoint Anchor Parity
          </span>
          {verificationResult?.checkpoint_parity_valid ? (
            <span className="text-xs font-mono font-medium text-[var(--text-primary)] flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> SYNCHRONIZED HEAD
            </span>
          ) : verificationResult ? (
            <span className="text-xs font-mono font-medium text-[var(--text-primary)] flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5 text-rose-500" /> ANCHOR DESYNCHRONIZED
            </span>
          ) : (
            <span className="text-xs font-mono text-[var(--text-muted)]">PENDING AUDIT</span>
          )}
          <span className="text-xs text-[var(--text-muted)] block mt-0.5">
            Anchor Seq: #{verificationResult?.anchor_sequence ?? 0}
          </span>
        </div>
      </div>

      {/* Verification Breakdown Checklist */}
      {verificationResult && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
          <div className="p-2.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] flex items-center justify-between">
            <span className="text-xs font-mono text-[var(--text-secondary)] flex items-center gap-1.5">
              <FileCheck className="w-3.5 h-3.5 text-[var(--text-muted)]" /> RFC 8785 Canonicalization
            </span>
            {verificationResult.jcs_canonicalization_valid ? (
              <span className="inline-flex items-center gap-1 text-xs font-mono text-[var(--text-primary)] font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> VALID
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-xs font-mono text-[var(--text-primary)] font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500" /> TAMPERED
              </span>
            )}
          </div>

          <div className="p-2.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] flex items-center justify-between">
            <span className="text-xs font-mono text-[var(--text-secondary)] flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-[var(--text-muted)]" /> HMAC-SHA256 Signatures
            </span>
            {verificationResult.hmac_signatures_valid ? (
              <span className="inline-flex items-center gap-1 text-xs font-mono text-[var(--text-primary)] font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> VALIDATED
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-xs font-mono text-[var(--text-primary)] font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500" /> INVALID / UNAVAIL
              </span>
            )}
          </div>

          <div className="p-2.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] flex items-center justify-between">
            <span className="text-xs font-mono text-[var(--text-secondary)] flex items-center gap-1.5">
              <Anchor className="w-3.5 h-3.5 text-[var(--text-muted)]" /> Monotonic Anchor Guard
            </span>
            <span className="inline-flex items-center gap-1 text-xs font-mono text-[var(--text-primary)] font-medium">
              <span className={`w-1.5 h-1.5 rounded-full ${verificationResult.anchor_present ? 'bg-emerald-500' : 'bg-amber-500'}`} />
              {verificationResult.anchor_present ? 'ACTIVE' : 'NOT CONFIGURED'}
            </span>
          </div>
        </div>
      )}

      {/* Diagnostic Errors Alert Box */}
      {((verificationResult?.errors && verificationResult.errors.length > 0) || verificationError) && (
        <div className="p-4 rounded-xs bg-rose-500/10 border border-rose-500/30 text-rose-300 space-y-2">
          <div className="flex items-center gap-2 text-xs font-mono font-bold text-rose-400 uppercase">
            <AlertCircle className="w-4 h-4 text-rose-500" />
            Cryptographic Integrity Diagnostic Errors ({verificationResult?.errors?.length ?? 1})
          </div>
          <ul className="text-xs font-mono space-y-1 list-disc pl-5 text-rose-200">
            {verificationError && <li>{verificationError}</li>}
            {verificationResult?.errors?.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Cryptographic Scope & Trust Boundary Limitations Notice */}
      <div className="p-3.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs text-[var(--text-muted)] space-y-1">
        <div className="font-mono font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 text-[var(--text-muted)]" />
          Cryptographic Scope & Trust Boundary Limitations
        </div>
        <p>
          • <strong>Local Single-Process Scope:</strong> Verification validates internal consistency on this host node.
        </p>
        <p>
          • <strong>Filesystem Anchor Boundary:</strong> Local checkpoint anchors detect truncation and sequential fork anomalies within this filesystem, but cannot prevent coordinated host-level snapshot restoration.
        </p>
        <p>
          • <strong>Symmetric Authentication:</strong> HMAC-SHA256 provides symmetric authentication with local secret keys; it does not constitute asymmetric digital signatures or external non-repudiation.
        </p>
      </div>
    </div>
  )
}
