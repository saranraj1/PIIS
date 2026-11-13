import React, { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  ShieldCheck,
  Hash,
  Database,
  ArrowUpDown,
  Search,
  Filter,
  Eye,
  ChevronLeft,
  ChevronRight,
  Key,
  Calendar,
} from 'lucide-react'
import { apiClient } from '../api/client'
import { API_ENDPOINTS } from '../api/endpoints'
import type {
  AuditRecordItem,
  AuditSummaryResponse,
  AuditVerificationResponse,
  PaginatedResponse,
} from '../api/types'
import { EpistemicBadge } from '../components/epistemic/EpistemicBadge'
import { LedgerVerificationCard } from '../components/audit/LedgerVerificationCard'
import { AuditProvenanceFlow } from '../components/audit/AuditProvenanceFlow'
import { AuditRecordDetailDrawer } from '../components/audit/AuditRecordDetailDrawer'
import { EmptyState } from '../components/common/EmptyState'
import { ErrorState } from '../components/common/ErrorState'

const PAGE_SIZE = 10

export const AuditLedgerPage: React.FC = () => {
  // Filters & Pagination State
  const [incidentFilter, setIncidentFilter] = useState<string>('')
  const [actionFilter, setActionFilter] = useState<string>('ALL')
  const [operatorFilter, setOperatorFilter] = useState<string>('')
  const [order, setOrder] = useState<'desc' | 'asc'>('desc')
  const [pageOffset, setPageOffset] = useState<number>(0)

  // Selected Record & Drawer State
  const [selectedRecord, setSelectedRecord] = useState<AuditRecordItem | null>(null)
  const [isDetailDrawerOpen, setIsDetailDrawerOpen] = useState<boolean>(false)

  // 1. Fetch Summary Metrics
  const {
    data: summary,
    isLoading: isLoadingSummary,
  } = useQuery<AuditSummaryResponse>({
    queryKey: ['audit-summary'],
    queryFn: () => apiClient.get<AuditSummaryResponse>(API_ENDPOINTS.AUDIT_SUMMARY),
  })

  // 2. Fetch Paginated Records with Filters
  const {
    data: paginatedData,
    isLoading: isLoadingRecords,
    error: recordsError,
    refetch: refetchRecords,
  } = useQuery<PaginatedResponse<AuditRecordItem>>({
    queryKey: [
      'audit-records',
      pageOffset,
      incidentFilter,
      actionFilter,
      operatorFilter,
      order,
    ],
    queryFn: () => {
      const params = new URLSearchParams()
      params.set('limit', String(PAGE_SIZE))
      params.set('offset', String(pageOffset))
      params.set('order', order)
      if (incidentFilter.trim()) {
        params.set('incident_id', incidentFilter.trim())
      }
      if (actionFilter !== 'ALL') {
        params.set('action', actionFilter)
      }
      if (operatorFilter.trim()) {
        params.set('operator_id', operatorFilter.trim())
      }
      return apiClient.get<PaginatedResponse<AuditRecordItem>>(
        `${API_ENDPOINTS.AUDIT_RECORDS}?${params.toString()}`
      )
    },
  })

  // 3. Triggerable Verification Mutation
  const verifyMutation = useMutation<AuditVerificationResponse, Error>({
    mutationFn: () => apiClient.get<AuditVerificationResponse>(API_ENDPOINTS.AUDIT_VERIFY),
  })

  const records = paginatedData?.items || []
  const totalCount = paginatedData?.total_count ?? 0
  const totalPages = Math.ceil(totalCount / PAGE_SIZE)
  const currentPage = Math.floor(pageOffset / PAGE_SIZE) + 1

  const handleSelectRecord = (record: AuditRecordItem) => {
    setSelectedRecord(record)
    setIsDetailDrawerOpen(true)
  }

  const handleResetFilters = () => {
    setIncidentFilter('')
    setActionFilter('ALL')
    setOperatorFilter('')
    setPageOffset(0)
  }

  return (
    <div className="space-y-6">
      {/* Workspace Header Notice */}
      <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 flex flex-wrap items-center justify-between gap-3 transition-colors">
        <div>
          <h1 className="text-sm font-bold text-[var(--text-primary)] font-mono uppercase tracking-wider">
            Audit Ledger Workspace
          </h1>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            Tamper-evident RFC 8785 JSON Canonicalization, SHA-256 hash-chaining, HMAC-SHA256 authenticated logging, and local monotonic checkpoint parity.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded-xs text-xs font-mono font-medium bg-[var(--bg-subtle)] text-[var(--text-secondary)] border border-[var(--border-subtle)]">
            READ-ONLY DECISION SUPPORT
          </span>
        </div>
      </div>

      {/* Screen 1: Ledger Overview Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-3">
        <div className="p-3.5 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] transition-colors">
          <span className="text-xs font-medium text-[var(--text-secondary)] flex items-center gap-1.5 mb-1">
            <Database className="w-3.5 h-3.5 text-[var(--text-muted)]" /> Total Ledger Blocks
          </span>
          <span className="text-lg font-mono tabular-nums font-bold text-[var(--text-primary)]">
            {isLoadingSummary ? '...' : (summary?.total_records ?? 0)}
          </span>
          <span className="text-xs text-[var(--text-muted)] block mt-0.5">
            Append-only JSONL
          </span>
        </div>

        <div className="p-3.5 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] transition-colors">
          <span className="text-xs font-medium text-[var(--text-secondary)] flex items-center gap-1.5 mb-1">
            <Hash className="w-3.5 h-3.5 text-[var(--text-muted)]" /> Latest Sequence
          </span>
          <span className="text-lg font-mono tabular-nums font-bold text-[var(--text-primary)]">
            {isLoadingSummary ? '...' : `#${summary?.latest_sequence ?? 0}`}
          </span>
          <span className="text-xs text-[var(--text-muted)] block mt-0.5">
            Monotonic Head
          </span>
        </div>

        <div className="p-3.5 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] transition-colors">
          <span className="text-xs font-medium text-[var(--text-secondary)] flex items-center gap-1.5 mb-1">
            <ShieldCheck className="w-3.5 h-3.5 text-[var(--text-muted)]" /> Anchor Sequence
          </span>
          <span className="text-lg font-mono tabular-nums font-bold text-[var(--text-primary)]">
            {summary?.anchor_present
              ? `#${summary.anchor_sequence ?? 0}`
              : 'NONE'}
          </span>
          <span className="text-xs text-[var(--text-muted)] block mt-0.5">
            Local Monotonic Parity
          </span>
        </div>

        <div className="p-3.5 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] transition-colors">
          <span className="text-xs font-medium text-[var(--text-secondary)] flex items-center gap-1.5 mb-1">
            <Key className="w-3.5 h-3.5 text-[var(--text-muted)]" /> Canonicalization
          </span>
          <span className="text-xs font-mono font-bold text-[var(--text-primary)] truncate block mt-1">
            RFC 8785 (JCS)
          </span>
          <span className="text-xs text-[var(--text-muted)] block mt-1">
            Deterministic Hashes
          </span>
        </div>

        <div className="p-3.5 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] col-span-2 sm:col-span-4 lg:col-span-1 transition-colors">
          <span className="text-xs font-medium text-[var(--text-secondary)] flex items-center gap-1.5 mb-1">
            <Calendar className="w-3.5 h-3.5 text-[var(--text-muted)]" /> Latest Activity
          </span>
          <span className="text-xs font-mono tabular-nums text-[var(--text-primary)] block mt-1 truncate">
            {summary?.latest_timestamp || 'No Records Recorded'}
          </span>
          <span className="text-xs text-[var(--text-muted)] block mt-1">
            UTC System Timestamp
          </span>
        </div>
      </div>

      {/* Screen 4: Dedicated Integrity Verification Panel */}
      <LedgerVerificationCard
        verificationResult={verifyMutation.data ?? null}
        isVerifying={verifyMutation.isPending}
        onTriggerVerification={() => verifyMutation.mutate()}
        verificationError={verifyMutation.error ? verifyMutation.error.message : null}
      />

      {/* Screen 5: Audit Provenance Flow Pipeline */}
      <AuditProvenanceFlow
        record={selectedRecord || (records.length > 0 ? records[0] : null)}
        anchorSequence={summary?.anchor_sequence}
      />

      {/* Screen 2: Audit Record Explorer */}
      <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] overflow-hidden transition-colors">
        {/* Explorer Header & Filters Bar */}
        <div className="p-4 border-b border-[var(--border-subtle)] space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-[var(--text-primary)] font-mono uppercase tracking-wider flex items-center gap-2">
                <Hash className="w-4 h-4 text-[var(--text-primary)]" /> Audit Ledger Chronological Blocks
              </h2>
              <span className="text-xs font-mono tabular-nums text-[var(--text-muted)]">
                ({totalCount} Total)
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setOrder(order === 'desc' ? 'asc' : 'desc')}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xs text-xs font-mono bg-[var(--bg-subtle)] hover:bg-[var(--border-subtle)] border border-[var(--border-subtle)] text-[var(--text-primary)] transition-colors cursor-pointer"
                title="Toggle sequence sort order"
              >
                <ArrowUpDown className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                {order === 'desc' ? 'Desc (Newest)' : 'Asc (Oldest)'}
              </button>
            </div>
          </div>

          {/* Filter Inputs Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
            {/* Incident Filter */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-[var(--text-muted)] absolute left-2.5 top-2.5" />
              <input
                type="text"
                placeholder="Filter by Incident ID..."
                value={incidentFilter}
                onChange={(e) => {
                  setIncidentFilter(e.target.value)
                  setPageOffset(0)
                }}
                className="w-full pl-8 pr-3 py-1.5 rounded-xs text-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--border-strong)] font-mono"
              />
            </div>

            {/* Operator Filter */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-[var(--text-muted)] absolute left-2.5 top-2.5" />
              <input
                type="text"
                placeholder="Filter by Operator ID..."
                value={operatorFilter}
                onChange={(e) => {
                  setOperatorFilter(e.target.value)
                  setPageOffset(0)
                }}
                className="w-full pl-8 pr-3 py-1.5 rounded-xs text-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--border-strong)] font-mono"
              />
            </div>

            {/* Action Dropdown */}
            <div className="relative">
              <Filter className="w-3.5 h-3.5 text-[var(--text-muted)] absolute left-2.5 top-2.5" />
              <select
                value={actionFilter}
                onChange={(e) => {
                  setActionFilter(e.target.value)
                  setPageOffset(0)
                }}
                className="w-full pl-8 pr-3 py-1.5 rounded-xs text-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--border-strong)] font-mono cursor-pointer"
              >
                <option value="ALL">All Action Types</option>
                <option value="APPROVED">APPROVED (Human Concurrence)</option>
                <option value="REJECTED">REJECTED (Human Disapproval)</option>
                <option value="SUBMITTED">SUBMITTED (Model Proposal)</option>
                <option value="MODIFIED">MODIFIED (Human Tailored)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Records Table or Empty/Error States */}
        {recordsError ? (
          <div className="p-6">
            <ErrorState
              error={recordsError}
              title="Failed to Load Audit Ledger Records"
              onRetry={() => refetchRecords()}
            />
          </div>
        ) : isLoadingRecords ? (
          <div className="p-8 text-center text-xs font-mono text-[var(--text-muted)] animate-pulse">
            Loading cryptographic audit records from ledger...
          </div>
        ) : records.length === 0 ? (
          <div className="p-6">
            <EmptyState
              title="No Audit Records Found"
              description={
                incidentFilter || actionFilter !== 'ALL' || operatorFilter
                  ? 'No records match your active search filters. Try clearing or relaxing the criteria.'
                  : 'The audit ledger is currently empty (Genesis state). Ingested recommendations and human reviews will record immutable blocks here.'
              }
              actionLabel={
                incidentFilter || actionFilter !== 'ALL' || operatorFilter
                  ? 'Reset Filters'
                  : undefined
              }
              onAction={handleResetFilters}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-[var(--bg-subtle)] border-b border-[var(--border-subtle)] text-[var(--text-muted)] uppercase text-xs">
                <tr>
                  <th className="px-4 py-2.5 font-semibold">Block Seq</th>
                  <th className="px-4 py-2.5 font-semibold">Timestamp (UTC)</th>
                  <th className="px-4 py-2.5 font-semibold">Action Type</th>
                  <th className="px-4 py-2.5 font-semibold">Actor Principal</th>
                  <th className="px-4 py-2.5 font-semibold">Incident Ref</th>
                  <th className="px-4 py-2.5 font-semibold">Recommendation Ref</th>
                  <th className="px-4 py-2.5 font-semibold">SHA-256 Digest</th>
                  <th className="px-4 py-2.5 font-semibold">Previous Hash</th>
                  <th className="px-4 py-2.5 font-semibold text-right">Inspect</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)] font-sans">
                {records.map((entry) => {
                  const isApprove = entry.action === 'APPROVED'
                  const isReject = entry.action === 'REJECTED'
                  const isSubmit = entry.action === 'SUBMITTED'
                  const isGenesis =
                    entry.sequence_number === 1 || entry.prev_hash === 'GENESIS_CHECKPOINT'

                  return (
                    <tr
                      key={entry.sequence_number}
                      onClick={() => handleSelectRecord(entry)}
                      className="hover:bg-[var(--bg-subtle)] transition-colors cursor-pointer group"
                    >
                      <td className="px-4 py-3 font-mono tabular-nums font-bold text-[var(--text-primary)]">
                        #{String(entry.sequence_number).padStart(6, '0')}
                      </td>
                      <td className="px-4 py-3 font-mono tabular-nums text-[var(--text-muted)] text-xs whitespace-nowrap">
                        {entry.timestamp}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          <span className="font-semibold text-[var(--text-primary)]">
                            {entry.action || entry.decision}
                          </span>
                          {isApprove ? (
                            <EpistemicBadge category="HUMAN_APPROVED_DECISION" size="sm" />
                          ) : isSubmit ? (
                            <EpistemicBadge category="MODEL_PREDICTION" size="sm" />
                          ) : isReject ? (
                            <span className="px-1.5 py-0.5 rounded-xs text-xs font-mono bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
                              REJECTED
                            </span>
                          ) : (
                            <EpistemicBadge category="OBSERVED_FACT" size="sm" />
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 font-mono text-[var(--text-primary)] text-xs">
                        {entry.operator_id}
                        {entry.reviewer_role && (
                          <span className="text-[var(--text-muted)] text-xs block">
                            {entry.reviewer_role}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono tabular-nums text-[var(--text-primary)] text-xs">
                        {entry.incident_id || <span className="text-[var(--text-muted)] italic">N/A</span>}
                      </td>
                      <td className="px-4 py-3 font-mono tabular-nums text-[var(--text-muted)] text-xs">
                        {entry.recommendation_id || <span className="italic">N/A</span>}
                      </td>
                      <td className="px-4 py-3 font-mono tabular-nums text-emerald-600 dark:text-emerald-400 text-xs truncate max-w-[120px]" title={entry.entry_hash}>
                        {entry.entry_hash.slice(0, 12)}...
                      </td>
                      <td className="px-4 py-3 font-mono tabular-nums text-[var(--text-muted)] text-xs truncate max-w-[120px]" title={entry.prev_hash}>
                        {isGenesis ? 'GENESIS' : `${entry.prev_hash.slice(0, 10)}...`}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleSelectRecord(entry)
                          }}
                          className="p-1 rounded-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface)] transition-colors"
                          aria-label={`Inspect record #${entry.sequence_number}`}
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Sub-Bar */}
        <div className="px-4 py-3 border-t border-[var(--border-subtle)] bg-[var(--bg-subtle)] flex items-center justify-between text-xs font-mono">
          <span className="text-[var(--text-muted)] tabular-nums">
            Showing {records.length > 0 ? pageOffset + 1 : 0} to{' '}
            {Math.min(pageOffset + PAGE_SIZE, totalCount)} of {totalCount} records
          </span>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setPageOffset(Math.max(0, pageOffset - PAGE_SIZE))}
              disabled={pageOffset === 0 || isLoadingRecords}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xs text-xs bg-[var(--bg-surface)] hover:bg-[var(--border-subtle)] disabled:opacity-40 border border-[var(--border-subtle)] text-[var(--text-primary)] transition-colors cursor-pointer disabled:cursor-not-allowed font-mono"
            >
              <ChevronLeft className="w-3.5 h-3.5" /> Previous
            </button>

            <span className="text-[var(--text-muted)] tabular-nums">
              Page {totalCount > 0 ? currentPage : 0} of {totalPages || 1}
            </span>

            <button
              onClick={() => setPageOffset(pageOffset + PAGE_SIZE)}
              disabled={pageOffset + PAGE_SIZE >= totalCount || isLoadingRecords}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xs text-xs bg-[var(--bg-surface)] hover:bg-[var(--border-subtle)] disabled:opacity-40 border border-[var(--border-subtle)] text-[var(--text-primary)] transition-colors cursor-pointer disabled:cursor-not-allowed font-mono"
            >
              Next <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Screen 3: Detail Drawer Modal */}
      <AuditRecordDetailDrawer
        record={selectedRecord}
        isOpen={isDetailDrawerOpen}
        onClose={() => setIsDetailDrawerOpen(false)}
      />
    </div>
  )
}
