import { useQuery, useMutation, useQueryClient, type UseQueryResult } from '@tanstack/react-query'
import { apiClient } from './client'
import { API_ENDPOINTS } from './endpoints'
import type {
  HealthResponse,
  ReadyResponse,
  IncidentListResponse,
  IncidentDetailResponse,
  IntegrationsHealthResponse,
  AuditVerifyResponse,
  InvestigationResponse,
  InvestigationEvidenceItem,
  IncidentHypothesisItem,
  DiagnosticRecommendationItem,
  NetworkOverviewResponse,
  NetworkTopologyResponse,
  NetworkElementDetailResponse,
  NetworkImpactResponse,
  NetworkAlarmsResponse,
  NetworkTelemetryResponse,
} from './types'

export interface IncidentQueryParams {
  limit?: number
  offset?: number
  domain?: string
  severity?: string
  refetchInterval?: number
}

/**
 * Shared Incident List Query.
 * Avoids duplicate network calls across Command Center and Incident Explorer.
 */
export function useIncidentsQuery(
  params: IncidentQueryParams = {}
): UseQueryResult<IncidentListResponse, Error> {
  const { limit = 50, offset = 0, domain, severity, refetchInterval } = params

  const queryParams = new URLSearchParams()
  queryParams.set('limit', String(limit))
  queryParams.set('offset', String(offset))
  if (domain && domain !== 'ALL') {
    queryParams.set('domain', domain)
  }
  if (severity && severity !== 'ALL') {
    queryParams.set('severity', severity)
  }

  const endpoint = `${API_ENDPOINTS.INCIDENTS}?${queryParams.toString()}`

  return useQuery<IncidentListResponse, Error>({
    queryKey: ['incidents', { limit, offset, domain, severity }],
    queryFn: () => apiClient.get<IncidentListResponse>(endpoint),
    staleTime: 15_000,
    refetchInterval,
  })
}

/**
 * Single Incident Detail Query with lineage.
 */
export function useIncidentDetailQuery(
  incidentId: string | null
): UseQueryResult<IncidentDetailResponse, Error> {
  return useQuery<IncidentDetailResponse, Error>({
    queryKey: ['incident-detail', incidentId],
    queryFn: () => {
      if (!incidentId) throw new Error('Incident ID is required')
      return apiClient.get<IncidentDetailResponse>(API_ENDPOINTS.INCIDENT_GET(incidentId))
    },
    enabled: Boolean(incidentId),
    staleTime: 30_000,
  })
}

/**
 * Kubernetes Liveness Probe Query.
 */
export function useSystemHealthQuery(): UseQueryResult<HealthResponse, Error> {
  return useQuery<HealthResponse, Error>({
    queryKey: ['system-health'],
    queryFn: () => apiClient.get<HealthResponse>(API_ENDPOINTS.HEALTH),
    staleTime: 10_000,
    refetchInterval: 15_000,
  })
}

/**
 * Kubernetes Readiness Probe Query.
 */
export function useSystemReadyQuery(): UseQueryResult<ReadyResponse, Error> {
  return useQuery<ReadyResponse, Error>({
    queryKey: ['system-ready'],
    queryFn: () => apiClient.get<ReadyResponse>(API_ENDPOINTS.READY),
    staleTime: 10_000,
    refetchInterval: 15_000,
  })
}

/**
 * Adapter Matrix Health Query.
 */
export function useAdaptersHealthQuery(): UseQueryResult<IntegrationsHealthResponse, Error> {
  return useQuery<IntegrationsHealthResponse, Error>({
    queryKey: ['adapters-health'],
    queryFn: () => apiClient.get<IntegrationsHealthResponse>(API_ENDPOINTS.INTEGRATIONS_HEALTH),
    staleTime: 15_000,
    refetchInterval: 30_000,
  })
}

/**
 * Cryptographic Audit Hash-Chain Verification Query.
 */
export function useAuditVerifyQuery(): UseQueryResult<AuditVerifyResponse, Error> {
  return useQuery<AuditVerifyResponse, Error>({
    queryKey: ['audit-verify'],
    queryFn: () => apiClient.get<AuditVerifyResponse>(API_ENDPOINTS.AUDIT_VERIFY),
    staleTime: 30_000,
  })
}

