import React, { useState, useMemo } from 'react'
import {
  Search,
  FileCheck2,
  AlertTriangle,
  Clock,
  CheckCircle,
  XCircle,
  RefreshCw,
} from 'lucide-react'
import type { ReviewQueueItem } from '../../api/types'
import { StatusPill } from '../common/StatusPill'
import { SeverityBadge } from '../common/SeverityBadge'
import { DomainBadge } from '../common/DomainBadge'
import { EmptyState } from '../common/EmptyState'

interface ReviewQueueListProps {
  items: ReviewQueueItem[]
  selectedItem: ReviewQueueItem | null
  onSelectItem: (item: ReviewQueueItem) => void
  isLoading?: boolean
  pendingCount?: number
  approvedCount?: number
  rejectedCount?: number
  onRefresh?: () => void
}

export const ReviewQueueList: React.FC<ReviewQueueListProps> = ({
  items,
  selectedItem,
  onSelectItem,
  isLoading = false,
  pendingCount = 0,
  approvedCount = 0,
  rejectedCount = 0,
  onRefresh,
}) => {
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('ALL')
  const [domainFilter, setDomainFilter] = useState<string>('ALL')
  const [riskFilter, setRiskFilter] = useState<string>('ALL')
  const [sortBy, setSortBy] = useState<'newest' | 'oldest' | 'severity' | 'risk'>('newest')

  // Filter & Sort
  const filteredItems = useMemo(() => {
    let result = [...items]

    // Text search
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase().trim()
      result = result.filter(
        (i) =>
          i.recommendation_id.toLowerCase().includes(q) ||
          i.incident_id.toLowerCase().includes(q) ||
          i.description.toLowerCase().includes(q) ||
          i.source_runbook_id.toLowerCase().includes(q)
      )
    }

    // Status filter
    if (statusFilter !== 'ALL') {
      result = result.filter((i) => i.approval_status.toUpperCase() === statusFilter)
    }

    // Domain filter
    if (domainFilter !== 'ALL') {
      result = result.filter((i) => (i.network_domain || '').toUpperCase() === domainFilter)
    }

    // Risk filter
    if (riskFilter !== 'ALL') {
      result = result.filter((i) => (i.risk_classification || '').toUpperCase() === riskFilter)
    }

    // Sorting
    result.sort((a, b) => {
      if (sortBy === 'newest') {
        return (b.created_at || '').localeCompare(a.created_at || '')
      }
      if (sortBy === 'oldest') {
        return (a.created_at || '').localeCompare(b.created_at || '')
      }
      if (sortBy === 'severity') {
        const order: Record<string, number> = { CRITICAL: 4, MAJOR: 3, MINOR: 2, WARNING: 1 }
        return (order[b.incident_severity] || 0) - (order[a.incident_severity] || 0)
      }
      if (sortBy === 'risk') {
        const order: Record<string, number> = {
          HIGH_RISK_MANUAL: 4,
          DISRUPTIVE_AUDIT: 3,
          LOW_OBSERVABILITY: 2,
          READ_ONLY_SAFE: 1,
        }
        return (order[b.risk_classification] || 0) - (order[a.risk_classification] || 0)
      }
      return 0
    })

    return result
  }, [items, searchTerm, statusFilter, domainFilter, riskFilter, sortBy])

  return (
    <div className="space-y-4" role="region" aria-label="Review Queue Explorer">
      {/* 1. Queue Metrics Bar */}
      <div className="grid grid-cols-4 gap-2 text-xs">
        <div className="p-2.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] space-y-0.5">
          <div className="text-xs text-[var(--text-muted)] font-mono uppercase">Total Queue</div>
          <div className="text-base font-bold font-mono text-[var(--text-primary)]">
            {items.length}
          </div>
        </div>

        <div className="p-2.5 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] space-y-0.5">
          <div className="text-xs text-amber-500 font-mono uppercase flex items-center gap-1">
            <Clock className="w-3 h-3" />
            <span>Pending</span>
          </div>
          <div className="text-base font-bold font-mono text-amber-500">
            {pendingCount}
          </div>
        </div>

        <div className="p-2.5 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] space-y-0.5">
          <div className="text-xs text-emerald-500 font-mono uppercase flex items-center gap-1">
            <CheckCircle className="w-3 h-3" />
            <span>Approved</span>
          </div>
          <div className="text-base font-bold font-mono text-emerald-500">
            {approvedCount}
          </div>
        </div>

        <div className="p-2.5 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] space-y-0.5">
          <div className="text-xs text-rose-500 font-mono uppercase flex items-center gap-1">
            <XCircle className="w-3 h-3" />
            <span>Rejected</span>
          </div>
          <div className="text-base font-bold font-mono text-rose-500">
            {rejectedCount}
          </div>
        </div>
      </div>

      {/* 2. Search & Controls */}
      <div className="space-y-2.5">
        <div className="relative">
          <Search className="w-4 h-4 text-[var(--text-muted)] absolute left-3 top-2.5" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search by REC ID, incident, runbook, or keyword..."
            aria-label="Search review recommendations"
            className="w-full pl-9 pr-3 py-2 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] font-mono focus:outline-hidden focus:ring-1 focus:ring-[var(--border-strong)]"
          />
        </div>

        {/* Filters and Sorting Bar */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {/* Status Select */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label="Filter by approval status"
            className="p-1.5 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] font-mono"
          >
            <option value="ALL">Status: All</option>
            <option value="PENDING_REVIEW">Pending Review</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
          </select>

          {/* Domain Select */}
          <select
            value={domainFilter}
            onChange={(e) => setDomainFilter(e.target.value)}
            aria-label="Filter by network domain"
            className="p-1.5 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] font-mono"
          >
            <option value="ALL">Domain: All</option>
            <option value="RAN">RAN</option>
            <option value="5G_CORE">5G Core</option>
            <option value="TRANSPORT">Transport</option>
            <option value="SERVICE">Service</option>
            <option value="CROSS_DOMAIN">Cross Domain</option>
          </select>

          {/* Risk Select */}
          <select
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value)}
            aria-label="Filter by risk tier"
            className="p-1.5 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] font-mono"
          >
            <option value="ALL">Risk: All</option>
            <option value="READ_ONLY_SAFE">Read-Only Safe</option>
            <option value="LOW_OBSERVABILITY">Low Observability</option>
            <option value="DISRUPTIVE_AUDIT">Disruptive Audit</option>
            <option value="HIGH_RISK_MANUAL">High Risk Manual</option>
          </select>

          {/* Sort Select */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as 'newest' | 'oldest' | 'severity' | 'risk')}
            aria-label="Sort queue items"
            className="p-1.5 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] font-mono ml-auto"
          >
            <option value="newest">Sort: Newest First</option>
            <option value="oldest">Sort: Oldest First</option>
            <option value="severity">Sort: Severity</option>
            <option value="risk">Sort: Risk Tier</option>
          </select>

          {onRefresh && (
            <button
              onClick={onRefresh}
              aria-label="Refresh queue"
              className="p-1.5 rounded-xs border border-[var(--border-subtle)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
              title="Refresh queue"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          )}
        </div>
      </div>

      {/* 3. Items List */}
      <div className="space-y-2.5 max-h-[calc(100vh-320px)] overflow-y-auto pr-1">
        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((n) => (
              <div
                key={n}
                className="p-4 rounded-xs border border-[var(--border-subtle)] bg-[var(--bg-surface)] animate-pulse space-y-2"
              >
                <div className="h-4 bg-[var(--border-subtle)] rounded-xs w-1/3" />
                <div className="h-3 bg-[var(--border-subtle)] rounded-xs w-3/4" />
                <div className="h-3 bg-[var(--border-subtle)] rounded-xs w-1/2" />
              </div>
            ))}
          </div>
        ) : filteredItems.length === 0 ? (
          <EmptyState
            icon={<FileCheck2 className="w-6 h-6" />}
            title={items.length === 0 ? 'Review Queue Empty' : 'No Matching Recommendations'}
            description={
              items.length === 0
                ? 'No actionable diagnostic recommendations currently awaiting review. Recommendations are generated when incidents are investigated.'
                : 'No recommendations matched your search query or filter criteria. Try adjusting the filter settings.'
            }
          />
        ) : (
          filteredItems.map((item) => {
            const isSelected = selectedItem?.recommendation_id === item.recommendation_id
            return (
              <div
                key={item.recommendation_id}
                role="button"
                tabIndex={0}
                onClick={() => onSelectItem(item)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    onSelectItem(item)
                  }
                }}
                className={`p-3.5 rounded-xs border cursor-pointer transition-all space-y-2 text-left ${
                  isSelected
                    ? 'bg-[var(--bg-card)] border-[var(--text-primary)] ring-1 ring-[var(--text-primary)]/40'
                    : 'bg-[var(--bg-surface)] border-[var(--border-subtle)] hover:bg-[var(--bg-card)]'
                }`}
              >
                {/* Header row */}
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-semibold text-[var(--text-primary)]">
                      {item.recommendation_id}
                    </span>
                    <span className="font-mono text-[var(--text-muted)] text-xs">
                      ({item.incident_id})
                    </span>
                  </div>
                  <StatusPill state={item.approval_status} size="sm" />
                </div>

                {/* Description */}
                <h4 className="text-xs font-semibold text-[var(--text-primary)] line-clamp-2 leading-relaxed">
                  {item.description}
                </h4>

                {/* Badges footer */}
                <div className="flex flex-wrap items-center justify-between gap-1.5 pt-1 text-xs font-mono">
                  <div className="flex items-center gap-1.5">
                    <SeverityBadge severity={item.incident_severity} size="sm" />
                    <DomainBadge domain={item.network_domain} size="sm" />
                  </div>

                  <div className="flex items-center gap-1.5">
                    {item.has_contradictions && (
                      <span
                        className="flex items-center gap-1 text-amber-500 font-bold px-1.5 py-0.5 rounded-xs bg-amber-500/10"
                        title="Contradictory evidence detected"
                      >
                        <AlertTriangle className="w-3 h-3" />
                        <span>CONTRADICTORY</span>
                      </span>
                    )}
                    <span className="text-[var(--text-muted)] font-semibold">
                      {item.risk_classification}
                    </span>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
