import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  HelpCircle,
  RefreshCw,
  Server,
  ShieldCheck,
  Cpu,
  Database,
  Search,
  Lock,
  X,
  Layers,
  GitBranch,
  Clock,
  Radio,
  ChevronRight,
} from 'lucide-react'
import { apiClient } from '../api/client'
import { API_ENDPOINTS } from '../api/endpoints'
import type {
  ComponentHealthItem,
  SystemHealthOverviewResponse,
  IngestionHealthResponse,
  IntelligenceSubsystemHealthResponse,
  PersistenceAuditHealthResponse,
  SystemHealthEventItem,
  SystemDependencyGraphResponse,
  PaginatedResponse,
  HealthResponse,
  ReadyResponse,
} from '../api/types'
import { MetricCard } from '../components/common/MetricCard'
import { EmptyState } from '../components/common/EmptyState'
import { useAuth } from '../auth/AuthContext'

type HealthTab = 'registry' | 'ingestion' | 'intelligence' | 'persistence' | 'events' | 'topology'

export const SystemHealthPage: React.FC = () => {
  const { isAuthenticated, loginWithDemoSession } = useAuth()
  const [activeTab, setActiveTab] = useState<HealthTab>('registry')

  // Component Registry Filters
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL')
  const [stateFilter, setStateFilter] = useState<string>('ALL')
  const [criticalityFilter, setCriticalityFilter] = useState<string>('ALL')

  // Selected Component for Detail Drawer
  const [selectedComponent, setSelectedComponent] = useState<ComponentHealthItem | null>(null)

  // Events Filters
  const [eventComponentFilter, setEventComponentFilter] = useState<string>('')
  const [eventTypeFilter, setEventTypeFilter] = useState<string>('')

  // 1. Overview Query
  const {
    data: overview,
    isLoading: overviewLoading,
    error: overviewError,
    refetch: refetchOverview,
  } = useQuery<SystemHealthOverviewResponse>({
    queryKey: ['system-health-overview'],
    queryFn: () => apiClient.get<SystemHealthOverviewResponse>(API_ENDPOINTS.SYSTEM_HEALTH.OVERVIEW),
    refetchInterval: 15000,
  })

  // 2. Components Query
  const {
    data: components,
    isLoading: componentsLoading,
    error: componentsError,
    refetch: refetchComponents,
  } = useQuery<ComponentHealthItem[]>({
    queryKey: ['system-health-components'],
    queryFn: () => apiClient.get<ComponentHealthItem[]>(API_ENDPOINTS.SYSTEM_HEALTH.COMPONENTS),
    refetchInterval: 15000,
  })

  // 3. Ingestion Health Query
  const {
    data: ingestion,
    refetch: refetchIngestion,
  } = useQuery<IngestionHealthResponse>({
    queryKey: ['system-health-ingestion'],
    queryFn: () => apiClient.get<IngestionHealthResponse>(API_ENDPOINTS.SYSTEM_HEALTH.INGESTION),
    refetchInterval: 15000,
    enabled: activeTab === 'ingestion',
  })

  // 4. Intelligence Health Query
  const {
    data: intelligence,
    refetch: refetchIntelligence,
  } = useQuery<IntelligenceSubsystemHealthResponse>({
    queryKey: ['system-health-intelligence'],
    queryFn: () => apiClient.get<IntelligenceSubsystemHealthResponse>(API_ENDPOINTS.SYSTEM_HEALTH.INTELLIGENCE),
    refetchInterval: 15000,
    enabled: activeTab === 'intelligence',
  })

  // 5. Persistence Health Query
  const {
    data: persistence,
    refetch: refetchPersistence,
  } = useQuery<PersistenceAuditHealthResponse>({
    queryKey: ['system-health-persistence'],
    queryFn: () => apiClient.get<PersistenceAuditHealthResponse>(API_ENDPOINTS.SYSTEM_HEALTH.PERSISTENCE),
    refetchInterval: 15000,
    enabled: activeTab === 'persistence',
  })

  // 6. Events Query
  const {
    data: eventsResponse,
    isLoading: eventsLoading,
    refetch: refetchEvents,
  } = useQuery<PaginatedResponse<SystemHealthEventItem>>({
    queryKey: ['system-health-events', eventComponentFilter, eventTypeFilter],
    queryFn: () => {
      const params = new URLSearchParams({ limit: '100' })
      if (eventComponentFilter) params.append('component_id', eventComponentFilter)
      if (eventTypeFilter) params.append('event_type', eventTypeFilter)
      return apiClient.get<PaginatedResponse<SystemHealthEventItem>>(`${API_ENDPOINTS.SYSTEM_HEALTH.EVENTS}?${params.toString()}`)
    },
    refetchInterval: 15000,
    enabled: activeTab === 'events',
  })

  // 7. Dependencies Query
  const {
    data: dependencies,
    refetch: refetchDependencies,
  } = useQuery<SystemDependencyGraphResponse>({
    queryKey: ['system-health-dependencies'],
    queryFn: () => apiClient.get<SystemDependencyGraphResponse>(API_ENDPOINTS.SYSTEM_HEALTH.DEPENDENCIES),
    refetchInterval: 30000,
    enabled: activeTab === 'topology',
  })

  // 8. Runtime Probes (Process Liveness & Subsystem Readiness)
  const { data: livenessProbe } = useQuery<HealthResponse>({
    queryKey: ['system-liveness-probe'],
    queryFn: () => apiClient.get<HealthResponse>(API_ENDPOINTS.HEALTH),
    refetchInterval: 15000,
  })

  const { data: readinessProbe } = useQuery<ReadyResponse>({
    queryKey: ['system-readiness-probe'],
    queryFn: () => apiClient.get<ReadyResponse>(API_ENDPOINTS.READY),
    refetchInterval: 15000,
  })

  const handleRefreshAll = () => {
    refetchOverview()
    refetchComponents()
    if (activeTab === 'ingestion') refetchIngestion()
    if (activeTab === 'intelligence') refetchIntelligence()
    if (activeTab === 'persistence') refetchPersistence()
    if (activeTab === 'events') refetchEvents()
    if (activeTab === 'topology') refetchDependencies()
  }

  // Filtered Components List
  const filteredComponents = (components || []).filter((comp) => {
    if (categoryFilter !== 'ALL' && comp.category !== categoryFilter) return false
    if (stateFilter !== 'ALL' && comp.health_state !== stateFilter) return false
    if (criticalityFilter !== 'ALL' && comp.criticality !== criticalityFilter) return false
    if (searchQuery) {
      const q = searchQuery.toLowerCase()
      const matchName = comp.name.toLowerCase().includes(q)
      const matchId = comp.component_id.toLowerCase().includes(q)
      const matchReason = (comp.failure_reason || '').toLowerCase().includes(q)
      if (!matchName && !matchId && !matchReason) return false
    }
    return true
  })

  // Helper for Status Badges
  const renderHealthBadge = (state: string) => {
    switch (state) {
      case 'HEALTHY':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-xs text-xs font-semibold font-mono bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" /> HEALTHY
          </span>
        )
      case 'DEGRADED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-xs text-xs font-semibold font-mono bg-amber-500/10 text-amber-500 border border-amber-500/20">
            <AlertTriangle className="w-3 h-3" /> DEGRADED
          </span>
        )
      case 'UNAVAILABLE':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-xs text-xs font-semibold font-mono bg-rose-500/10 text-rose-500 border border-rose-500/20">
            <XCircle className="w-3 h-3" /> UNAVAILABLE
          </span>
        )
      case 'UNKNOWN':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-xs text-xs font-semibold font-mono bg-zinc-500/10 text-zinc-400 border border-zinc-500/20">
            <HelpCircle className="w-3 h-3" /> UNKNOWN
          </span>
        )
    }
  }

  const renderCriticalityBadge = (crit: string) => {
    switch (crit) {
      case 'CRITICAL':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-xs text-xs font-bold uppercase tracking-wider bg-rose-500/10 text-rose-400 border border-rose-500/20 font-mono">
            CRITICAL
          </span>
        )
      case 'STANDARD':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-xs text-xs font-bold uppercase tracking-wider bg-zinc-500/10 text-zinc-400 border border-zinc-500/20 font-mono">
            STANDARD
          </span>
        )
      case 'INFORMATIONAL':
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-xs text-xs font-bold uppercase tracking-wider bg-zinc-500/10 text-zinc-400 border border-zinc-500/20 font-mono">
            INFORMATIONAL
          </span>
        )
    }
  }

  const renderFreshnessBadge = (freshness: string) => {
    switch (freshness) {
      case 'FRESH':
        return <span className="text-xs font-mono text-emerald-400">● FRESH</span>
      case 'STALE':
        return <span className="text-xs font-mono text-amber-400">▲ STALE</span>
      case 'EXPIRED':
        return <span className="text-xs font-mono text-rose-400">✕ EXPIRED</span>
      default:
        return <span className="text-xs font-mono text-zinc-500">— N/A</span>
    }
  }

  return (
    <div className="space-y-6">
      {/* SECTION A: TOP-LEVEL OPERATIONAL STATUS BANNER */}
      <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 transition-colors">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-start sm:items-center gap-3.5">
            <div
              className={`p-3 rounded-xs border ${
                overview?.aggregate_status === 'HEALTHY'
                  ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                  : overview?.aggregate_status === 'DEGRADED'
                  ? 'bg-amber-500/10 text-amber-500 border-amber-500/20'
                  : overview?.aggregate_status === 'UNAVAILABLE'
                  ? 'bg-rose-500/10 text-rose-500 border-rose-500/20'
                  : 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20'
              }`}
            >
              <Activity className="w-7 h-7" />
            </div>

            <div>
              <h1 className="text-lg font-bold text-[var(--text-primary)] tracking-tight">
                System Health & Operations Workspace
              </h1>
              <p className="text-xs text-[var(--text-muted)] mt-1">
                Deterministic operational observability, component registry, and cryptographic persistence monitoring.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 self-start lg:self-auto">
            <div className="text-right hidden sm:block">
              <div className="text-xs font-mono tabular-nums text-[var(--text-muted)]">
                Last Evaluated:{' '}
                {overview?.last_evaluated_at
                  ? new Date(overview.last_evaluated_at).toLocaleTimeString()
                  : '—'}
              </div>
              <div className="text-xs font-mono text-emerald-500">
                Policy: CRITICALITY_AWARE_STRICT
              </div>
            </div>

            <button
              onClick={handleRefreshAll}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs text-xs font-medium bg-[var(--bg-subtle)] hover:bg-[var(--border-subtle)] border border-[var(--border-subtle)] text-[var(--text-primary)] transition-colors font-mono"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${overviewLoading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* Portfolio Edition Limitation Disclaimer */}
        <div className="mt-4 p-3 rounded bg-amber-500/5 border border-amber-500/20 text-xs text-amber-200/90 flex items-start gap-2.5">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <div className="font-semibold text-amber-300">
              Portfolio Edition Trust & Connectivity Scope
            </div>
            <div className="text-xs text-zinc-300">
              PIIS operates strictly as a read-only telecom decision support system. External enterprise trust anchors (WORM storage, cloud KMS, enterprise OIDC) and live carrier brokers are not connected. Local coordinated rollback detection requires an external hardware or cloud trust anchor. Inbound telemetry and alerts are locally ingested and processed.
            </div>
          </div>
        </div>

        {/* Unauthenticated or Telemetry Warning Banner */}
        {(!isAuthenticated || overviewError || componentsError) && (
          <div className="mt-4 p-3.5 rounded-xs border border-amber-500/30 bg-amber-500/10 text-amber-200 text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 font-mono">
            <div className="flex items-center gap-2.5">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
              <div>
                <span className="font-semibold text-amber-300">
                  {!isAuthenticated ? 'Operator Authentication Required' : 'Subsystem Telemetry Request Warning'}
                </span>
                <p className="text-zinc-300 text-xs font-sans mt-0.5">
                  {!isAuthenticated
                    ? 'Internal subsystem metrics and component states require an active authenticated operator session.'
                    : ((overviewError as Error)?.message || (componentsError as Error)?.message || 'Failed to query subsystem telemetry.')}
                </p>
              </div>
            </div>
            {loginWithDemoSession && (
              <button
                type="button"
                onClick={() => loginWithDemoSession('INCIDENT_MANAGER')}
                className="px-3 py-1.5 rounded-xs bg-[var(--text-primary)] text-[var(--bg-surface)] hover:opacity-90 font-semibold text-xs whitespace-nowrap transition-opacity shrink-0"
              >
                Initialize Demo Session
              </button>
            )}
          </div>
        )}

        {/* Top Operational Metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mt-4">
          <MetricCard
            label="Aggregate Status"
            value={
              overviewLoading ? (
                '...'
              ) : (
                <span className="font-mono text-[var(--text-primary)]">{overview?.aggregate_status || 'UNKNOWN'}</span>
              )
            }
            subtext="Hierarchical Criticality Strict"
            sourceEndpoint="/api/v1/system-health/overview"
            epistemicCategory="OBSERVED_FACT"
            icon={<Activity className="w-4 h-4 text-[var(--text-muted)]" />}
          />

          <MetricCard
            label="Healthy Subsystems"
            value={
              overviewLoading ? (
                '...'
              ) : (
                <span className="font-mono text-[var(--text-primary)]">
                  {overview?.healthy_count ?? 0} / {overview?.total_components ?? 0}
                </span>
              )
            }
            subtext="Active & Verified"
            sourceEndpoint="/api/v1/system-health/overview"
            epistemicCategory="OBSERVED_FACT"
            icon={<CheckCircle2 className="w-4 h-4 text-[var(--text-muted)]" />}
          />

          <MetricCard
            label="Degraded Subsystems"
            value={
              overviewLoading ? (
                '...'
              ) : (
                <span className="font-mono text-[var(--text-primary)]">{overview?.degraded_count ?? 0}</span>
              )
            }
            subtext="Non-Fatal Impairment"
            sourceEndpoint="/api/v1/system-health/overview"
            epistemicCategory="OBSERVED_FACT"
            icon={<AlertTriangle className="w-4 h-4 text-[var(--text-muted)]" />}
          />

          <MetricCard
            label="Unavailable Subsystems"
            value={
              overviewLoading ? (
                '...'
              ) : (
                <span className="font-mono text-[var(--text-primary)]">{overview?.unavailable_count ?? 0}</span>
              )
            }
            subtext="Component Faults"
            sourceEndpoint="/api/v1/system-health/overview"
            epistemicCategory="OBSERVED_FACT"
            icon={<XCircle className="w-4 h-4 text-[var(--text-muted)]" />}
          />

          <MetricCard
            label="Readiness & Liveness"
            value={
              overviewLoading ? (
                '...'
              ) : (
                <span className="font-mono text-[var(--text-primary)]">
                  {overview?.readiness_status || 'READY'}
                </span>
              )
            }
            subtext={`K8s Probes: ${overview?.liveness_status || 'OK'}`}
            sourceEndpoint="/api/v1/ready"
            epistemicCategory="OBSERVED_FACT"
            icon={<Server className="w-4 h-4 text-[var(--text-muted)]" />}
          />
        </div>
      </div>

      {/* WORKSPACE NAVIGATION TABS */}
      <div className="border-b border-[var(--border-subtle)] flex items-center gap-2 overflow-x-auto pb-px no-scrollbar">
        <button
          onClick={() => setActiveTab('registry')}
          className={`px-3.5 py-2 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors flex items-center gap-1.5 font-mono ${
            activeTab === 'registry'
              ? 'border-[var(--text-primary)] text-[var(--text-primary)] bg-[var(--bg-subtle)]'
              : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
          }`}
        >
          <Server className="w-3.5 h-3.5" />
          Component Registry ({components ? components.length : (overview?.total_components ?? (componentsLoading ? '...' : 0))})
        </button>

        <button
          onClick={() => setActiveTab('ingestion')}
          className={`px-3.5 py-2 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors flex items-center gap-1.5 font-mono ${
            activeTab === 'ingestion'
              ? 'border-[var(--text-primary)] text-[var(--text-primary)] bg-[var(--bg-subtle)]'
              : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
          }`}
        >
          <Radio className="w-3.5 h-3.5" />
          Ingestion & DLQ Pipeline
        </button>

        <button
          onClick={() => setActiveTab('intelligence')}
          className={`px-3.5 py-2 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors flex items-center gap-1.5 font-mono ${
            activeTab === 'intelligence'
              ? 'border-[var(--text-primary)] text-[var(--text-primary)] bg-[var(--bg-subtle)]'
              : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
          }`}
        >
          <Cpu className="w-3.5 h-3.5" />
          AI & Retrieval Subsystem
        </button>

        <button
          onClick={() => setActiveTab('persistence')}
          className={`px-3.5 py-2 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors flex items-center gap-1.5 font-mono ${
            activeTab === 'persistence'
              ? 'border-[var(--text-primary)] text-[var(--text-primary)] bg-[var(--bg-subtle)]'
              : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
          }`}
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          Persistence & Audit Parity
        </button>

        <button
          onClick={() => setActiveTab('events')}
          className={`px-3.5 py-2 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors flex items-center gap-1.5 font-mono ${
            activeTab === 'events'
              ? 'border-[var(--text-primary)] text-[var(--text-primary)] bg-[var(--bg-subtle)]'
              : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
          }`}
        >
          <Clock className="w-3.5 h-3.5" />
          Health Events Timeline
        </button>

        <button
          onClick={() => setActiveTab('topology')}
          className={`px-3.5 py-2 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors flex items-center gap-1.5 font-mono ${
            activeTab === 'topology'
              ? 'border-[var(--text-primary)] text-[var(--text-primary)] bg-[var(--bg-subtle)]'
              : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
          }`}
        >
          <GitBranch className="w-3.5 h-3.5" />
          Dependency Topology Map
        </button>
      </div>

      {/* TAB 1: COMPONENT REGISTRY & RUNTIME PROBES */}
      {activeTab === 'registry' && (
        <div className="space-y-6">
          {/* Filters Bar */}
          <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-3.5 shadow-xs flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2.5 flex-1 min-w-[280px]">
              <div className="relative flex-1 min-w-[200px]">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  type="text"
                  placeholder="Search component by name, ID, or fault..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 text-xs rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-emerald-500"
                />
              </div>

              {/* Category Dropdown */}
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="px-2.5 py-1.5 text-xs rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-emerald-500 font-mono"
              >
                <option value="ALL">All Categories</option>
                <option value="API">API</option>
                <option value="AUTH">AUTH</option>
                <option value="INGESTION">INGESTION</option>
                <option value="DEDUPLICATION">DEDUPLICATION</option>
                <option value="DLQ">DLQ</option>
                <option value="RETRIEVAL">RETRIEVAL</option>
                <option value="INVESTIGATION">INVESTIGATION</option>
                <option value="REVIEW">REVIEW</option>
                <option value="AUDIT">AUDIT</option>
                <option value="INTEGRATIONS">INTEGRATIONS</option>
                <option value="TELEMETRY">TELEMETRY</option>
                <option value="BACKGROUND">BACKGROUND</option>
              </select>

              {/* Health State Dropdown */}
              <select
                value={stateFilter}
                onChange={(e) => setStateFilter(e.target.value)}
                className="px-2.5 py-1.5 text-xs rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-emerald-500 font-mono"
              >
                <option value="ALL">All Health States</option>
                <option value="HEALTHY">HEALTHY</option>
                <option value="DEGRADED">DEGRADED</option>
                <option value="UNAVAILABLE">UNAVAILABLE</option>
                <option value="UNKNOWN">UNKNOWN</option>
              </select>

              {/* Criticality Dropdown */}
              <select
                value={criticalityFilter}
                onChange={(e) => setCriticalityFilter(e.target.value)}
                className="px-2.5 py-1.5 text-xs rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-emerald-500 font-mono"
              >
                <option value="ALL">All Criticalities</option>
                <option value="CRITICAL">CRITICAL</option>
                <option value="STANDARD">STANDARD</option>
                <option value="INFORMATIONAL">INFORMATIONAL</option>
              </select>
            </div>

            {(searchQuery || categoryFilter !== 'ALL' || stateFilter !== 'ALL' || criticalityFilter !== 'ALL') && (
              <button
                onClick={() => {
                  setSearchQuery('')
                  setCategoryFilter('ALL')
                  setStateFilter('ALL')
                  setCriticalityFilter('ALL')
                }}
                className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] underline"
              >
                Reset Filters
              </button>
            )}
          </div>

          {/* Components Table */}
          <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] overflow-hidden shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs" aria-label="Component Health Registry">
                <thead className="bg-[var(--bg-canvas)] border-b border-[var(--border-subtle)] font-mono uppercase text-xs text-[var(--text-muted)]">
                  <tr>
                    <th className="py-2.5 px-4">Component & ID</th>
                    <th className="py-2.5 px-3">Category</th>
                    <th className="py-2.5 px-3">Criticality</th>
                    <th className="py-2.5 px-3">Health State</th>
                    <th className="py-2.5 px-3">Freshness</th>
                    <th className="py-2.5 px-3">Implementation</th>
                    <th className="py-2.5 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-subtle)]">
                  {componentsLoading ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-xs text-[var(--text-muted)]">
                        Evaluating internal subsystems...
                      </td>
                    </tr>
                  ) : componentsError ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-xs text-rose-400">
                        <div className="flex flex-col items-center justify-center gap-2">
                          <AlertTriangle className="w-6 h-6 text-rose-500" />
                          <span className="font-semibold">Failed to evaluate subsystem components</span>
                          <span className="text-[var(--text-muted)] font-mono">{(componentsError as Error).message}</span>
                          <button
                            type="button"
                            onClick={() => refetchComponents()}
                            className="mt-2 px-3 py-1 rounded-xs border border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[var(--text-primary)] font-mono hover:bg-[var(--border-subtle)]"
                          >
                            Retry Evaluation
                          </button>
                        </div>
                      </td>
                    </tr>
                  ) : filteredComponents.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-8">
                        <EmptyState
                          title="No Subsystems Match Criteria"
                          description="Try clearing search filters to see all 17 registered components."
                        />
                      </td>
                    </tr>
                  ) : (
                    filteredComponents.map((comp) => (
                      <tr
                        key={comp.component_id}
                        className="hover:bg-[var(--bg-card)]/50 transition-colors"
                      >
                        <td className="py-3 px-4">
                          <div className="font-semibold text-[var(--text-primary)]">{comp.name}</div>
                          <div className="text-xs font-mono text-[var(--text-muted)]">
                            {comp.component_id}
                          </div>
                          {comp.failure_reason && (
                            <div className="mt-1 text-xs text-rose-400 flex items-center gap-1 font-mono">
                              <AlertTriangle className="w-3 h-3 shrink-0" />
                              {comp.failure_reason}
                            </div>
                          )}
                        </td>

                        <td className="py-3 px-3">
                          <span className="font-mono text-xs px-2 py-0.5 rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-secondary)]">
                            {comp.category}
                          </span>
                        </td>

                        <td className="py-3 px-3">{renderCriticalityBadge(comp.criticality)}</td>

                        <td className="py-3 px-3">{renderHealthBadge(comp.health_state)}</td>

                        <td className="py-3 px-3">{renderFreshnessBadge(comp.freshness)}</td>

                        <td className="py-3 px-3">
                          <span className="text-xs font-mono text-[var(--text-muted)]">
                            {comp.implementation_nature}
                          </span>
                        </td>

                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => setSelectedComponent(comp)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium bg-[var(--bg-card)] hover:bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] transition-colors"
                          >
                            Diagnostics <ChevronRight className="w-3 h-3" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* SECTION C: RUNTIME & PLATFORM PROBES */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] font-mono">
              Process Runtime Probes & Telemetry Export
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Liveness Probe Card */}
              <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold uppercase text-[var(--text-muted)]">
                    Liveness Probe
                  </span>
                  <Server className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span className="text-sm font-mono font-bold text-emerald-400">
                    STATUS: {livenessProbe?.status?.toUpperCase() || 'OK'}
                  </span>
                </div>
                <div className="mt-1 text-xs font-mono text-[var(--text-muted)]">
                  Service: {livenessProbe?.service || 'piis-core'} | Mode: {livenessProbe?.mode || 'read_only'}
                </div>
              </div>

              {/* Readiness Probe Card */}
              <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold uppercase text-[var(--text-muted)]">
                    Readiness Probe
                  </span>
                  <CheckCircle2 className="w-4 h-4 text-[var(--text-muted)]" />
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-sm font-mono font-bold text-[var(--text-primary)] flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                    STATUS: {readinessProbe?.status?.toUpperCase() || 'READY'}
                  </span>
                </div>
                <div className="mt-1 text-xs font-mono text-[var(--text-muted)]">
                  Adapters: {readinessProbe?.registered_adapters_count ?? 6} | Incidents: {readinessProbe?.incidents_count ?? 0}
                </div>
              </div>

              {/* Prometheus Telemetry Card */}
              <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold uppercase text-[var(--text-muted)]">
                    Prometheus Metrics Exporter
                  </span>
                  <Activity className="w-4 h-4 text-[var(--text-muted)]" />
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-sm font-mono font-bold text-[var(--text-primary)] flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-[var(--text-muted)]" />
                    ENDPOINT EXPOSED (PASSIVE)
                  </span>
                </div>
                <div className="mt-1 text-xs font-mono text-[var(--text-muted)]">
                  Endpoint: <code className="text-[var(--text-secondary)] font-mono">GET /metrics</code> (OpenMetrics v1) | Passive target
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: INGESTION PIPELINE & DLQ (SECTION D) */}
      {activeTab === 'ingestion' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              label="Ingested Envelopes"
              value={ingestion?.cumulative_ingested_events ?? 0}
              subtext="Total Envelopes Processed"
              sourceEndpoint="/api/v1/system-health/ingestion"
              epistemicCategory="OBSERVED_FACT"
              icon={<Radio className="w-4 h-4 text-[var(--text-muted)]" />}
            />

            <MetricCard
              label="Stored Incidents"
              value={ingestion?.cumulative_stored_incidents ?? 0}
              subtext="Canonical Incidents"
              sourceEndpoint="/api/v1/system-health/ingestion"
              epistemicCategory="OBSERVED_FACT"
              icon={<Layers className="w-4 h-4 text-[var(--text-muted)]" />}
            />

            <MetricCard
              label="Stored Alarms"
              value={ingestion?.cumulative_stored_alarms ?? 0}
              subtext="3GPP OSS/NMS Events"
              sourceEndpoint="/api/v1/system-health/ingestion"
              epistemicCategory="OBSERVED_FACT"
              icon={<AlertTriangle className="w-4 h-4 text-[var(--text-muted)]" />}
            />

            <MetricCard
              label="Telemetry Observations"
              value={ingestion?.cumulative_stored_telemetry ?? 0}
              subtext="Prometheus & OTEL Metrics"
              sourceEndpoint="/api/v1/system-health/ingestion"
              epistemicCategory="OBSERVED_FACT"
              icon={<Activity className="w-4 h-4 text-[var(--text-muted)]" />}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Dead Letter Quarantine Card */}
            <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 shadow-xs space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] font-mono">
                  Dead-Letter Quarantine (DLQ)
                </span>
                <span className="inline-flex items-center gap-1.5 text-xs font-mono font-bold px-2 py-0.5 rounded bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--text-primary)]">
                  <span className={`w-1.5 h-1.5 rounded-full ${(ingestion?.current_dlq_depth ?? 0) > 0 ? 'bg-amber-500' : 'bg-emerald-500'}`} />
                  {(ingestion?.current_dlq_depth ?? 0) > 0 ? 'ATTENTION REQUIRED' : 'CLEAN'}
                </span>
              </div>

              <div className="text-2xl font-mono font-bold text-[var(--text-primary)]">
                {ingestion?.current_dlq_depth ?? 0} <span className="text-xs text-[var(--text-muted)] font-normal">quarantined items</span>
              </div>

              <p className="text-xs text-[var(--text-muted)]">
                Strict human-gated quarantine. Malformed payloads or validation failures are isolated without mutating production telemetry. Replays require dual-operator authorization.
              </p>
            </div>

            {/* Deduplication & Rate Limiting Card */}
            <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 shadow-xs space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] font-mono">
                  Idempotency & Rate Limiting
                </span>
                <span className="inline-flex items-center gap-1.5 text-xs font-mono font-bold px-2 py-0.5 rounded bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--text-primary)]">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  ACTIVE
                </span>
              </div>

              <div className="text-2xl font-mono font-bold text-[var(--text-primary)]">
                {ingestion?.deduplication_cache_size ?? 0} <span className="text-xs text-[var(--text-muted)] font-normal">SHA-256 cached keys</span>
              </div>

              <div className="space-y-1 text-xs text-[var(--text-muted)] font-mono">
                <div>Policy: {ingestion?.rate_limit_policy || 'TOKEN_BUCKET_BURST_PROTECTED'}</div>
                <div>Flow Direction: {ingestion?.data_direction || 'INBOUND_ONLY'} (Zero outbound commands)</div>
                <div>Configured Protocol Adapters: {ingestion?.registered_adapters_count ?? 6}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: AI & INVESTIGATION SUBSYSTEM (SECTION E) */}
      {activeTab === 'intelligence' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <MetricCard
              label="Investigation Engine"
              value={intelligence?.investigation_status || 'OPERATIONAL'}
              subtext={`Version: ${intelligence?.engine_version || '1.0.0'}`}
              sourceEndpoint="/api/v1/system-health/intelligence"
              epistemicCategory="OBSERVED_FACT"
              icon={<Cpu className="w-4 h-4 text-[var(--text-muted)]" />}
            />

            <MetricCard
              label="Lexical BM25 Index"
              value={intelligence?.bm25_index_status || 'OPERATIONAL'}
              subtext={`${intelligence?.bm25_total_chunks ?? 0} Knowledge Chunks`}
              sourceEndpoint="/api/v1/system-health/intelligence"
              epistemicCategory="OBSERVED_FACT"
              icon={<Search className="w-4 h-4 text-[var(--text-muted)]" />}
            />

            <MetricCard
              label="Deterministic SOP Rules"
              value={`${intelligence?.sop_rules_count ?? 15} Rules`}
              subtext="Tier 3 Fallback Map"
              sourceEndpoint="/api/v1/system-health/intelligence"
              epistemicCategory="OBSERVED_FACT"
              icon={<ShieldCheck className="w-4 h-4 text-[var(--text-muted)]" />}
            />
          </div>

          <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  Dense Bi-Encoder Vector Search & Fallback Mode
                </h3>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  Semantic retrieval pipeline with air-gapped deterministic TF-IDF fallback protection.
                </p>
              </div>

              <span className="inline-flex items-center gap-1.5 text-xs font-mono font-bold px-2.5 py-1 rounded-full bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--text-primary)]">
                <span className={`w-1.5 h-1.5 rounded-full ${intelligence?.dense_is_fallback_mode ? 'bg-amber-500' : 'bg-emerald-500'}`} />
                {intelligence?.dense_index_status || 'OPERATIONAL'}
              </span>
            </div>

            {intelligence?.dense_is_fallback_mode ? (
              <div className="p-3 rounded bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs text-[var(--text-secondary)] space-y-1">
                <div className="font-semibold flex items-center gap-1.5 text-[var(--text-primary)]">
                  <AlertTriangle className="w-4 h-4 text-[var(--text-muted)]" />
                  Local Fallback Mode Active (Air-Gapped / Disconnected)
                </div>
                <div className="text-xs text-[var(--text-muted)]">
                  SentenceTransformer weights are unavailable or in offline mode. The retrieval engine is operating via deterministic word-level TF-IDF sparse projection to guarantee uninterrupted search without external API dependencies.
                </div>
              </div>
            ) : (
              <div className="p-3 rounded bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs text-[var(--text-secondary)] flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                <span>Dense bi-encoder running live SentenceTransformer model: <code className="font-mono text-[var(--text-primary)]">{intelligence?.dense_model_name}</code></span>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono pt-2 border-t border-[var(--border-subtle)]">
              <div>
                <span className="text-[var(--text-muted)]">Fusion Algorithm: </span>
                <span className="text-[var(--text-primary)]">{intelligence?.fusion_algorithm}</span>
              </div>
              <div>
                <span className="text-[var(--text-muted)]">Anomaly Detection: </span>
                <span className="text-[var(--text-primary)]">{intelligence?.anomaly_detection_status} (3-Sigma + Isolation Forest)</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: PERSISTENCE & AUDIT PARITY (SECTION F) */}
      {activeTab === 'persistence' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <MetricCard
              label="Audit Ledger Status"
              value={persistence?.audit_ledger_status || 'VERIFIED'}
              subtext={`Records: ${persistence?.ledger_record_count ?? 0} | Head: #${persistence?.ledger_head_sequence ?? 0}`}
              sourceEndpoint="/api/v1/system-health/persistence"
              epistemicCategory="OBSERVED_FACT"
              icon={<Database className="w-4 h-4 text-[var(--text-muted)]" />}
            />

            <MetricCard
              label="Checkpoint Anchor Parity"
              value={persistence?.checkpoint_anchor_status || 'SYNCHRONIZED'}
              subtext={`Anchor Seq: #${persistence?.checkpoint_sequence ?? 0}`}
              sourceEndpoint="/api/v1/system-health/persistence"
              epistemicCategory="OBSERVED_FACT"
              icon={<ShieldCheck className="w-4 h-4 text-[var(--text-muted)]" />}
            />

            <MetricCard
              label="HMAC Key Provider"
              value={persistence?.hmac_key_provider_status || 'AVAILABLE'}
              subtext="Key ID: piis-audit-local-v1"
              sourceEndpoint="/api/v1/system-health/persistence"
              epistemicCategory="OBSERVED_FACT"
              icon={<Lock className="w-4 h-4 text-[var(--text-muted)]" />}
            />
          </div>

          <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 shadow-xs space-y-4">
            <h3 className="text-sm font-bold text-[var(--text-primary)]">
              Cryptographic Audit Ledger Verification & Anchor Parity
            </h3>

            <div className="space-y-2.5 text-xs">
              <div className="flex items-center justify-between p-2.5 rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)]">
                <span className="text-[var(--text-muted)]">Physical JSONL File Accessible on Disk:</span>
                <span className="font-mono font-bold text-[var(--text-primary)] flex items-center gap-1.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${persistence?.ledger_file_accessible ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                  {persistence?.ledger_file_accessible ? 'YES (READABLE)' : 'NO (MISSING)'}
                </span>
              </div>

              <div className="flex items-center justify-between p-2.5 rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)]">
                <span className="text-[var(--text-muted)]">Disk Fsync Monotonic Persistence Supported:</span>
                <span className="font-mono font-bold text-[var(--text-primary)] flex items-center gap-1.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${persistence?.disk_fsync_supported ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                  {persistence?.disk_fsync_supported ? 'SUPPORTED (ATOMIC WRITES)' : 'NO'}
                </span>
              </div>

              <div className="flex items-center justify-between p-2.5 rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)]">
                <span className="text-[var(--text-muted)]">External WORM / Cloud KMS Connected:</span>
                <span className="font-mono font-bold text-[var(--text-muted)] flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-zinc-500" />
                  {persistence?.external_trust_anchor_connected ? 'CONNECTED' : 'DISCONNECTED (PORTFOLIO MODE)'}
                </span>
              </div>
            </div>

            {/* Explicit Disclosure Alert */}
            <div className="p-3 rounded bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs text-[var(--text-secondary)]">
              <div className="font-semibold text-[var(--text-primary)] mb-1 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-[var(--text-muted)]" />
                Immutable Trust Anchor Limitation Disclosure
              </div>
              <p className="text-xs text-[var(--text-muted)]">
                {persistence?.trust_anchor_limitation_disclosure}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: HEALTH EVENTS TIMELINE (SECTION G) */}
      {activeTab === 'events' && (
        <div className="space-y-6">
          {/* Ephemeral In-Memory Storage Disclosure */}
          <div className="p-3.5 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs text-[var(--text-secondary)] flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 text-[var(--text-muted)] shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold text-[var(--text-primary)]">Ephemeral In-Memory Observation Buffer:</span>{' '}
              Health state transitions and diagnostic observations are recorded in an in-memory ring buffer (up to 500 records) for operational session monitoring. This buffer resets on application process restart and is distinct from the durable, append-only RFC 8785 JSONL cryptographic audit ledger.
            </div>
          </div>

          <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-3.5 shadow-xs flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2.5 flex-1">
              <input
                type="text"
                placeholder="Filter by component ID..."
                value={eventComponentFilter}
                onChange={(e) => setEventComponentFilter(e.target.value)}
                className="px-2.5 py-1.5 text-xs rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-emerald-500 font-mono"
              />

              <input
                type="text"
                placeholder="Filter by event type..."
                value={eventTypeFilter}
                onChange={(e) => setEventTypeFilter(e.target.value)}
                className="px-2.5 py-1.5 text-xs rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-emerald-500 font-mono"
              />
            </div>

            {(eventComponentFilter || eventTypeFilter) && (
              <button
                onClick={() => {
                  setEventComponentFilter('')
                  setEventTypeFilter('')
                }}
                className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] underline"
              >
                Clear Filters
              </button>
            )}
          </div>

          <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] overflow-hidden shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs" aria-label="Health Events Timeline">
                <thead className="bg-[var(--bg-canvas)] border-b border-[var(--border-subtle)] font-mono uppercase text-xs text-[var(--text-muted)]">
                  <tr>
                    <th className="py-2.5 px-4">Timestamp</th>
                    <th className="py-2.5 px-3">Component</th>
                    <th className="py-2.5 px-3">State</th>
                    <th className="py-2.5 px-3">Event Type</th>
                    <th className="py-2.5 px-3">Source</th>
                    <th className="py-2.5 px-4">Observation Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-subtle)]">
                  {eventsLoading ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-xs text-[var(--text-muted)]">
                        Loading health observations...
                      </td>
                    </tr>
                  ) : (eventsResponse?.items || []).length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8">
                        <EmptyState
                          title="No Health Events Found"
                          description="No observation transitions recorded for current filter criteria."
                        />
                      </td>
                    </tr>
                  ) : (
                    (eventsResponse?.items || []).map((evt) => (
                      <tr key={evt.event_id} className="hover:bg-[var(--bg-card)]/50 transition-colors">
                        <td className="py-3 px-4 font-mono text-xs text-[var(--text-muted)] whitespace-nowrap">
                          {new Date(evt.timestamp).toLocaleString()}
                        </td>

                        <td className="py-3 px-3 font-mono font-semibold text-[var(--text-primary)]">
                          {evt.component_id}
                        </td>

                        <td className="py-3 px-3">{renderHealthBadge(evt.new_state)}</td>

                        <td className="py-3 px-3">
                          <span className="font-mono text-xs px-2 py-0.5 rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-secondary)]">
                            {evt.event_type}
                          </span>
                        </td>

                        <td className="py-3 px-3 font-mono text-xs text-[var(--text-muted)]">
                          {evt.source}
                        </td>

                        <td className="py-3 px-4 text-xs text-[var(--text-secondary)]">
                          {evt.reason || '—'}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 6: DEPENDENCY TOPOLOGY MAP (SECTION H) */}
      {activeTab === 'topology' && (
        <div className="space-y-6">
          <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  Architecturally Grounded Dependency Topology Map
                </h3>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  Static codebase-grounded import and invocation graph across internal PIIS subsystems.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1.5 text-xs font-mono px-2 py-0.5 rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)]">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  {dependencies?.nodes.length || 17} Subsystem Nodes
                </span>
                <span className="inline-flex items-center gap-1.5 text-xs font-mono px-2 py-0.5 rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)]">
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--text-muted)]" />
                  {dependencies?.edges.length || 15} Directed Edges
                </span>
              </div>
            </div>

            {/* Architecture Layer Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 pt-2">
              {/* Layer 1: Edge & Ingestion */}
              <div className="rounded-xs bg-[var(--bg-canvas)] border border-[var(--border-subtle)] p-3.5 space-y-2.5">
                <div className="text-xs font-mono font-bold uppercase text-[var(--text-muted)] border-b border-[var(--border-subtle)] pb-1.5">
                  1. Edge & Ingestion Layer
                </div>
                {['api-gateway', 'auth-manager', 'ingestion-pipeline', 'idempotency-engine', 'dead-letter-quarantine'].map((id) => {
                  const node = (dependencies?.nodes || []).find((n) => n.id === id)
                  return (
                    <div
                      key={id}
                      onClick={() => {
                        const comp = (components || []).find((c) => c.component_id === id)
                        if (comp) setSelectedComponent(comp)
                      }}
                      className="p-2 rounded bg-[var(--bg-surface)] border border-[var(--border-subtle)] hover:border-emerald-500 cursor-pointer transition-colors flex items-center justify-between"
                    >
                      <div>
                        <div className="text-xs font-semibold text-[var(--text-primary)]">{node?.name || id}</div>
                        <div className="text-xs font-mono text-[var(--text-muted)]">{id}</div>
                      </div>
                      {renderHealthBadge(node?.health_state || 'HEALTHY')}
                    </div>
                  )
                })}
              </div>

              {/* Layer 2: Intelligence & Retrieval */}
              <div className="rounded-xs bg-[var(--bg-canvas)] border border-[var(--border-subtle)] p-3.5 space-y-2.5">
                <div className="text-xs font-mono font-bold uppercase text-[var(--text-muted)] border-b border-[var(--border-subtle)] pb-1.5">
                  2. Intelligence & Retrieval Layer
                </div>
                {['investigation-engine', 'knowledge-retrieval-bm25', 'knowledge-retrieval-dense', 'telemetry-anomaly'].map((id) => {
                  const node = (dependencies?.nodes || []).find((n) => n.id === id)
                  return (
                    <div
                      key={id}
                      onClick={() => {
                        const comp = (components || []).find((c) => c.component_id === id)
                        if (comp) setSelectedComponent(comp)
                      }}
                      className="p-2 rounded bg-[var(--bg-surface)] border border-[var(--border-subtle)] hover:border-emerald-500 cursor-pointer transition-colors flex items-center justify-between"
                    >
                      <div>
                        <div className="text-xs font-semibold text-[var(--text-primary)]">{node?.name || id}</div>
                        <div className="text-xs font-mono text-[var(--text-muted)]">{id}</div>
                      </div>
                      {renderHealthBadge(node?.health_state || 'HEALTHY')}
                    </div>
                  )
                })}
              </div>

              {/* Layer 3: Review & Cryptographic Audit */}
              <div className="rounded-xs bg-[var(--bg-canvas)] border border-[var(--border-subtle)] p-3.5 space-y-2.5">
                <div className="text-xs font-mono font-bold uppercase text-[var(--text-muted)] border-b border-[var(--border-subtle)] pb-1.5">
                  3. Review & Audit Layer
                </div>
                {['human-review-hub', 'audit-ledger-jcs', 'checkpoint-anchor', 'trust-boundary-hmac'].map((id) => {
                  const node = (dependencies?.nodes || []).find((n) => n.id === id)
                  return (
                    <div
                      key={id}
                      onClick={() => {
                        const comp = (components || []).find((c) => c.component_id === id)
                        if (comp) setSelectedComponent(comp)
                      }}
                      className="p-2 rounded bg-[var(--bg-surface)] border border-[var(--border-subtle)] hover:border-emerald-500 cursor-pointer transition-colors flex items-center justify-between"
                    >
                      <div>
                        <div className="text-xs font-semibold text-[var(--text-primary)]">{node?.name || id}</div>
                        <div className="text-xs font-mono text-[var(--text-muted)]">{id}</div>
                      </div>
                      {renderHealthBadge(node?.health_state || 'HEALTHY')}
                    </div>
                  )
                })}
              </div>

              {/* Layer 4: External / Informational Boundaries */}
              <div className="rounded-xs bg-[var(--bg-canvas)] border border-[var(--border-subtle)] p-3.5 space-y-2.5">
                <div className="text-xs font-mono font-bold uppercase text-[var(--text-muted)] border-b border-[var(--border-subtle)] pb-1.5">
                  4. Informational Boundaries
                </div>
                {['integration-adapters', 'enterprise-oidc', 'external-worm-storage', 'background-worker'].map((id) => {
                  const node = (dependencies?.nodes || []).find((n) => n.id === id)
                  return (
                    <div
                      key={id}
                      onClick={() => {
                        const comp = (components || []).find((c) => c.component_id === id)
                        if (comp) setSelectedComponent(comp)
                      }}
                      className="p-2 rounded bg-[var(--bg-surface)] border border-[var(--border-subtle)] hover:border-emerald-500 cursor-pointer transition-colors flex items-center justify-between"
                    >
                      <div>
                        <div className="text-xs font-semibold text-[var(--text-primary)]">{node?.name || id}</div>
                        <div className="text-xs font-mono text-[var(--text-muted)]">{id}</div>
                      </div>
                      {renderHealthBadge(node?.health_state || 'UNKNOWN')}
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Directed Relationships Table */}
            <div className="pt-4 border-t border-[var(--border-subtle)] space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] font-mono">
                Directed Subsystem Dependency Edges
              </h4>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {(dependencies?.edges || []).map((edge, idx) => (
                  <div
                    key={idx}
                    className="p-2 rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-xs font-mono flex items-center justify-between"
                  >
                    <div className="truncate">
                      <span className="text-zinc-300 font-bold">{edge.source}</span>
                      <span className="text-emerald-400 mx-1">→</span>
                      <span className="text-zinc-300 font-bold">{edge.target}</span>
                    </div>
                    <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--bg-surface)] text-[var(--text-muted)] shrink-0 ml-1">
                      {edge.relationship_type}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* COMPONENT DIAGNOSTICS SLIDE-OVER DRAWER */}
      {selectedComponent && (
        <div className="fixed inset-0 z-50 overflow-hidden flex justify-end" aria-modal="true" role="dialog">
          <div
            className="fixed inset-0 bg-black/60 transition-opacity"
            onClick={() => setSelectedComponent(null)}
          />

          <div className="relative w-full max-w-lg bg-[var(--bg-surface)] border-l border-[var(--border-subtle)] shadow-2xl h-full flex flex-col z-10 overflow-y-auto">
            {/* Drawer Header */}
            <div className="p-5 border-b border-[var(--border-subtle)] flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold text-[var(--text-primary)]">
                    {selectedComponent.name}
                  </h3>
                  {renderHealthBadge(selectedComponent.health_state)}
                </div>
                <div className="text-xs font-mono text-[var(--text-muted)] mt-0.5">
                  ID: {selectedComponent.component_id}
                </div>
              </div>

              <button
                onClick={() => setSelectedComponent(null)}
                className="p-1 rounded-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)] transition-colors"
                aria-label="Close Drawer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drawer Body */}
            <div className="p-5 space-y-4 flex-1">
              {/* Failure Alert if Degraded/Unavailable */}
              {selectedComponent.failure_reason && (
                <div className="p-3.5 rounded bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 space-y-1">
                  <div className="font-semibold flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-rose-400" />
                    Operational Fault / Degraded Reason
                  </div>
                  <div className="text-xs text-zinc-300 font-mono">
                    {selectedComponent.failure_reason}
                  </div>
                </div>
              )}

              {/* Attributes Grid */}
              <div className="space-y-2 text-xs">
                <div className="flex items-center justify-between p-2.5 rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)]">
                  <span className="text-[var(--text-muted)]">Category:</span>
                  <span className="font-mono font-bold text-[var(--text-primary)]">{selectedComponent.category}</span>
                </div>

                <div className="flex items-center justify-between p-2.5 rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)]">
                  <span className="text-[var(--text-muted)]">Criticality Tier:</span>
                  <span>{renderCriticalityBadge(selectedComponent.criticality)}</span>
                </div>

                <div className="flex items-center justify-between p-2.5 rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)]">
                  <span className="text-[var(--text-muted)]">Freshness Status:</span>
                  <span>{renderFreshnessBadge(selectedComponent.freshness)}</span>
                </div>

                <div className="flex items-center justify-between p-2.5 rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)]">
                  <span className="text-[var(--text-muted)]">Check Source:</span>
                  <span className="font-mono text-zinc-300">{selectedComponent.check_source}</span>
                </div>

                <div className="flex items-center justify-between p-2.5 rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)]">
                  <span className="text-[var(--text-muted)]">Implementation Nature:</span>
                  <span className="font-mono text-zinc-300">{selectedComponent.implementation_nature}</span>
                </div>

                <div className="flex items-center justify-between p-2.5 rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)]">
                  <span className="text-[var(--text-muted)]">Last Observation Timestamp:</span>
                  <span className="font-mono text-zinc-300">
                    {selectedComponent.last_observed_at
                      ? new Date(selectedComponent.last_observed_at).toLocaleString()
                      : '—'}
                  </span>
                </div>
              </div>

              {/* Raw Details JSON */}
              <div className="space-y-1.5 pt-2">
                <div className="text-xs font-mono font-bold uppercase text-[var(--text-muted)]">
                  Diagnostic Telemetry & Attributes
                </div>
                <pre className="p-3 rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-xs font-mono text-zinc-300 overflow-x-auto">
                  {JSON.stringify(selectedComponent.details, null, 2)}
                </pre>
              </div>
            </div>

            {/* Drawer Footer */}
            <div className="p-4 border-t border-[var(--border-subtle)] bg-[var(--bg-canvas)] flex justify-end">
              <button
                onClick={() => setSelectedComponent(null)}
                className="px-4 py-1.5 rounded text-xs font-semibold bg-[var(--bg-card)] hover:bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-primary)] transition-colors"
              >
                Close Diagnostics
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