/**
 * Top-Level Investigation Context Query.
 * Retrieves full investigation report including sufficiency, staleness, and recommendations.
 */
export function useInvestigationQuery(
  incidentId: string | null
): UseQueryResult<InvestigationResponse, Error> {
  return useQuery<InvestigationResponse, Error>({
    queryKey: ['investigation', incidentId],
    queryFn: async () => {
      if (!incidentId) throw new Error('Incident ID is required for investigation')
      return apiClient.get<InvestigationResponse>(
        API_ENDPOINTS.INCIDENT_INVESTIGATION_GET(incidentId)
      )
    },
    enabled: Boolean(incidentId),
    staleTime: 20_000,
  })
}

/**
 * Correlated Evidence Register Query.
 */
export function useInvestigationEvidenceQuery(
  incidentId: string | null
): UseQueryResult<InvestigationEvidenceItem[], Error> {
  return useQuery<InvestigationEvidenceItem[], Error>({
    queryKey: ['investigation-evidence', incidentId],
    queryFn: () => {
      if (!incidentId) throw new Error('Incident ID is required')
      return apiClient.get<InvestigationEvidenceItem[]>(
        API_ENDPOINTS.INCIDENT_EVIDENCE(incidentId)
      )
    },
    enabled: Boolean(incidentId),
    staleTime: 30_000,
  })
}

/**
 * Ranked Hypotheses Query.
 */
export function useInvestigationHypothesesQuery(
  incidentId: string | null
): UseQueryResult<IncidentHypothesisItem[], Error> {
  return useQuery<IncidentHypothesisItem[], Error>({
    queryKey: ['investigation-hypotheses', incidentId],
    queryFn: async () => {
      if (!incidentId) throw new Error('Incident ID is required')
      return apiClient.get<IncidentHypothesisItem[]>(
        API_ENDPOINTS.INCIDENT_HYPOTHESES(incidentId)
      )
    },
    enabled: Boolean(incidentId),
    staleTime: 30_000,
  })
}

/**
 * Diagnostic Recommendations Query.
 */
export function useInvestigationRecommendationsQuery(
  incidentId: string | null
): UseQueryResult<DiagnosticRecommendationItem[], Error> {
  return useQuery<DiagnosticRecommendationItem[], Error>({
    queryKey: ['investigation-recommendations', incidentId],
    queryFn: () => {
      if (!incidentId) throw new Error('Incident ID is required')
      return apiClient.get<DiagnosticRecommendationItem[]>(
        API_ENDPOINTS.INCIDENT_RECOMMENDATIONS(incidentId)
      )
    },
    enabled: Boolean(incidentId),
    staleTime: 20_000,
  })
}

/**
 * Trigger Investigation Mutation.
 * Explicitly triggers POST /api/v1/incidents/{incidentId}/investigate.
 * Preserves strict read-only semantics for GET requests by requiring
 * deliberate operator invocation for initial diagnostic generation.
 */
export function useTriggerInvestigationMutation() {
  const queryClient = useQueryClient()
  return useMutation<InvestigationResponse, Error, string>({
    mutationFn: (incidentId: string) => {
      return apiClient.post<InvestigationResponse>(
        API_ENDPOINTS.INCIDENT_INVESTIGATE(incidentId)
      )
    },
    onSuccess: (_, incidentId) => {
      queryClient.invalidateQueries({ queryKey: ['investigation', incidentId] })
      queryClient.invalidateQueries({ queryKey: ['investigation-evidence', incidentId] })
      queryClient.invalidateQueries({ queryKey: ['investigation-hypotheses', incidentId] })
      queryClient.invalidateQueries({ queryKey: ['investigation-recommendations', incidentId] })
    },
  })
}

// --- UI-4 Network Intelligence Queries ---

/**
 * Network Observability Overview Query.
 */
export function useNetworkOverviewQuery(
  refetchInterval?: number
): UseQueryResult<NetworkOverviewResponse, Error> {
  return useQuery<NetworkOverviewResponse, Error>({
    queryKey: ['network-overview'],
    queryFn: () => apiClient.get<NetworkOverviewResponse>(API_ENDPOINTS.NETWORK_OVERVIEW),
    staleTime: 10_000,
    refetchInterval,
  })
}

