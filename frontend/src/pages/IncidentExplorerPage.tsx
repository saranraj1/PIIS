import React, { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search,
  Filter,
  RefreshCw,
  Eye,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  X,
  FileSearch,
  ExternalLink,
} from 'lucide-react'
import { useIncidentsQuery, useIncidentDetailQuery } from '../api/queries'
import { useIncidentContextStore } from '../store/incidentContextStore'
import { SeverityBadge } from '../components/common/SeverityBadge'
import { DomainBadge } from '../components/common/DomainBadge'
import { ErrorState } from '../components/common/ErrorState'
import { EmptyState } from '../components/common/EmptyState'

export const IncidentExplorerPage: React.FC = () => {
  const navigate = useNavigate()

  // Shared store state
  const {
    search,
    domain,
    severity,
    status,
    page,
    limit,
    sortBy,
    sortOrder,
    selectedIncidentId,
    setSearch,
    setDomain,
    setSeverity,
    setStatus,
    setPage,
    setLimit,
    setSorting,
    setSelectedIncidentId,
    resetFilters,
  } = useIncidentContextStore()

  // Query backend: pass domain and severity to backend when specified
  const {
    data: incidentsData,
    isLoading,
    isError,
    error,
    isStale,
    refetch,
  } = useIncidentsQuery({
    limit: 100, // Fetch up to 100 records within API limits for client-side text search and pagination
    domain: domain !== 'ALL' ? domain : undefined,
    severity: severity !== 'ALL' ? severity : undefined,
  })

  // Selected incident detail query
  const { data: detailData, isLoading: detailLoading } = useIncidentDetailQuery(selectedIncidentId)

  const incidentsList = incidentsData?.items

  // Client-side text search, status refinement, and sorting
  const processedIncidents = useMemo(() => {
    let result = incidentsList ? [...incidentsList] : []

    // 1. Text Search across ID, Title, Description, Fault Category, Elements
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      result = result.filter((inc) => {
        const idMatch = inc.incident_id.toLowerCase().includes(q)
        const titleMatch = (inc.title || '').toLowerCase().includes(q)
        const descMatch = (inc.description || '').toLowerCase().includes(q)
        const faultMatch = (inc.fault_category || '').toLowerCase().includes(q)
        const elemMatch = (inc.network_element_ids || []).some((e) => e.toLowerCase().includes(q))
        return idMatch || titleMatch || descMatch || faultMatch || elemMatch
      })
    }

    // 2. Severity Filter
    if (severity !== 'ALL') {
      result = result.filter((inc) => inc.severity?.toUpperCase() === severity.toUpperCase())
    }

    // 3. Domain Filter
    if (domain !== 'ALL') {
      result = result.filter((inc) => inc.network_domain?.toUpperCase() === domain.toUpperCase())
    }

    // 4. Status Filter: ACTIVE vs RESOLVED
    if (status !== 'ALL') {
      result = result.filter((inc) => {
        const isResolved = Boolean(inc.resolved_at)
        return status === 'RESOLVED' ? isResolved : !isResolved
      })
    }

    // 5. Sorting
    result.sort((a, b) => {
      let comparison = 0
      if (sortBy === 'created_at') {
        const timeA = a.created_at ? new Date(a.created_at).getTime() : 0
        const timeB = b.created_at ? new Date(b.created_at).getTime() : 0
        comparison = timeA - timeB
      } else if (sortBy === 'severity') {
        const weights: Record<string, number> = { CRITICAL: 4, MAJOR: 3, MINOR: 2, WARNING: 1 }
        const weightA = weights[a.severity?.toUpperCase()] || 0
        const weightB = weights[b.severity?.toUpperCase()] || 0
        comparison = weightA - weightB
      } else if (sortBy === 'incident_id') {
        comparison = a.incident_id.localeCompare(b.incident_id)
      }
      return sortOrder === 'asc' ? comparison : -comparison
    })

    return result
  }, [incidentsList, search, severity, domain, status, sortBy, sortOrder])

  // Pagination calculation
  const totalRecords = processedIncidents.length
  const totalPages = Math.max(1, Math.ceil(totalRecords / limit))
  const safePage = Math.min(page, totalPages)
  const startIndex = (safePage - 1) * limit
  const paginatedIncidents = processedIncidents.slice(startIndex, startIndex + limit)

  // Toggle sorting
  const handleSortToggle = (column: 'created_at' | 'severity' | 'incident_id') => {
    if (sortBy === column) {
      setSorting(column, sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSorting(column, 'desc')
    }
  }

  // Navigate to Investigation Workspace with current incident
  const handleLaunchInvestigation = (incidentId: string) => {
    setSelectedIncidentId(incidentId)
    navigate('/investigation')
  }

  return (
    <div className="space-y-5">
      {/* Search & Filter Controls Bar */}
      <div className="rounded-sm bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 space-y-3 transition-colors">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          {/* Text Search Box */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by ID, title, description, fault category, or node..."
              aria-label="Search incidents"
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)] rounded-xs focus:outline-none focus:ring-1 focus:ring-[var(--border-strong)] placeholder:text-[var(--text-muted)] font-mono"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                aria-label="Clear search"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Quick Refresh & Clear Filters */}
          <div className="flex items-center gap-2 shrink-0">
            {(search || domain !== 'ALL' || severity !== 'ALL' || status !== 'ALL') && (
              <button
                onClick={resetFilters}
                className="px-2.5 py-1.5 rounded-xs text-xs font-medium text-[var(--text-muted)] hover:text-[var(--text-primary)] bg-[var(--bg-subtle)] border border-[var(--border-subtle)] transition-colors font-mono"
              >
                Reset Filters
              </button>
            )}
            <button
              onClick={() => refetch()}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs text-xs font-medium bg-[var(--bg-subtle)] hover:bg-[var(--border-subtle)] border border-[var(--border-subtle)] transition-colors text-[var(--text-primary)] font-mono"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Filter Dropdowns Row */}
        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-[var(--border-subtle)] text-xs">
          <div className="flex items-center gap-1.5 text-[var(--text-muted)] font-medium">
            <Filter className="w-3.5 h-3.5 text-[var(--text-muted)]" />
            <span>Filters:</span>
          </div>

          {/* Severity Filter */}
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
            className="text-xs bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)] rounded-xs px-2.5 py-1 focus:outline-none focus:ring-1 focus:ring-[var(--border-strong)] font-mono"
            aria-label="Filter by Severity"
          >
            <option value="ALL">Severity: All</option>
            <option value="CRITICAL">Critical</option>
            <option value="MAJOR">Major</option>
            <option value="MINOR">Minor</option>
            <option value="WARNING">Warning</option>
          </select>

          {/* Domain Filter */}
          <select
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            className="text-xs bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)] rounded-xs px-2.5 py-1 focus:outline-none focus:ring-1 focus:ring-[var(--border-strong)] font-mono"
            aria-label="Filter by Network Domain"
          >
            <option value="ALL">Domain: All</option>
            <option value="RAN">RAN</option>
            <option value="5G_CORE">5G Core</option>
            <option value="TRANSPORT">Transport</option>
            <option value="SERVICE">Service</option>
          </select>

          {/* Status Filter */}
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="text-xs bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)] rounded-xs px-2.5 py-1 focus:outline-none focus:ring-1 focus:ring-[var(--border-strong)] font-mono"
            aria-label="Filter by Resolution Status"
          >
            <option value="ALL">Status: All</option>
            <option value="ACTIVE">Active / Unresolved</option>
            <option value="RESOLVED">Resolved</option>
          </select>

          {/* Results Counter & Cache Indicator */}
          <div className="ml-auto flex items-center gap-2 text-xs font-mono text-[var(--text-muted)]">
            {isStale && <span className="text-amber-500">● Cache Stale</span>}
            <span>
              Showing {paginatedIncidents.length} of {totalRecords} records
            </span>
          </div>
        </div>
      </div>

      {/* Main Content Area: Table + Optional Detail Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Incident Table: Takes 2 or 3 cols depending on selection */}
        <div className={`${selectedIncidentId ? 'lg:col-span-2' : 'lg:col-span-3'} space-y-4`}>
          <div className="rounded-sm bg-[var(--bg-surface)] border border-[var(--border-subtle)] overflow-hidden transition-colors">
            <div className="px-4 py-3 border-b border-[var(--border-subtle)] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-[var(--text-primary)]">
                  Incident Catalog
                </h3>
                <span className="text-xs font-mono tabular-nums text-[var(--text-muted)]">
                  ({totalRecords} total)
                </span>
              </div>
            </div>

            {isLoading ? (
              <div className="p-12 text-center text-xs text-[var(--text-muted)] flex flex-col items-center justify-center gap-2 font-mono">
                <RefreshCw className="w-6 h-6 animate-spin text-[var(--text-primary)]" />
                <span>Loading incident catalog from FastAPI backend (/api/v1/incidents)...</span>
              </div>
            ) : isError ? (
              <div className="p-6">
                <ErrorState
                  error={error}
                  onRetry={refetch}
                  title="Failed to Load Incidents"
                  endpointName="/api/v1/incidents"
                />
              </div>
            ) : paginatedIncidents.length === 0 ? (
              <div className="p-8">
                <EmptyState
                  title="No Incidents Found"
                  description="No incidents match the active search query or filter selection."
                  actionLabel="Reset All Filters"
                  onAction={resetFilters}
                />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-sans">
                  <thead className="bg-[var(--bg-subtle)] border-b border-[var(--border-subtle)] text-[var(--text-muted)] font-mono uppercase text-xs">
                    <tr>
                      <th
                        onClick={() => handleSortToggle('incident_id')}
                        className="px-4 py-2.5 font-semibold cursor-pointer hover:text-[var(--text-primary)] select-none whitespace-nowrap"
                      >
                        <div className="flex items-center gap-1">
                          <span>Incident ID</span>
                          <ArrowUpDown className="w-3 h-3" />
                        </div>
                      </th>
                      <th className="px-4 py-2.5 font-semibold">Title & Description</th>
                      <th className="px-4 py-2.5 font-semibold whitespace-nowrap">Domain</th>
                      <th
                        onClick={() => handleSortToggle('severity')}
                        className="px-4 py-2.5 font-semibold cursor-pointer hover:text-[var(--text-primary)] select-none whitespace-nowrap"
                      >
                        <div className="flex items-center gap-1">
                          <span>Severity</span>
                          <ArrowUpDown className="w-3 h-3" />
                        </div>
                      </th>
                      <th className="px-4 py-2.5 font-semibold whitespace-nowrap">Status</th>
                      <th className="px-4 py-2.5 font-semibold whitespace-nowrap">Source</th>
                      <th
                        onClick={() => handleSortToggle('created_at')}
                        className="px-4 py-2.5 font-semibold cursor-pointer hover:text-[var(--text-primary)] select-none whitespace-nowrap"
                      >
                        <div className="flex items-center gap-1">
                          <span>Created</span>
                          <ArrowUpDown className="w-3 h-3" />
                        </div>
                      </th>
                      <th className="px-4 py-2.5 font-semibold text-right whitespace-nowrap">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-subtle)]">
                    {paginatedIncidents.map((inc) => {
                      const isSelected = selectedIncidentId === inc.incident_id
                      const isResolved = Boolean(inc.resolved_at)

                      return (
                        <tr
                          key={inc.incident_id}
                          onClick={() => setSelectedIncidentId(inc.incident_id)}
                          className={`cursor-pointer transition-colors ${
                            isSelected
                              ? 'bg-[var(--bg-subtle)] border-l-2 border-[var(--text-primary)]'
                              : 'hover:bg-[var(--bg-subtle)]'
                          }`}
                        >
                          <td className="px-4 py-3 font-mono tabular-nums font-bold text-[var(--text-primary)] whitespace-nowrap">
                            {inc.incident_id}
                          </td>
                          <td className="px-4 py-3 max-w-xs sm:max-w-sm md:max-w-md">
                            <div className="font-semibold text-[var(--text-primary)] truncate">
                              {inc.title || inc.description}
                            </div>
                            <div className="text-xs text-[var(--text-muted)] truncate mt-0.5">
                              {inc.description}
                            </div>
                            {inc.fault_category && (
                              <div className="mt-1">
                                <span className="inline-block text-xs font-mono px-2 py-0.5 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-muted)]">
                                  Category: {inc.fault_category}
                                </span>
                              </div>
                            )}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <DomainBadge domain={inc.network_domain} />
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <SeverityBadge severity={inc.severity} />
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className="text-xs font-mono font-medium uppercase px-2 py-0.5 rounded-xs border border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[var(--text-primary)] inline-flex items-center gap-1.5">
                              <span className={`w-1.5 h-1.5 rounded-full ${isResolved ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                              {isResolved ? 'RESOLVED' : 'ACTIVE'}
                            </span>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap font-mono text-xs text-[var(--text-muted)]">
                            {inc.source_dataset || inc.source_type}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap font-mono tabular-nums text-xs text-[var(--text-muted)]">
                            {inc.created_at ? new Date(inc.created_at).toLocaleString() : 'n/a'}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-right" onClick={(e) => e.stopPropagation()}>
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                onClick={() => setSelectedIncidentId(inc.incident_id)}
                                title="Inspect Details"
                                className="p-1 rounded-xs bg-[var(--bg-subtle)] hover:bg-[var(--border-subtle)] border border-[var(--border-subtle)] text-[var(--text-primary)] transition-colors"
                              >
                                <Eye className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => handleLaunchInvestigation(inc.incident_id)}
                                title="Open in Investigation Workspace"
                                className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-xs bg-[var(--bg-subtle)] hover:bg-[var(--border-subtle)] border border-[var(--border-subtle)] text-[var(--text-primary)] transition-colors font-mono"
                              >
                                <span>Investigate</span>
                                <ExternalLink className="w-3 h-3" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination Controls Footer */}
            {totalPages > 1 && (
              <div className="px-4 py-3 border-t border-[var(--border-subtle)] bg-[var(--bg-subtle)] flex flex-wrap items-center justify-between gap-3 text-xs">
                <div className="flex items-center gap-2 text-[var(--text-muted)] font-mono">
                  <span>Rows per page:</span>
                  <select
                    value={limit}
                    onChange={(e) => setLimit(Number(e.target.value))}
                    className="bg-[var(--bg-surface)] text-[var(--text-primary)] border border-[var(--border-subtle)] rounded-xs px-2 py-0.5 font-mono text-xs focus:outline-none"
                  >
                    <option value="10">10</option>
                    <option value="20">20</option>
                    <option value="50">50</option>
                  </select>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-[var(--text-muted)] font-mono text-xs tabular-nums">
                    Page {safePage} of {totalPages}
                  </span>
                  <div className="flex items-center gap-1">
                    <button
                      disabled={safePage <= 1}
                      onClick={() => setPage(safePage - 1)}
                      className="p-1 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] disabled:opacity-40 text-[var(--text-primary)] transition-colors"
                      aria-label="Previous Page"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <button
                      disabled={safePage >= totalPages}
                      onClick={() => setPage(safePage + 1)}
                      className="p-1 rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] disabled:opacity-40 text-[var(--text-primary)] transition-colors"
                      aria-label="Next Page"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Selected Incident Detail Drawer */}
        {selectedIncidentId && (
          <div className="lg:col-span-1">
            <div className="rounded-sm bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 space-y-4 sticky top-16 transition-colors">
              <div className="flex items-start justify-between gap-2 border-b border-[var(--border-subtle)] pb-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono tabular-nums text-xs font-bold text-[var(--text-primary)]">
                      {selectedIncidentId}
                    </span>
                  </div>
                  <h4 className="text-sm font-bold text-[var(--text-primary)]">
                    {detailData?.incident?.title || 'Incident Inspection'}
                  </h4>
                </div>
                <button
                  onClick={() => setSelectedIncidentId(null)}
                  className="p-1 rounded-xs hover:bg-[var(--bg-subtle)] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                  aria-label="Close detail panel"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {detailLoading ? (
                <div className="p-6 text-center text-xs text-[var(--text-muted)] font-mono animate-pulse">
                  Querying detail from /api/v1/incidents/{selectedIncidentId}...
                </div>
              ) : detailData?.incident ? (
                <div className="space-y-3 text-xs">
                  {/* Metadata Chips */}
                  <div className="flex flex-wrap gap-1.5">
                    <SeverityBadge severity={detailData.incident.severity} />
                    <DomainBadge domain={detailData.incident.network_domain} />
                    {detailData.incident.support_level_label && (
                      <span className="font-mono text-xs px-2 py-0.5 rounded-xs bg-[var(--bg-subtle)] text-[var(--text-secondary)] border border-[var(--border-subtle)]">
                        Level: {detailData.incident.support_level_label}
                      </span>
                    )}
                  </div>

                  {/* Description Box */}
                  <div className="p-3 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] space-y-1">
                    <span className="text-xs font-mono uppercase text-[var(--text-muted)] block">
                      Description
                    </span>
                    <p className="text-[var(--text-primary)] leading-relaxed">
                      {detailData.incident.description}
                    </p>
                  </div>

                  {/* Network Elements */}
                  {detailData.incident.network_element_ids &&
                    detailData.incident.network_element_ids.length > 0 && (
                      <div className="p-2.5 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] space-y-1">
                        <span className="text-xs font-mono uppercase text-[var(--text-muted)] block">
                          Correlated Elements
                        </span>
                        <div className="flex flex-wrap gap-1">
                          {detailData.incident.network_element_ids.map((elem) => (
                            <span
                              key={elem}
                              className="font-mono text-xs px-2 py-0.5 rounded-xs bg-[var(--bg-surface)] text-[var(--text-primary)] border border-[var(--border-subtle)]"
                            >
                              {elem}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                  {/* Provenance & Lineage */}
                  <div className="p-2.5 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] space-y-1 font-mono text-xs text-[var(--text-muted)]">
                    <div>Source System: <strong className="text-[var(--text-primary)]">{detailData.lineage?.source_system || detailData.incident.source_type}</strong></div>
                    <div>Source ID: <strong className="text-[var(--text-primary)]">{detailData.lineage?.external_event_id || detailData.incident.source_record_id || 'n/a'}</strong></div>
                    <div>Created At: <span className="text-[var(--text-primary)] tabular-nums">{detailData.incident.created_at}</span></div>
                  </div>

                  {/* Action Link to Investigation */}
                  <div className="pt-2">
                    <button
                      onClick={() => handleLaunchInvestigation(selectedIncidentId)}
                      className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 rounded-xs text-xs font-semibold bg-[var(--text-primary)] hover:opacity-90 text-[var(--bg-surface)] transition-opacity font-mono"
                    >
                      <FileSearch className="w-4 h-4" />
                      <span>Launch Investigation Workspace</span>
                    </button>
                  </div>
                </div>
              ) : (
                <div className="p-4 text-center text-xs text-[var(--text-muted)] font-mono">
                  Detailed record not found on backend.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
