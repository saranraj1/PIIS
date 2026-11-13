import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Layers,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  Activity,
  ArrowRight,
  Lock,
  Inbox,
  Eye,
  X,
  Search,
  Filter,
  Info,
  Server,
  Zap,
  RotateCcw,
} from 'lucide-react'
import { apiClient } from '../api/client'
import { API_ENDPOINTS } from '../api/endpoints'
import type {
  IntegrationRegistryItem,
  IntegrationSummaryResponse,
  IntegrationDetailResponse,
  IntegrationActivityItem,
  DataFlowResponse,
  DeadLetterItem,
  PaginatedResponse,
} from '../api/types'
import { EpistemicBadge } from '../components/epistemic/EpistemicBadge'
import { MetricCard } from '../components/common/MetricCard'
import { EmptyState } from '../components/common/EmptyState'

type TabType = 'registry' | 'dataflow' | 'activity' | 'dlq'

export const IntegrationsPage: React.FC = () => {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<TabType>('registry')

  // Filters for Registry
  const [registryCategory, setRegistryCategory] = useState<string>('ALL')
  const [registryStatus, setRegistryStatus] = useState<string>('ALL')
  const [registrySearch, setRegistrySearch] = useState<string>('')

  // Selected Integration for Detail Drawer
  const [selectedIntegrationId, setSelectedIntegrationId] = useState<string | null>(null)

  // Filters for Activity Stream
  const [activityPage, setActivityPage] = useState<number>(0)
  const [activityStatus, setActivityStatus] = useState<string>('ALL')
  const [activityEventType, setActivityEventType] = useState<string>('ALL')
  const [activityAdapterId, setActivityAdapterId] = useState<string>('')

  // DLQ inspect / retry states
  const [inspectedDlqItem, setInspectedDlqItem] = useState<DeadLetterItem | null>(null)
  const [retryFeedback, setRetryFeedback] = useState<{ status: 'success' | 'error'; message: string } | null>(null)

  // 1. Fetch Summary Metrics
  const {
    data: summary,
    isLoading: isSummaryLoading,
    refetch: refetchSummary,
  } = useQuery<IntegrationSummaryResponse>({
    queryKey: ['integrations-summary'],
    queryFn: () => apiClient.get<IntegrationSummaryResponse>(API_ENDPOINTS.INTEGRATIONS_SUMMARY),
  })

  // 2. Fetch Registry Items
  const {
    data: registryItems,
    isLoading: isRegistryLoading,
    refetch: refetchRegistry,
  } = useQuery<IntegrationRegistryItem[]>({
    queryKey: ['integrations-registry', registryCategory, registryStatus, registrySearch],
    queryFn: () => {
      const params = new URLSearchParams()
      if (registryCategory !== 'ALL') params.append('category', registryCategory)
      if (registryStatus !== 'ALL') params.append('status', registryStatus)
      if (registrySearch.trim()) params.append('search', registrySearch.trim())
      const qs = params.toString() ? `?${params.toString()}` : ''
      return apiClient.get<IntegrationRegistryItem[]>(`${API_ENDPOINTS.INTEGRATIONS_REGISTRY}${qs}`)
    },
  })

  // 3. Fetch Detail Drawer Data when selected
  const {
    data: selectedDetail,
    isLoading: isDetailLoading,
  } = useQuery<IntegrationDetailResponse>({
    queryKey: ['integration-detail', selectedIntegrationId],
    queryFn: () => apiClient.get<IntegrationDetailResponse>(API_ENDPOINTS.INTEGRATION_GET(selectedIntegrationId!)),
    enabled: !!selectedIntegrationId,
  })

  // 4. Fetch Data Flow Topology
  const {
    data: dataFlow,
    isLoading: isDataFlowLoading,
    refetch: refetchDataFlow,
  } = useQuery<DataFlowResponse>({
    queryKey: ['integrations-data-flow'],
    queryFn: () => apiClient.get<DataFlowResponse>(API_ENDPOINTS.INTEGRATIONS_DATA_FLOW),
    enabled: activeTab === 'dataflow',
  })

  // 5. Fetch Activity Stream
  const activityLimit = 15
  const {
    data: activityData,
    isLoading: isActivityLoading,
    refetch: refetchActivity,
  } = useQuery<PaginatedResponse<IntegrationActivityItem>>({
    queryKey: ['integrations-activity', activityPage, activityStatus, activityEventType, activityAdapterId],
    queryFn: () => {
      const params = new URLSearchParams()
      params.append('limit', String(activityLimit))
      params.append('offset', String(activityPage * activityLimit))
      if (activityStatus !== 'ALL') params.append('status', activityStatus)
      if (activityEventType !== 'ALL') params.append('event_type', activityEventType)
      if (activityAdapterId.trim()) params.append('integration_id', activityAdapterId.trim())
      return apiClient.get<PaginatedResponse<IntegrationActivityItem>>(`${API_ENDPOINTS.INTEGRATIONS_ACTIVITY}?${params.toString()}`)
    },
    enabled: activeTab === 'activity',
  })

  // 6. Fetch Dead-Letter Queue Items
  const {
    data: dlqData,
    isLoading: isDlqLoading,
    refetch: refetchDlq,
  } = useQuery<PaginatedResponse<DeadLetterItem>>({
    queryKey: ['integrations-dlq'],
    queryFn: () => apiClient.get<PaginatedResponse<DeadLetterItem>>(API_ENDPOINTS.INTEGRATIONS_DLQ),
    enabled: activeTab === 'dlq' || activeTab === 'registry',
  })

  // Mutation for DLQ retry
  const retryMutation = useMutation({
    mutationFn: (itemId: string) =>
      apiClient.post<{ status: string; message?: string; error?: string }>(
        API_ENDPOINTS.INTEGRATION_OPS.RETRY_DEAD_LETTER(itemId),
        {}
      ),
    onSuccess: (data) => {
      setRetryFeedback({
        status: 'success',
        message: data.message || `Dead-letter payload successfully replayed through pipeline.`,
      })
      queryClient.invalidateQueries({ queryKey: ['integrations-dlq'] })
      queryClient.invalidateQueries({ queryKey: ['integrations-summary'] })
      queryClient.invalidateQueries({ queryKey: ['integrations-activity'] })
    },
    onError: (err: Error) => {
      setRetryFeedback({
        status: 'error',
        message: `Retry replay failed: ${err.message}`,
      })
    },
  })

  const handleRefreshAll = () => {
    refetchSummary()
    refetchRegistry()
    if (activeTab === 'dataflow') refetchDataFlow()
    if (activeTab === 'activity') refetchActivity()
    if (activeTab === 'dlq') refetchDlq()
  }

  return (
    <div className="space-y-6">
      {/* Disclaimer / Read-Only Governance Banner */}
      <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 transition-colors">
        <div className="flex items-start gap-3">
          <ShieldCheck className="w-5 h-5 text-[var(--text-primary)] shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-bold text-[var(--text-primary)] uppercase tracking-wide font-mono">
                Telecom Protocol Adapters & Read-Only Ingress Gateways
              </span>
              <span className="px-2 py-0.5 rounded-xs text-xs font-mono font-bold bg-[var(--bg-subtle)] text-[var(--text-secondary)] border border-[var(--border-strong)]">
                PORTFOLIO EDITION
              </span>
              <span className="px-2 py-0.5 rounded-xs text-xs font-mono font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                STRICT READ-ONLY BOUNDARY
              </span>
            </div>
            <p className="text-[var(--text-muted)] leading-relaxed">
              PIIS connects via local simulations and reference implementations to standard telecom sources (ServiceNow, Jira, Prometheus, OpenTelemetry, 3GPP OSS/NMS).
              All inbound adapters strictly enforce read-only boundaries (safe HTTP methods only); network element mutations, ticket modifications, and external command executions are architecturally barred.
            </p>
          </div>
        </div>
      </div>

      {/* Workspace Header Card */}
      <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition-colors">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xs bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-base font-bold text-[var(--text-primary)]">
              Integrations Workspace
            </h2>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Protocol ingestion status, schema normalizers, pipeline data flow topology, and dead-letter quarantine inspector
            </p>
          </div>
        </div>

        <button
          onClick={handleRefreshAll}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs text-xs font-medium bg-[var(--bg-subtle)] hover:bg-[var(--border-subtle)] border border-[var(--border-subtle)] transition-colors self-start sm:self-auto text-[var(--text-primary)] cursor-pointer font-mono"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isSummaryLoading || isRegistryLoading ? 'animate-spin' : ''}`} />
          Refresh Integrations
        </button>
      </div>

      {/* Section A: Ecosystem Overview Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3">
        <MetricCard
          label="Total Adapters"
          value={summary?.total_adapters ?? 6}
          subtext="Registered in pipeline"
          sourceEndpoint="GET /api/v1/integrations/summary"
          epistemicCategory="OBSERVED_FACT"
          isLoading={isSummaryLoading}
          icon={<Server className="w-4 h-4" />}
        />
        <MetricCard
          label="Readiness State"
          value={
            <span className="text-[var(--text-primary)] font-bold">
              {summary?.overall_readiness ?? 'OPERATIONAL'}
            </span>
          }
          subtext={`${summary?.available_count ?? 6} Available / ${summary?.degraded_count ?? 0} Degraded`}
          sourceEndpoint="GET /api/v1/integrations/summary"
          epistemicCategory="OBSERVED_FACT"
          isLoading={isSummaryLoading}
          icon={<CheckCircle2 className="w-4 h-4 text-[var(--text-muted)]" />}
        />
        <MetricCard
          label="Ingestion Mode"
          value="INBOUND ONLY"
          subtext="Safe GET/HEAD enforced"
          sourceEndpoint="GET /api/v1/integrations"
          epistemicCategory="DETERMINISTIC_RULE"
          icon={<Lock className="w-4 h-4 text-[var(--text-muted)]" />}
        />
        <MetricCard
          label="Architecture Modes"
          value={`${summary?.simulated_count ?? 4} Sim / ${summary?.reference_count ?? 2} Ref`}
          subtext="Local sandbox fixtures"
          sourceEndpoint="GET /api/v1/integrations/summary"
          epistemicCategory="REFERENCE_DATA"
          isLoading={isSummaryLoading}
          icon={<Zap className="w-4 h-4 text-[var(--text-muted)]" />}
        />
        <MetricCard
          label="Quarantined (DLQ)"
          value={summary?.total_dlq_count ?? 0}
          subtext="Malformed payloads"
          sourceEndpoint="GET /api/v1/integrations/dead-letter"
          epistemicCategory="OBSERVED_FACT"
          isLoading={isSummaryLoading}
          icon={<Inbox className="w-4 h-4 text-[var(--text-muted)]" />}
        />
        <MetricCard
          label="Events Ingested"
          value={summary?.total_ingested_events ?? 0}
          subtext="Pipeline throughput"
          sourceEndpoint="GET /api/v1/integrations/summary"
          epistemicCategory="OBSERVED_FACT"
          isLoading={isSummaryLoading}
          icon={<Activity className="w-4 h-4 text-[var(--text-muted)]" />}
        />
      </div>

      {/* Navigation Tabs */}
      <div className="border-b border-[var(--border-subtle)] flex items-center gap-2 overflow-x-auto no-scrollbar">
        <button
          onClick={() => setActiveTab('registry')}
          className={`px-4 py-2 text-xs font-semibold border-b-2 transition-colors flex items-center gap-1.5 cursor-pointer whitespace-nowrap font-mono ${
            activeTab === 'registry'
              ? 'border-[var(--text-primary)] text-[var(--text-primary)] bg-[var(--bg-subtle)]'
              : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
          }`}
        >
          <Server className="w-3.5 h-3.5" />
          Adapter Registry & Health
          <span className="ml-1 px-1.5 py-0.5 rounded-xs text-xs font-mono tabular-nums bg-[var(--bg-subtle)] text-[var(--text-muted)] border border-[var(--border-subtle)]">
            {summary?.total_adapters ?? 6}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('dataflow')}
          className={`px-4 py-2 text-xs font-semibold border-b-2 transition-colors flex items-center gap-1.5 cursor-pointer whitespace-nowrap font-mono ${
            activeTab === 'dataflow'
              ? 'border-[var(--text-primary)] text-[var(--text-primary)] bg-[var(--bg-subtle)]'
              : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
          }`}
        >
          <ArrowRight className="w-3.5 h-3.5" />
          Pipeline Data Flow Topology
          <span className="ml-1 px-1.5 py-0.5 rounded-xs text-xs font-mono tabular-nums bg-[var(--bg-subtle)] text-[var(--text-muted)] border border-[var(--border-subtle)]">
            8 Stages
          </span>
        </button>

        <button
          onClick={() => setActiveTab('activity')}
          className={`px-4 py-2 text-xs font-semibold border-b-2 transition-colors flex items-center gap-1.5 cursor-pointer whitespace-nowrap font-mono ${
            activeTab === 'activity'
              ? 'border-[var(--text-primary)] text-[var(--text-primary)] bg-[var(--bg-subtle)]'
              : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          Activity Stream
        </button>

        <button
          onClick={() => setActiveTab('dlq')}
          className={`px-4 py-2 text-xs font-semibold border-b-2 transition-colors flex items-center gap-1.5 cursor-pointer whitespace-nowrap font-mono ${
            activeTab === 'dlq'
              ? 'border-[var(--text-primary)] text-[var(--text-primary)] bg-[var(--bg-subtle)]'
              : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
          }`}
        >
          <Inbox className="w-3.5 h-3.5" />
          Dead-Letter Quarantine (DLQ)
          <span
            className={`ml-1 px-1.5 py-0.5 rounded-xs text-xs font-mono tabular-nums border ${
              (summary?.total_dlq_count ?? 0) > 0
                ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/40 font-bold'
                : 'bg-[var(--bg-subtle)] text-[var(--text-muted)] border-[var(--border-subtle)]'
            }`}
          >
            {summary?.total_dlq_count ?? 0}
          </span>
        </button>
      </div>

      {/* =====================================================================
          TAB 1: ADAPTER REGISTRY & HEALTH
         ===================================================================== */}
      {activeTab === 'registry' && (
        <div className="space-y-6">
          {/* Filters Bar */}
          <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-3 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div className="flex items-center gap-2 flex-1">
              <div className="relative flex-1 max-w-sm">
                <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  type="text"
                  placeholder="Search adapters by name, ID, or provider..."
                  value={registrySearch}
                  onChange={(e) => setRegistrySearch(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 rounded-xs text-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--border-strong)]"
                />
                {registrySearch && (
                  <button
                    onClick={() => setRegistrySearch('')}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>

              {/* Category Pills */}
              <div className="flex items-center gap-1.5 overflow-x-auto">
                {['ALL', 'ITSM', 'TELEMETRY', 'OSS_NMS_ALARM'].map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setRegistryCategory(cat)}
                    className={`px-2.5 py-1 rounded-xs text-xs font-medium border transition-colors cursor-pointer ${
                      registryCategory === cat
                        ? 'bg-[var(--text-primary)] text-[var(--bg-surface)] font-semibold border-[var(--text-primary)]'
                        : 'bg-[var(--bg-card)] text-[var(--text-muted)] border-[var(--border-subtle)] hover:bg-[var(--bg-canvas)]'
                    }`}
                  >
                    {cat === 'ALL' ? 'All Categories' : cat}
                  </button>
                ))}
              </div>
            </div>

            {/* Status Select */}
            <div className="flex items-center gap-2">
              <Filter className="w-3.5 h-3.5 text-[var(--text-muted)]" />
              <select
                value={registryStatus}
                onChange={(e) => setRegistryStatus(e.target.value)}
                className="px-2.5 py-1.5 rounded-xs text-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--border-strong)] cursor-pointer"
              >
                <option value="ALL">All Operational Statuses</option>
                <option value="AVAILABLE">AVAILABLE Only</option>
                <option value="DEGRADED">DEGRADED Only</option>
                <option value="UNAVAILABLE">UNAVAILABLE Only</option>
              </select>
            </div>
          </div>

          {/* Registry Table */}
          <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] overflow-hidden shadow-xs">
            <div className="p-3.5 bg-[var(--bg-card)] border-b border-[var(--border-subtle)] flex items-center justify-between">
              <span className="text-xs font-semibold text-[var(--text-primary)]">
                Configured Protocol Adapters ({registryItems?.length ?? 0})
              </span>
              <span className="text-xs text-[var(--text-muted)] font-mono">
                Safe HTTP Methods: GET, HEAD • Inbound Only
              </span>
            </div>

            {isRegistryLoading ? (
              <div className="p-8 text-center text-xs text-[var(--text-muted)] animate-pulse">
                Loading protocol adapter registry...
              </div>
            ) : !registryItems || registryItems.length === 0 ? (
              <EmptyState
                title="No Adapters Match Query"
                description="Try clearing search filters or selecting 'All Categories'."
                actionLabel="Clear Filters"
                onAction={() => {
                  setRegistrySearch('')
                  setRegistryCategory('ALL')
                  setRegistryStatus('ALL')
                }}
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[var(--bg-canvas)] text-[var(--text-muted)] border-b border-[var(--border-subtle)] uppercase text-xs tracking-wider">
                    <tr>
                      <th className="px-4 py-2.5">Adapter ID</th>
                      <th className="px-4 py-2.5">Connector Name</th>
                      <th className="px-4 py-2.5">Category</th>
                      <th className="px-4 py-2.5">Connection Mode</th>
                      <th className="px-4 py-2.5">Operational Status</th>
                      <th className="px-4 py-2.5">Rate Limit</th>
                      <th className="px-4 py-2.5">Heartbeat</th>
                      <th className="px-4 py-2.5 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-subtle)]">
                    {registryItems.map((adapter) => {
                      const isAvailable = adapter.operational_status === 'AVAILABLE'

                      return (
                        <tr
                          key={adapter.integration_id}
                          className="hover:bg-[var(--bg-card)] transition-colors group cursor-pointer"
                          onClick={() => setSelectedIntegrationId(adapter.integration_id)}
                        >
                          <td className="px-4 py-3 font-mono font-bold text-[var(--text-primary)]">
                            {adapter.integration_id}
                          </td>
                          <td className="px-4 py-3">
                            <div className="font-semibold text-[var(--text-primary)]">
                              {adapter.name}
                            </div>
                            <div className="text-xs text-[var(--text-muted)]">
                              Provider: {adapter.provider_type} ({adapter.adapter_class})
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-0.5 rounded-xs text-xs font-mono font-medium border border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[var(--text-secondary)]">
                              {adapter.category}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-0.5 rounded-xs text-xs font-mono font-medium border border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[var(--text-secondary)]">
                              {adapter.connection_mode}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs text-xs font-mono font-medium border border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[var(--text-primary)]">
                              <span
                                className={`w-1.5 h-1.5 rounded-full ${
                                  isAvailable ? 'bg-emerald-500' : 'bg-amber-500'
                                }`}
                              />
                              {adapter.operational_status}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-mono text-xs text-[var(--text-muted)]">
                            {adapter.rate_limit_rps} rps
                          </td>
                          <td className="px-4 py-3 font-mono text-xs text-[var(--text-muted)]">
                            {adapter.last_heartbeat ? new Date(adapter.last_heartbeat).toLocaleTimeString() : 'N/A'}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                setSelectedIntegrationId(adapter.integration_id)
                              }}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xs text-xs font-medium bg-[var(--bg-canvas)] hover:bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors cursor-pointer"
                            >
                              <Eye className="w-3 h-3 text-[var(--text-muted)]" />
                              Inspect
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Section F: Live Health & Heartbeat Cards */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] font-mono">
                Operational Heartbeat Grid
              </h3>
              <span className="text-xs text-[var(--text-muted)]">
                Autonomous heartbeat verification running locally
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {registryItems?.map((adapter) => {
                const isHealthy = adapter.operational_status === 'AVAILABLE'

                return (
                  <div
                    key={adapter.integration_id}
                    className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 shadow-xs space-y-3 cursor-pointer hover:border-[var(--border-strong)] transition-colors"
                    onClick={() => setSelectedIntegrationId(adapter.integration_id)}
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-[var(--text-primary)]">
                            {adapter.name}
                          </span>
                        </div>
                        <span className="text-xs font-mono text-[var(--text-primary)]">
                          {adapter.integration_id}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="relative flex h-2 w-2">
                          <span
                            className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                              isHealthy ? 'bg-emerald-400' : 'bg-amber-400'
                            }`}
                          />
                          <span
                            className={`relative inline-flex rounded-full h-2 w-2 ${
                              isHealthy ? 'bg-emerald-500' : 'bg-amber-500'
                            }`}
                          />
                        </span>
                        <span
                          className={`text-xs font-mono font-bold ${
                            isHealthy ? 'text-emerald-400' : 'text-amber-400'
                          }`}
                        >
                          {adapter.operational_status}
                        </span>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs bg-[var(--bg-card)] p-2.5 rounded border border-[var(--border-subtle)]">
                      <div>
                        <span className="text-[var(--text-muted)] block text-xs">Consecutive Failures</span>
                        <span className="font-mono font-bold text-[var(--text-primary)]">
                          {adapter.consecutive_failures}
                        </span>
                      </div>
                      <div>
                        <span className="text-[var(--text-muted)] block text-xs">Data Flow</span>
                        <span className="font-mono text-emerald-400 font-bold">
                          {adapter.data_direction}
                        </span>
                      </div>
                    </div>

                    <div className="text-xs text-[var(--text-muted)] truncate">
                      {adapter.error_message ? (
                        <span className="text-rose-400 font-mono">{adapter.error_message}</span>
                      ) : (
                        <span>✓ No active protocol faults reported</span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          TAB 2: DATA FLOW TOPOLOGY (8-STAGE PIPELINE)
         ===================================================================== */}
      {activeTab === 'dataflow' && (
        <div className="space-y-6">
          <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 shadow-xs">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  End-to-End Telecom Intelligence Data Flow
                </h3>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  Visual topology of 8 ingestion, sanitization, canonical mapping, and governance stages
                </p>
              </div>
              <span className="px-2.5 py-1 rounded text-xs font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                Pipeline Health: {dataFlow?.pipeline_health ?? 'HEALTHY'}
              </span>
            </div>

            {isDataFlowLoading ? (
              <div className="p-8 text-center text-xs text-[var(--text-muted)] animate-pulse">
                Loading data flow topology...
              </div>
            ) : (
              <div className="space-y-4 pt-2">
                {/* Visual Pipeline Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {dataFlow?.stages.map((stage) => {
                    const isSimulated = stage.is_simulated

                    return (
                      <div
                        key={stage.stage_id}
                        className="rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] p-4 shadow-xs relative flex flex-col justify-between hover:border-[var(--border-strong)] transition-colors"
                      >
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <span className="w-5 h-5 rounded-full bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)] font-mono text-xs font-bold flex items-center justify-center">
                              {stage.order}
                            </span>
                            <EpistemicBadge category={stage.epistemic_badge} size="sm" />
                          </div>

                          <h4 className="text-xs font-bold text-[var(--text-primary)]">
                            {stage.title}
                          </h4>
                          <span className="text-xs text-[var(--text-muted)] block font-mono mt-0.5">
                            {stage.subtitle}
                          </span>

                          <p className="text-xs text-[var(--text-muted)] mt-2.5 leading-relaxed">
                            {stage.description}
                          </p>
                        </div>

                        <div className="mt-4 pt-3 border-t border-[var(--border-subtle)] flex items-center justify-between text-xs">
                          <span
                            className={`px-1.5 py-0.5 rounded text-xs font-mono font-bold ${
                              isSimulated
                                ? 'bg-amber-500/10 text-amber-300 border border-amber-500/20'
                                : 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20'
                            }`}
                          >
                            {isSimulated ? 'LOCAL SIMULATION' : 'DETERMINISTIC PIPELINE'}
                          </span>
                          <span className="font-mono text-[var(--text-muted)]">
                            Count: {stage.active_count}
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>

                {/* Pipeline Directed Graph Summary */}
                <div className="rounded-xs bg-[var(--bg-canvas)] border border-[var(--border-subtle)] p-4 text-xs space-y-2">
                  <span className="font-mono font-bold text-[var(--text-primary)] uppercase text-xs tracking-wider block">
                    Directed Ingestion & Quarantine Graph
                  </span>
                  <div className="flex items-center gap-2 flex-wrap font-mono text-xs text-[var(--text-muted)]">
                    <span className="text-[var(--text-primary)] font-semibold">Sources</span>
                    <ArrowRight className="w-3 h-3 text-[var(--text-muted)] shrink-0" />
                    <span className="text-[var(--text-primary)]">Adapters</span>
                    <ArrowRight className="w-3 h-3 text-[var(--text-muted)] shrink-0" />
                    <span className="text-[var(--text-primary)]">Security Defanging</span>
                    <ArrowRight className="w-3 h-3 text-[var(--text-muted)] shrink-0" />
                    <span className="text-[var(--text-primary)]">Canonical Normalization</span>
                    <ArrowRight className="w-3 h-3 text-[var(--text-muted)] shrink-0" />
                    <span className="text-[var(--text-primary)]">Deduplication</span>
                    <ArrowRight className="w-3 h-3 text-[var(--text-muted)] shrink-0" />
                    <span className="text-[var(--text-primary)]">Provenance Ledger</span>
                    <ArrowRight className="w-3 h-3 text-[var(--text-muted)] shrink-0" />
                    <span className="text-[var(--text-primary)] font-semibold">Human Review Hub</span>
                  </div>
                  <div className="text-xs text-[var(--text-muted)] pt-1">
                    * Rejected or malformed payloads bypass downstream normalization directly into the isolated Dead-Letter Queue (DLQ).
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* =====================================================================
          TAB 3: ACTIVITY STREAM
         ===================================================================== */}
      {activeTab === 'activity' && (
        <div className="space-y-4">
          {/* Filters Bar */}
          <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-3 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div className="flex items-center gap-2 flex-1">
              <div className="relative flex-1 max-w-xs">
                <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  type="text"
                  placeholder="Filter by adapter ID..."
                  value={activityAdapterId}
                  onChange={(e) => {
                    setActivityAdapterId(e.target.value)
                    setActivityPage(0)
                  }}
                  className="w-full pl-8 pr-3 py-1.5 rounded-xs text-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--border-strong)]"
                />
              </div>

              {/* Event Type Filter */}
              <select
                value={activityEventType}
                onChange={(e) => {
                  setActivityEventType(e.target.value)
                  setActivityPage(0)
                }}
                className="px-2.5 py-1.5 rounded-xs text-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--border-strong)] cursor-pointer"
              >
                <option value="ALL">All Event Types</option>
                <option value="HEARTBEAT_CHECK">HEARTBEAT_CHECK</option>
                <option value="METRIC_POLL">METRIC_POLL</option>
                <option value="INGESTION_SUCCESS">INGESTION_SUCCESS</option>
                <option value="DEAD_LETTER_REPLAY">DEAD_LETTER_REPLAY</option>
                <option value="RATE_LIMITED">RATE_LIMITED</option>
              </select>

              {/* Status Filter */}
              <select
                value={activityStatus}
                onChange={(e) => {
                  setActivityStatus(e.target.value)
                  setActivityPage(0)
                }}
                className="px-2.5 py-1.5 rounded-xs text-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--border-strong)] cursor-pointer"
              >
                <option value="ALL">All Outcomes</option>
                <option value="SUCCESS">SUCCESS</option>
                <option value="HEALTHY">HEALTHY</option>
                <option value="FAILED">FAILED</option>
              </select>
            </div>

            <button
              onClick={() => refetchActivity()}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xs text-xs font-medium bg-[var(--bg-card)] hover:bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isActivityLoading ? 'animate-spin' : ''}`} />
              Refresh Stream
            </button>
          </div>

          {/* Activity Table */}
          <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] overflow-hidden shadow-xs">
            <div className="p-3.5 bg-[var(--bg-card)] border-b border-[var(--border-subtle)] flex items-center justify-between">
              <span className="text-xs font-semibold text-[var(--text-primary)]">
                Operational Event Stream ({activityData?.total_count ?? 0} total events)
              </span>
              <span className="text-xs text-[var(--text-muted)] font-mono">
                Showing Page {activityPage + 1}
              </span>
            </div>

            {isActivityLoading ? (
              <div className="p-8 text-center text-xs text-[var(--text-muted)] animate-pulse">
                Loading activity stream...
              </div>
            ) : !activityData || activityData.items.length === 0 ? (
              <EmptyState
                title="No Events Found"
                description="No integration activity matched the selected filter criteria."
                actionLabel="Reset Stream Filters"
                onAction={() => {
                  setActivityAdapterId('')
                  setActivityEventType('ALL')
                  setActivityStatus('ALL')
                  setActivityPage(0)
                }}
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[var(--bg-canvas)] text-[var(--text-muted)] border-b border-[var(--border-subtle)] uppercase text-xs tracking-wider">
                    <tr>
                      <th className="px-4 py-2.5">Timestamp</th>
                      <th className="px-4 py-2.5">Event ID</th>
                      <th className="px-4 py-2.5">Adapter ID</th>
                      <th className="px-4 py-2.5">Event Type</th>
                      <th className="px-4 py-2.5">Outcome</th>
                      <th className="px-4 py-2.5">Details</th>
                      <th className="px-4 py-2.5">Epistemic Classification</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-subtle)]">
                    {activityData.items.map((event) => {
                      const isSuccess = event.status === 'SUCCESS' || event.status === 'HEALTHY'

                      return (
                        <tr key={event.event_id} className="hover:bg-[var(--bg-card)] transition-colors">
                          <td className="px-4 py-3 font-mono text-xs text-[var(--text-muted)] whitespace-nowrap">
                            {new Date(event.timestamp).toLocaleTimeString()}
                          </td>
                          <td className="px-4 py-3 font-mono font-bold text-[var(--text-primary)] whitespace-nowrap">
                            {event.event_id}
                          </td>
                          <td className="px-4 py-3 font-mono text-[var(--text-primary)] whitespace-nowrap">
                            {event.adapter_id}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className="px-2 py-0.5 rounded-xs text-xs font-mono font-medium bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)]">
                              {event.event_type}
                            </span>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs text-xs font-mono font-medium border border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[var(--text-primary)]">
                              <span className={`w-1.5 h-1.5 rounded-full ${isSuccess ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                              {event.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-[var(--text-muted)] max-w-md truncate">
                            {event.details}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <EpistemicBadge category={event.epistemic_tag} size="sm" />
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination Controls */}
            {activityData && activityData.total_count > activityLimit && (
              <div className="p-3 bg-[var(--bg-card)] border-t border-[var(--border-subtle)] flex items-center justify-between text-xs">
                <span className="text-[var(--text-muted)]">
                  Showing {activityPage * activityLimit + 1}–
                  {Math.min((activityPage + 1) * activityLimit, activityData.total_count)} of{' '}
                  {activityData.total_count} events
                </span>
                <div className="flex items-center gap-2">
                  <button
                    disabled={activityPage === 0}
                    onClick={() => setActivityPage((p) => Math.max(0, p - 1))}
                    className="px-2.5 py-1 rounded border border-[var(--border-subtle)] bg-[var(--bg-surface)] text-[var(--text-primary)] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[var(--bg-canvas)] cursor-pointer"
                  >
                    Previous
                  </button>
                  <button
                    disabled={(activityPage + 1) * activityLimit >= activityData.total_count}
                    onClick={() => setActivityPage((p) => p + 1)}
                    className="px-2.5 py-1 rounded border border-[var(--border-subtle)] bg-[var(--bg-surface)] text-[var(--text-primary)] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[var(--bg-canvas)] cursor-pointer"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* =====================================================================
          TAB 4: DEAD-LETTER QUEUE (DLQ) QUARANTINE
         ===================================================================== */}
      {activeTab === 'dlq' && (
        <div className="space-y-4">
          {retryFeedback && (
            <div
              className={`p-3 rounded-xs border text-xs flex items-center justify-between ${
                retryFeedback.status === 'success'
                  ? 'bg-emerald-950/20 text-emerald-300 border-emerald-500/30'
                  : 'bg-rose-950/20 text-rose-300 border-rose-500/30'
              }`}
            >
              <span>{retryFeedback.message}</span>
              <button
                onClick={() => setRetryFeedback(null)}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          <div className="rounded-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] overflow-hidden shadow-xs">
            <div className="p-3.5 bg-[var(--bg-card)] border-b border-[var(--border-subtle)] flex items-center justify-between">
              <div>
                <span className="text-xs font-semibold text-[var(--text-primary)]">
                  Dead-Letter Quarantine Repository
                </span>
                <span className="text-xs text-[var(--text-muted)] block mt-0.5">
                  Isolates unparseable or rejected raw envelopes to prevent pipeline crashes
                </span>
              </div>
              <button
                onClick={() => refetchDlq()}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs bg-[var(--bg-surface)] border border-[var(--border-subtle)] hover:bg-[var(--bg-canvas)] cursor-pointer text-[var(--text-primary)]"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isDlqLoading ? 'animate-spin' : ''}`} />
                Refresh DLQ
              </button>
            </div>

            {isDlqLoading ? (
              <div className="p-8 text-center text-xs text-[var(--text-muted)] animate-pulse">
                Checking quarantine status...
              </div>
            ) : !dlqData || dlqData.items.length === 0 ? (
              <div className="p-8 text-center rounded-xs bg-[var(--bg-card)] flex flex-col items-center justify-center gap-2">
                <div className="p-3 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <h3 className="text-sm font-semibold text-[var(--text-primary)] mt-1">
                  Quarantine Clean
                </h3>
                <p className="text-xs text-[var(--text-muted)] max-w-sm">
                  Zero unparseable or rejected payloads are currently held in the Dead-Letter Queue. All incoming envelopes have been normalized successfully.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[var(--bg-canvas)] text-[var(--text-muted)] border-b border-[var(--border-subtle)] uppercase text-xs tracking-wider">
                    <tr>
                      <th className="px-4 py-2.5">Item ID</th>
                      <th className="px-4 py-2.5">Envelope ID</th>
                      <th className="px-4 py-2.5">Source System</th>
                      <th className="px-4 py-2.5">Failure Reason</th>
                      <th className="px-4 py-2.5">Attempts</th>
                      <th className="px-4 py-2.5">Last Failed At</th>
                      <th className="px-4 py-2.5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-subtle)]">
                    {dlqData.items.map((item) => (
                      <tr key={item.item_id} className="hover:bg-[var(--bg-card)] transition-colors">
                        <td className="px-4 py-3 font-mono font-bold text-[var(--text-primary)]">
                          {item.item_id}
                        </td>
                        <td className="px-4 py-3 font-mono text-[var(--text-muted)]">
                          {item.envelope_id}
                        </td>
                        <td className="px-4 py-3 font-semibold text-[var(--text-primary)]">
                          {item.source_system}
                        </td>
                        <td className="px-4 py-3 font-mono text-[var(--text-secondary)] max-w-xs truncate">
                          {item.failure_reason}
                        </td>
                        <td className="px-4 py-3 font-mono text-[var(--text-muted)]">
                          {item.attempt_count} / 3
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-[var(--text-muted)] whitespace-nowrap">
                          {new Date(item.last_failed_at).toLocaleTimeString()}
                        </td>
                        <td className="px-4 py-3 text-right space-x-2">
                          <button
                            onClick={() => setInspectedDlqItem(item)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xs text-xs font-medium bg-[var(--bg-canvas)] hover:bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] cursor-pointer"
                          >
                            <Eye className="w-3 h-3 text-[var(--text-muted)]" />
                            Payload
                          </button>
                          <button
                            disabled={retryMutation.isPending || item.attempt_count >= 3}
                            onClick={() => retryMutation.mutate(item.item_id)}
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xs text-xs font-medium bg-[var(--bg-card)] hover:bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)] disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                          >
                            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                            <RotateCcw className="w-3 h-3 text-[var(--text-muted)]" />
                            Retry
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
      )}

      {/* =====================================================================
          SLIDE-OVER DETAIL DRAWER: INTEGRATION SPECIFICATION (SECTION C)
         ===================================================================== */}
      {selectedIntegrationId && (
        <div className="fixed inset-0 z-50 overflow-hidden flex justify-end bg-black/60 backdrop-blur-xs transition-opacity animate-in fade-in">
          <div
            className="w-full max-w-2xl bg-[var(--bg-surface)] border-l border-[var(--border-subtle)] h-full shadow-2xl flex flex-col justify-between overflow-y-auto"
            role="dialog"
            aria-label="Integration Specification Detail"
          >
            {/* Drawer Header */}
            <div className="p-5 border-b border-[var(--border-subtle)] bg-[var(--bg-card)] flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold text-[var(--text-primary)]">
                    {selectedDetail?.name ?? 'Loading adapter...'}
                  </h3>
                  {selectedDetail && (
                    <span className="px-2 py-0.5 rounded-xs text-xs font-mono font-medium border border-[var(--border-subtle)] bg-[var(--bg-subtle)] text-[var(--text-secondary)]">
                      {selectedDetail.connection_mode}
                    </span>
                  )}
                </div>
                <div className="text-xs font-mono text-[var(--text-muted)] mt-0.5">
                  ID: {selectedIntegrationId} • Provider: {selectedDetail?.provider_type}
                </div>
              </div>

              <button
                onClick={() => setSelectedIntegrationId(null)}
                className="p-1.5 rounded-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface)] border border-transparent hover:border-[var(--border-subtle)] transition-colors cursor-pointer"
                aria-label="Close detail drawer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drawer Body */}
            {isDetailLoading || !selectedDetail ? (
              <div className="p-8 text-center text-xs text-[var(--text-muted)] animate-pulse flex-1">
                Loading complete adapter specification...
              </div>
            ) : (
              <div className="p-5 space-y-6 flex-1 text-xs">
                {/* 1. Architectural Overview */}
                <div className="space-y-2">
                  <h4 className="font-bold text-[var(--text-primary)] uppercase font-mono tracking-wider text-xs flex items-center gap-1.5">
                    <Info className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                    Adapter Overview
                  </h4>
                  <p className="text-[var(--text-muted)] leading-relaxed bg-[var(--bg-card)] p-3 rounded-xs border border-[var(--border-subtle)]">
                    {selectedDetail.description}
                  </p>
                </div>

                {/* Connectivity & Sandbox Mode Notice */}
                <div className="p-3 rounded-xs bg-[var(--bg-canvas)] border border-[var(--border-subtle)] flex items-center justify-between text-xs">
                  <span className="text-[var(--text-muted)] font-mono text-xs">External Connectivity:</span>
                  <span className="font-mono text-xs font-medium text-[var(--text-primary)]">
                    {selectedDetail.external_connectivity || "NOT_CONNECTED (LOCAL SIMULATION / REFERENCE ONLY)"}
                  </span>
                </div>

                {/* 2. Operational Boundary Enforcement */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="font-bold text-[var(--text-primary)] uppercase font-mono tracking-wider text-xs flex items-center gap-1.5">
                      <Lock className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                      Read-Only Boundary Enforcement
                    </h4>
                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-bold bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                      ENFORCED (IMMUTABLE)
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="p-3 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] space-y-1.5">
                      <span className="font-mono text-xs font-bold text-[var(--text-primary)] uppercase">
                        Permitted Operations (Inbound Only)
                      </span>
                      <div className="flex flex-wrap gap-1">
                        {selectedDetail.supported_operations.map((op) => (
                          <span
                            key={op}
                            className="px-1.5 py-0.5 rounded text-xs font-mono bg-[var(--bg-subtle)] text-[var(--text-secondary)] border border-[var(--border-subtle)]"
                          >
                            ✓ {op}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="p-3 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] space-y-1.5">
                      <span className="font-mono text-xs font-bold text-[var(--text-primary)] uppercase">
                        Forbidden Operations (Mutations Barred)
                      </span>
                      <div className="flex flex-wrap gap-1">
                        {selectedDetail.forbidden_operations.map((op) => (
                          <span
                            key={op}
                            className="px-1.5 py-0.5 rounded text-xs font-mono bg-[var(--bg-subtle)] text-[var(--text-muted)] border border-[var(--border-subtle)] line-through"
                          >
                            ✕ {op}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                {/* 3. Authentication & Security Model (Zero Secrets Guarantee) */}
                <div className="space-y-2">
                  <h4 className="font-bold text-[var(--text-primary)] uppercase font-mono tracking-wider text-xs flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                    Authentication & Redaction Boundary
                  </h4>
                  <div className="p-3 rounded-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] space-y-1">
                    <div className="font-semibold text-[var(--text-primary)]">
                      {selectedDetail.authentication_model}
                    </div>
                    <p className="text-[var(--text-muted)] text-xs">
                      Zero real credentials or private keys are stored, consumed, or transmitted across API endpoints.
                      All outbound authorization headers are validated against local reference schemes.
                    </p>
                  </div>
                </div>

                {/* 4. Sanitized Configuration Parameters */}
                <div className="space-y-2">
                  <h4 className="font-bold text-[var(--text-primary)] uppercase font-mono tracking-wider text-xs flex items-center gap-1.5">
                    <Server className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                    Sanitized Configuration Parameters
                  </h4>
                  <div className="border border-[var(--border-subtle)] rounded-xs overflow-hidden">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-[var(--bg-canvas)] text-[var(--text-muted)] border-b border-[var(--border-subtle)] uppercase text-xs">
                        <tr>
                          <th className="px-3 py-2">Parameter</th>
                          <th className="px-3 py-2">Type</th>
                          <th className="px-3 py-2">Description</th>
                          <th className="px-3 py-2">Sanitized Value</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border-subtle)]">
                        {selectedDetail.required_config_fields.map((field) => (
                          <tr key={field.name} className="hover:bg-[var(--bg-card)]">
                            <td className="px-3 py-2 font-mono font-bold text-[var(--text-primary)]">
                              {field.name}
                            </td>
                            <td className="px-3 py-2 font-mono text-[var(--text-muted)]">
                              {field.field_type}
                            </td>
                            <td className="px-3 py-2 text-[var(--text-muted)]">
                              {field.description}
                            </td>
                            <td className="px-3 py-2 font-mono text-[var(--text-primary)]">
                              {field.sanitized_value}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* 5. Health & Diagnostic State */}
                <div className="space-y-2">
                  <h4 className="font-bold text-[var(--text-primary)] uppercase font-mono tracking-wider text-xs flex items-center gap-1.5">
                    <Activity className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                    Health Telemetry & Heartbeat
                  </h4>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 bg-[var(--bg-card)] p-3 rounded-xs border border-[var(--border-subtle)] text-xs">
                    <div>
                      <span className="text-[var(--text-muted)] block text-xs">State</span>
                      <span className="font-mono font-bold text-[var(--text-primary)] flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                        {selectedDetail.health.state}
                      </span>
                    </div>
                    <div>
                      <span className="text-[var(--text-muted)] block text-xs">Failures</span>
                      <span className="font-mono font-bold text-[var(--text-primary)]">
                        {selectedDetail.health.consecutive_failures}
                      </span>
                    </div>
                    <div>
                      <span className="text-[var(--text-muted)] block text-xs">Last Heartbeat</span>
                      <span className="font-mono text-[var(--text-muted)]">
                        {selectedDetail.health.last_heartbeat
                          ? new Date(selectedDetail.health.last_heartbeat).toLocaleTimeString()
                          : 'N/A'}
                      </span>
                    </div>
                    <div>
                      <span className="text-[var(--text-muted)] block text-xs">Last Ingested</span>
                      <span className="font-mono text-[var(--text-muted)]">
                        {selectedDetail.health.last_successful_ingestion
                          ? new Date(selectedDetail.health.last_successful_ingestion).toLocaleTimeString()
                          : 'None'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* 6. Known Telecom Limitations */}
                <div className="space-y-2">
                  <h4 className="font-bold text-[var(--text-primary)] uppercase font-mono tracking-wider text-xs flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                    Telecom Portfolio Scope & Boundaries
                  </h4>
                  <ul className="list-disc list-inside space-y-1 bg-[var(--bg-card)] p-3 rounded-xs border border-[var(--border-subtle)] text-[var(--text-muted)] text-xs">
                    {selectedDetail.known_limitations.map((lim, idx) => (
                      <li key={idx}>{lim}</li>
                    ))}
                  </ul>
                </div>

                {/* 7. Provenance Authority */}
                <div className="p-3 rounded-xs bg-[var(--bg-canvas)] border border-[var(--border-subtle)] flex items-center justify-between text-xs">
                  <div>
                    <span className="font-mono text-[var(--text-muted)] block text-xs">
                      CONTRACT SPECIFICATION AUTHORITY
                    </span>
                    <span className="font-bold text-[var(--text-primary)]">
                      {String(selectedDetail.provenance_info?.source_authority ?? 'PIIS Ingestion Contract')}
                    </span>
                  </div>
                  <EpistemicBadge
                    category={String(selectedDetail.provenance_info?.epistemic_classification ?? 'REFERENCE_DATA')}
                    size="sm"
                  />
                </div>
              </div>
            )}

            {/* Drawer Footer */}
            <div className="p-4 border-t border-[var(--border-subtle)] bg-[var(--bg-card)] flex items-center justify-between">
              <span className="text-xs text-[var(--text-muted)] font-mono">
                PIIS Telecommunications Gateway v1.0
              </span>
              <button
                onClick={() => setSelectedIntegrationId(null)}
                className="px-3 py-1.5 rounded text-xs font-medium bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] transition-colors cursor-pointer"
              >
                Close Specification
              </button>
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          DLQ RAW PAYLOAD INSPECTOR MODAL
         ===================================================================== */}
      {inspectedDlqItem && (
        <div className="fixed inset-0 z-50 overflow-hidden flex items-center justify-center bg-black/70 backdrop-blur-xs p-4 animate-in fade-in">
          <div className="w-full max-w-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-xs shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
            <div className="p-4 border-b border-[var(--border-subtle)] bg-[var(--bg-card)] flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-bold text-[var(--text-primary)]">
                    Quarantined Ingestion Envelope
                  </h4>
                  <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-bold bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                    SERVER-REDACTED
                  </span>
                  <span className="px-2 py-0.5 rounded text-xs font-mono bg-[var(--bg-subtle)] text-[var(--text-muted)] border border-[var(--border-subtle)]">
                    {inspectedDlqItem.payload_size_bytes ?? 0} bytes
                  </span>
                </div>
                <span className="text-xs font-mono text-[var(--text-muted)] mt-0.5 block">
                  Item ID: {inspectedDlqItem.item_id}
                </span>
              </div>
              <button
                onClick={() => setInspectedDlqItem(null)}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-4 space-y-3 overflow-y-auto flex-1 text-xs">
              <div className="p-2.5 rounded bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-primary)]">
                <span className="font-bold block text-xs font-mono uppercase text-[var(--text-secondary)]">Rejection Reason:</span>
                <span>{inspectedDlqItem.failure_reason}</span>
              </div>

              <div>
                <span className="text-xs font-mono text-[var(--text-muted)] block mb-1">
                  Raw Envelope Payload:
                </span>
                <pre className="p-3 rounded bg-[var(--bg-canvas)] border border-[var(--border-subtle)] font-mono text-xs text-[var(--text-primary)] overflow-x-auto max-h-64">
                  {JSON.stringify(inspectedDlqItem.raw_payload ?? {}, null, 2)}
                </pre>
              </div>
            </div>

            <div className="p-3 border-t border-[var(--border-subtle)] bg-[var(--bg-card)] flex items-center justify-end">
              <button
                onClick={() => setInspectedDlqItem(null)}
                className="px-3 py-1.5 rounded text-xs font-medium bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] border border-[var(--border-subtle)] text-[var(--text-primary)] cursor-pointer"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