/**
 * Network Topology Graph Query.
 */
export function useNetworkTopologyQuery(
  domain?: string
): UseQueryResult<NetworkTopologyResponse, Error> {
  const endpoint = domain && domain !== 'ALL'
    ? `${API_ENDPOINTS.NETWORK_TOPOLOGY}?domain=${encodeURIComponent(domain)}`
    : API_ENDPOINTS.NETWORK_TOPOLOGY

  return useQuery<NetworkTopologyResponse, Error>({
    queryKey: ['network-topology', domain],
    queryFn: () => apiClient.get<NetworkTopologyResponse>(endpoint),
    staleTime: 30_000,
  })
}

/**
 * Single Network Element Detail Query.
 */
export function useNetworkElementDetailQuery(
  elementId: string | null
): UseQueryResult<NetworkElementDetailResponse, Error> {
  return useQuery<NetworkElementDetailResponse, Error>({
    queryKey: ['network-element', elementId],
    queryFn: () => {
      if (!elementId) throw new Error('Element ID is required')
      return apiClient.get<NetworkElementDetailResponse>(
        API_ENDPOINTS.NETWORK_ELEMENT_GET(elementId)
      )
    },
    enabled: Boolean(elementId),
    staleTime: 15_000,
  })
}

/**
 * Network Blast Radius & Impact Query.
 */
export function useNetworkImpactQuery(
  params: { element_id?: string; incident_id?: string },
  enabled = true
): UseQueryResult<NetworkImpactResponse, Error> {
  const { element_id, incident_id } = params
  const searchParams = new URLSearchParams()
  if (element_id) searchParams.set('element_id', element_id)
  if (incident_id) searchParams.set('incident_id', incident_id)

  const endpoint = `${API_ENDPOINTS.NETWORK_IMPACT}?${searchParams.toString()}`

  return useQuery<NetworkImpactResponse, Error>({
    queryKey: ['network-impact', { element_id, incident_id }],
    queryFn: () => apiClient.get<NetworkImpactResponse>(endpoint),
    enabled: enabled && Boolean(element_id || incident_id),
    staleTime: 30_000,
  })
}

/**
 * Active Alarms & Correlation Clusters Query.
 */
export function useNetworkAlarmsQuery(
  params: { element_id?: string; domain?: string; severity?: string } = {}
): UseQueryResult<NetworkAlarmsResponse, Error> {
  const { element_id, domain, severity } = params
  const searchParams = new URLSearchParams()
  if (element_id) searchParams.set('element_id', element_id)
  if (domain && domain !== 'ALL') searchParams.set('domain', domain)
  if (severity && severity !== 'ALL') searchParams.set('severity', severity)

  const queryStr = searchParams.toString()
  const endpoint = queryStr ? `${API_ENDPOINTS.NETWORK_ALARMS}?${queryStr}` : API_ENDPOINTS.NETWORK_ALARMS

  return useQuery<NetworkAlarmsResponse, Error>({
    queryKey: ['network-alarms', { element_id, domain, severity }],
    queryFn: () => apiClient.get<NetworkAlarmsResponse>(endpoint),
    staleTime: 10_000,
  })
}

/**
 * Network Element Telemetry Time-Series & Anomaly Stream Query.
 */
export function useNetworkTelemetryQuery(
  params: { element_id: string | null; metric_name?: string }
): UseQueryResult<NetworkTelemetryResponse, Error> {
  const { element_id, metric_name } = params
  const searchParams = new URLSearchParams()
  if (element_id) searchParams.set('element_id', element_id)
  if (metric_name) searchParams.set('metric_name', metric_name)

  const endpoint = `${API_ENDPOINTS.NETWORK_TELEMETRY}?${searchParams.toString()}`

  return useQuery<NetworkTelemetryResponse, Error>({
    queryKey: ['network-telemetry', { element_id, metric_name }],
    queryFn: () => {
      if (!element_id) throw new Error('Element ID is required')
      return apiClient.get<NetworkTelemetryResponse>(endpoint)
    },
    enabled: Boolean(element_id),
    staleTime: 10_000,
  })
}
