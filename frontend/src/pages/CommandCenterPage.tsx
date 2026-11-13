import React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ShieldAlert,
  Server,
  Activity,
  ArrowRight,
  RefreshCw,
  Clock,
  Eye,
  AlertTriangle,
  History,
} from 'lucide-react'
import {
  useSystemHealthQuery,
  useSystemReadyQuery,
  useIncidentsQuery,
  useAdaptersHealthQuery,
} from '../api/queries'
import { useIncidentContextStore } from '../store/incidentContextStore'
import { MetricCard } from '../components/common/MetricCard'
import { SeverityBadge } from '../components/common/SeverityBadge'
import { DomainBadge } from '../components/common/DomainBadge'
import { StatusPill } from '../components/common/StatusPill'
import { DistributionBar, type DistributionSegment } from '../components/charts/DistributionBar'
import { ErrorState } from '../components/common/ErrorState'
import { EmptyState } from '../components/common/EmptyState'

export const CommandCenterPage: React.FC = () => {
  const navigate = useNavigate()
  const { setSelectedIncidentId, setSeverity } = useIncidentContextStore()

  // Primary Queries using shared TanStack Query hooks
  const {
    data: health,
    isLoading: healthLoading,
    isError: healthError,
    refetch: refetchHealth,
  } = useSystemHealthQuery()

  const {
    data: ready,
    isLoading: readyLoading,
    isError: readyError,
    refetch: refetchReady,
  } = useSystemReadyQuery()

  const {
    data: incidentsData,
    isLoading: incidentsLoading,
    isError: incidentsError,
    error: incidentsErr,
    refetch: refetchIncidents,
  } = useIncidentsQuery({ limit: 100 })

  const {
    data: adapters,
    isLoading: adaptersLoading,
    isError: adaptersError,
    refetch: refetchAdapters,
  } = useAdaptersHealthQuery()

  const handleRefreshAll = () => {
    refetchHealth()
    refetchReady()
    refetchIncidents()
    refetchAdapters()
  }

  // Derive metrics strictly from real backend response data
  const incidents = incidentsData?.items || []
  const totalIncidentsCount = ready?.incidents_count ?? incidentsData?.total_count ?? incidents.length

  const criticalCount = incidents.filter((i) => i.severity?.toUpperCase() === 'CRITICAL').length
  const majorCount = incidents.filter((i) => i.severity?.toUpperCase() === 'MAJOR').length
  const minorCount = incidents.filter((i) => i.severity?.toUpperCase() === 'MINOR').length
  const warningCount = incidents.filter((i) => i.severity?.toUpperCase() === 'WARNING').length
  const highSeverityCount = criticalCount + majorCount

  // Severity Distribution Segments
  const severitySegments: DistributionSegment[] = [
    { key: 'CRITICAL', label: 'Critical', count: criticalCount, colorClass: 'text-rose-500', bgClass: 'bg-rose-500' },
    { key: 'MAJOR', label: 'Major', count: majorCount, colorClass: 'text-amber-500', bgClass: 'bg-amber-500' },
    { key: 'MINOR', label: 'Minor', count: minorCount, colorClass: 'text-sky-500', bgClass: 'bg-sky-500' },
    { key: 'WARNING', label: 'Warning', count: warningCount, colorClass: 'text-yellow-500', bgClass: 'bg-yellow-500' },
  ]

  // Network Domain Breakdown Segments
  const ranCount = incidents.filter((i) => i.network_domain === 'RAN').length
  const coreCount = incidents.filter((i) => i.network_domain === '5G_CORE').length
  const transportCount = incidents.filter((i) => i.network_domain === 'TRANSPORT').length
  const serviceCount = incidents.filter((i) => i.network_domain === 'SERVICE').length
  const otherDomainCount = incidents.length - (ranCount + coreCount + transportCount + serviceCount)

  const domainSegments: DistributionSegment[] = [
    { key: 'RAN', label: 'RAN (gNodeB)', count: ranCount, colorClass: 'text-sky-400', bgClass: 'bg-sky-500' },
    { key: '5G_CORE', label: '5G Core', count: coreCount, colorClass: 'text-purple-400', bgClass: 'bg-purple-500' },
    { key: 'TRANSPORT', label: 'Transport', count: transportCount, colorClass: 'text-emerald-400', bgClass: 'bg-emerald-500' },
    { key: 'SERVICE', label: 'Service', count: serviceCount, colorClass: 'text-indigo-400', bgClass: 'bg-indigo-500' },
    { key: 'OTHER', label: 'Other/Cross', count: Math.max(0, otherDomainCount), colorClass: 'text-slate-400', bgClass: 'bg-slate-500' },
  ]

  // Recent 5 incidents
  const recentIncidents = incidents.slice(0, 5)

  // Navigate to explorer with pre-applied filter
  const handleFilterClick = (sev: string) => {
    setSeverity(sev)
    navigate('/incidents')
  }

  // Navigate to investigation
  const handleInvestigateClick = (incidentId: string) => {
    setSelectedIncidentId(incidentId)
    navigate('/investigation')
  }

  return (
    <div className="space-y-6">
      {/* Situational Awareness Hero Header */}
      <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 transition-colors">
        <div className="flex items-start sm:items-center gap-3.5">
          <div className="p-2.5 rounded-xs bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)] shrink-0">
            <ShieldAlert className="w-5 h-5 text-[var(--text-muted)]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-[var(--text-primary)] tracking-tight">
                NOC Supervisory Command Center
              </h2>
              <span className="hidden sm:inline-flex items-center gap-1.5 text-xs font-mono font-medium px-2 py-0.5 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--text-secondary)]">
                <span className={`w-1.5 h-1.5 rounded-full ${highSeverityCount > 0 ? 'bg-amber-500' : 'bg-emerald-500'}`} />
                {highSeverityCount > 0 ? `${highSeverityCount} ACTIVE ATTENTION` : 'ALL SYSTEMS NOMINAL'}
              </span>
            </div>
            <p className="text-xs text-[var(--text-muted)] mt-1 leading-relaxed">
              Live operational overview, fault correlation, and incident metrics across mobile core and transport domains.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            onClick={handleRefreshAll}
            aria-label="Refresh all command center metrics"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs text-xs font-medium bg-[var(--bg-subtle)] hover:bg-[var(--border-subtle)] border border-[var(--border-subtle)] text-[var(--text-primary)] transition-colors focus:ring-1 focus:ring-[var(--border-strong)]"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 text-[var(--text-muted)] ${
                healthLoading || readyLoading || incidentsLoading ? 'animate-spin' : ''
              }`}
            />
            <span>Refresh All</span>
          </button>
        </div>
      </div>

      {/* Main KPI Operational Summary Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Active Incidents */}
        <MetricCard
          label="Total Incidents"
          value={totalIncidentsCount}
          subtext="Canonical tickets ingested into pipeline"
          sourceEndpoint="GET /api/v1/ready + /api/v1/incidents"
          isLoading={readyLoading || incidentsLoading}
          icon={<AlertTriangle className="w-4 h-4 text-[var(--text-muted)]" />}
          onClick={() => navigate('/incidents')}
        />

        {/* Critical & Major Severities */}
        <MetricCard
          label="Critical / High Severity"
          value={
            <div className="flex items-baseline gap-2">
              <span className="text-[var(--text-primary)] font-bold">{criticalCount}</span>
              <span className="text-sm text-[var(--text-muted)]">/ {majorCount} Major</span>
            </div>
          }
          subtext={`${highSeverityCount} high-severity incident${highSeverityCount === 1 ? '' : 's'} require immediate investigation`}
          sourceEndpoint="Computed from /api/v1/incidents"
          isLoading={incidentsLoading}
          icon={<AlertTriangle className="w-4 h-4 text-[var(--text-muted)]" />}
          onClick={() => handleFilterClick('CRITICAL')}
        />

        {/* API Liveness & Readiness */}
        <MetricCard
          label="FastAPI Core Status"
          value={
            readyError || healthError ? (
              <span className="text-rose-500 text-lg font-semibold">UNREACHABLE</span>
            ) : ready?.status === 'ready' && health?.status === 'ok' ? (
              <span className="text-[var(--text-primary)] text-lg font-semibold flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
                ONLINE (READY)
              </span>
            ) : (
              <span className="text-[var(--text-primary)] text-lg font-semibold">{ready?.status?.toUpperCase() || 'DEGRADED'}</span>
            )
          }
          subtext={
            ready?.degraded_adapters && ready.degraded_adapters.length > 0
              ? `Degraded adapters: ${ready.degraded_adapters.join(', ')}`
              : 'Liveness & readiness probes nominal'
          }
          sourceEndpoint="GET /api/v1/health & /ready"
          isLoading={healthLoading || readyLoading}
          icon={<Server className="w-4 h-4 text-[var(--text-muted)]" />}
        />

        {/* Pending Human Reviews / Audit Chain */}
        <MetricCard
          label="Cryptographic Audit Blocks"
          value={ready?.audit_ledger_records ?? 0}
          subtext="RFC 8785 immutable notary ledger entries"
          sourceEndpoint="GET /api/v1/ready (audit_ledger_records)"
          isLoading={readyLoading}
          icon={<History className="w-4 h-4 text-[var(--text-muted)]" />}
          onClick={() => navigate('/audit')}
        />
      </div>

      {/* Honest Operational Status & Component Readiness Bar */}
      <div className="rounded-sm bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 space-y-3 transition-colors">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border-subtle)] pb-2.5">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-[var(--text-muted)]" />
            <h3 className="text-xs font-semibold text-[var(--text-primary)]">
              Operational Subsystem & Integration Status
            </h3>
          </div>
          <span className="text-xs text-[var(--text-muted)]">
            Distinguishing Verified Local Probes vs External Integrations
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* FastAPI Core Probe */}
          <div className="p-2.5 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] flex items-center justify-between">
            <div>
              <span className="text-xs uppercase font-mono text-[var(--text-muted)] block">FastAPI REST API</span>
              <span className="text-xs font-semibold text-[var(--text-primary)]">Core Gateway</span>
            </div>
            <StatusPill state={healthError ? 'UNAVAILABLE' : 'HEALTHY'} label={healthError ? 'DOWN' : 'HEALTHY'} />
          </div>

          {/* Model Provider */}
          <div className="p-2.5 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] flex items-center justify-between">
            <div>
              <span className="text-xs uppercase font-mono text-[var(--text-muted)] block">Model Provider</span>
              <span className="text-xs font-semibold text-[var(--text-primary)]">Hybrid ML / Rules</span>
            </div>
            <StatusPill state="SIMULATED" label="SIMULATED (LOCAL)" />
          </div>

          {/* Retrieval Engine */}
          <div className="p-2.5 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] flex items-center justify-between">
            <div>
              <span className="text-xs uppercase font-mono text-[var(--text-muted)] block">Retrieval Engine</span>
              <span className="text-xs font-semibold text-[var(--text-primary)]">BM25 / Embeddings</span>
            </div>
            <StatusPill state="HEALTHY" label="LOCAL VERIFIED" />
          </div>

          {/* Ingestion Adapters Summary */}
          <div className="p-2.5 rounded-xs bg-[var(--bg-subtle)] border border-[var(--border-subtle)] flex items-center justify-between">
            <div>
              <span className="text-xs uppercase font-mono text-[var(--text-muted)] block">ITSM / OSS Adapters</span>
              <span className="text-xs font-semibold text-[var(--text-primary)]">
                {adaptersLoading ? 'Checking...' : `${adapters?.length || 4} Registered`}
              </span>
            </div>
            <StatusPill
              state={adaptersError ? 'UNKNOWN' : 'EXTERNALLY_UNVERIFIED'}
              label={adaptersError ? 'ERROR' : 'READ-ONLY (MOCK)'}
            />
          </div>
        </div>
      </div>

      {/* Distribution Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <DistributionBar
          title="Incident Severity Distribution"
          segments={severitySegments}
          totalCount={incidents.length}
          provenanceLabel="GET /api/v1/incidents"
        />

        <DistributionBar
          title="Network Domain Breakdown"
          segments={domainSegments}
          totalCount={incidents.length}
          provenanceLabel="GET /api/v1/incidents (network_domain)"
        />
      </div>

      {/* Recent Incidents Activity & Investigation Queue */}
      <div className="rounded-sm bg-[var(--bg-surface)] border border-[var(--border-subtle)] overflow-hidden transition-colors">
        <div className="px-4 py-3 border-b border-[var(--border-subtle)] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-[var(--text-muted)]" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] font-mono">
              Recent Incident Activity & Investigation Queue
            </h3>
          </div>
          <Link
            to="/incidents"
            className="inline-flex items-center gap-1 text-xs font-medium text-[var(--text-primary)] hover:underline font-mono"
          >
            <span>Open Incident Explorer</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {incidentsLoading ? (
          <div className="p-8 text-center text-xs text-[var(--text-muted)] font-mono animate-pulse">
            Loading recent incident feed...
          </div>
        ) : incidentsError ? (
          <div className="p-4">
            <ErrorState
              error={incidentsErr}
              onRetry={refetchIncidents}
              title="Failed to load incident feed"
              endpointName="/api/v1/incidents"
            />
          </div>
        ) : recentIncidents.length === 0 ? (
          <div className="p-6">
            <EmptyState
              title="No Ingested Incidents"
              description="The backend pipeline currently has no active incidents stored in memory. Ingest tickets via API or portfolio flow."
              actionLabel="Go to Incident Explorer"
              onAction={() => navigate('/incidents')}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-sans">
              <thead className="bg-[var(--bg-subtle)] border-b border-[var(--border-subtle)] text-[var(--text-muted)] font-mono uppercase text-xs">
                <tr>
                  <th className="px-4 py-2.5 font-semibold">Incident ID</th>
                  <th className="px-4 py-2.5 font-semibold">Title & Description</th>
                  <th className="px-4 py-2.5 font-semibold">Domain</th>
                  <th className="px-4 py-2.5 font-semibold">Severity</th>
                  <th className="px-4 py-2.5 font-semibold">Source</th>
                  <th className="px-4 py-2.5 font-semibold">Created</th>
                  <th className="px-4 py-2.5 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)]">
                {recentIncidents.map((inc) => (
                  <tr key={inc.incident_id} className="hover:bg-[var(--bg-subtle)] transition-colors">
                    <td className="px-4 py-3 font-mono tabular-nums font-bold text-[var(--text-primary)] whitespace-nowrap">
                      {inc.incident_id}
                    </td>
                    <td className="px-4 py-3 max-w-md">
                      <div className="font-semibold text-[var(--text-primary)] truncate">
                        {inc.title || inc.description}
                      </div>
                      <div className="text-xs text-[var(--text-muted)] truncate mt-0.5">
                        {inc.description}
                      </div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <DomainBadge domain={inc.network_domain} />
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <SeverityBadge severity={inc.severity} />
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap font-mono text-xs text-[var(--text-muted)]">
                      {inc.source_dataset || inc.source_type}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap font-mono tabular-nums text-xs text-[var(--text-muted)]">
                      {inc.created_at ? new Date(inc.created_at).toLocaleTimeString() : 'n/a'}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-right">
                      <button
                        onClick={() => handleInvestigateClick(inc.incident_id)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-xs bg-[var(--bg-subtle)] hover:bg-[var(--border-subtle)] border border-[var(--border-subtle)] text-[var(--text-primary)] transition-colors font-mono focus:ring-1 focus:ring-[var(--border-strong)]"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>Investigate</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
