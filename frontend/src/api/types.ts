/**
 * TypeScript Data Contracts mirroring Pydantic Schemas from src/piis/api/schemas.py
 * and schemas/incident.schema.json.
 */

export interface PaginatedResponse<T> {
  items: T[]
  total_count: number
  limit: number
  offset: number
}

export interface ApiErrorResponse {
  error: string
  detail: string
  code?: string
  correlation_id?: string
  timestamp?: string
}

export interface SystemHealthResponse {
  status: string
  service: string
  mode: string
}
export type HealthResponse = SystemHealthResponse

export interface SystemReadinessResponse {
  status: 'ready' | 'degraded' | string
  registered_adapters_count: number
  degraded_adapters: string[]
  incidents_count: number
  dead_letter_count: number
  audit_ledger_records: number
}
export type ReadyResponse = SystemReadinessResponse

export type NetworkDomain = 'RAN' | '5G_CORE' | 'TRANSPORT' | 'SERVICE' | 'CROSS_DOMAIN' | 'UNKNOWN'
export type IncidentSeverity = 'CRITICAL' | 'MAJOR' | 'MINOR' | 'WARNING' | 'UNKNOWN'
export type SupportLevelLabel = 'L1' | 'L2' | 'L3' | 'HUMAN_REVIEW' | 'UNLABELED'
export type SourceType = 'PUBLIC_REAL' | 'SYNTHETIC' | 'DERIVED' | 'HUMAN_ANNOTATED' | 'OPERATOR_INTERNAL'

export interface CanonicalIncidentItem {
  incident_id: string
  title: string | null
  description: string
  network_domain: NetworkDomain | string
  fault_category?: string | null
  severity: IncidentSeverity | string
  support_level_label?: SupportLevelLabel | string
  support_level_rationale?: string | null
  affected_region?: string | null
  affected_subscribers?: number | null
  network_element_ids?: string[]
  created_at: string
  resolved_at?: string | null
  resolution_summary?: string | null
  root_cause_confirmed?: boolean
  source_type: SourceType | string
  source_dataset?: string | null
  source_record_id?: string | null
  scenario_family_id?: string | null
  split_group_id?: string | null
  annotation_status?: string
  metadata?: Record<string, unknown>
  // Optional convenience fields if provided by adapter or query
  source_system?: string
  state?: string
}

export type IncidentListResponse = PaginatedResponse<CanonicalIncidentItem>

export interface IncidentDetailResponse {
  incident: CanonicalIncidentItem
  lineage?: {
    canonical_id?: string
    envelope_id?: string
    source_system?: string
    source_type?: string
    external_event_id?: string
    observation_timestamp?: string
    ingested_at?: string
    raw_payload_checksum?: string
    [key: string]: unknown
  } | null
}

export type RiskClassification = 'READ_ONLY_SAFE' | 'LOW_OBSERVABILITY' | 'DISRUPTIVE_AUDIT' | 'HIGH_RISK_MANUAL' | string
export type ApprovalStatus = 'PENDING_REVIEW' | 'APPROVED' | 'REJECTED' | 'MODIFIED' | string
export type HypothesisStatus = 'UNVERIFIED' | 'SUPPORTED' | 'REJECTED' | 'INCONCLUSIVE' | string
export type EvidenceType =
  | 'TICKET_METADATA'
  | 'ML_CLASSIFICATION'
  | 'SEVERITY_PREDICTION'
  | 'POLICY_ROUTING'
  | 'TELEMETRY_ANOMALY'
  | 'ALARM_CLUSTER'
  | 'TOPOLOGY_IMPACT'
  | 'APPROVED_RUNBOOK'
  | 'HISTORICAL_CASE'
  | string

export type TrustLevel =
  | 'HIGH_TRUST_APPROVED'
  | 'MEDIUM_TRUST_VERIFIED'
  | 'BENCHMARK_ONLY'
  | 'UNVERIFIED'
  | string

export interface DiagnosticRecommendationItem {
  recommendation_id: string
  incident_id?: string | null
  description: string
  reason: string
  supporting_evidence_ids: string[]
  source_runbook_id: string
  source_section?: string | null
  risk_classification: RiskClassification
  human_approval_required: boolean
  approval_status: ApprovalStatus
  reviewed_by?: string | null
  review_timestamp?: string | null
  review_notes?: string | null
}

export interface ReviewQueueItem {
  recommendation_id: string
  incident_id: string
  incident_title?: string | null
  incident_severity: IncidentSeverity | string
  network_domain: NetworkDomain | string
  description: string
  reason: string
  supporting_evidence_ids: string[]
  source_runbook_id: string
  source_section?: string | null
  risk_classification: RiskClassification
  human_approval_required: boolean
  approval_status: ApprovalStatus
  reviewed_by?: string | null
  review_timestamp?: string | null
  review_notes?: string | null
  is_sufficient: boolean
  has_contradictions: boolean
  has_missing_evidence: boolean
  created_at?: string | null
}

export interface ReviewQueueResponse {
  items: ReviewQueueItem[]
  total_count: number
  pending_count: number
  approved_count: number
  rejected_count: number
  limit: number
  offset: number
}

export interface ReviewHistoryItem {
  audit_id: string
  sequence_number: number
  incident_id: string
  recommendation_id: string
  action: string
  previous_status: string
  new_status: string
  operator_id: string
  reviewer_role: string
  timestamp_utc: string
  notes?: string | null
  entry_sha256: string
  hmac_signature?: string | null
}

export interface ReviewSubmissionRequest {
  recommendation_id: string
  decision: 'APPROVED' | 'REJECTED' | string
  review_notes: string
}

export interface ReviewResponse {
  incident_id: string
  recommendation_id: string
  decision: string
  reviewed_by: string
  review_timestamp: string
  audit_entry_hash: string
  ledger_sequence: number
  status: string
  receipt_id: string
}

export interface IncidentHypothesisItem {
  hypothesis_id: string
  description: string
  supporting_evidence_ids: string[]
  contradicting_evidence_ids: string[]
  evidence_source: string
  evidence_timestamp?: string | null
  confidence_proxy: number
  confidence_rationale: string
  alternative_explanations?: string[]
  recommended_verification_steps?: string[]
  status: HypothesisStatus
}

export interface InvestigationEvidenceItem {
  evidence_id: string
  evidence_type: EvidenceType
  source_ref: string
  domain: string
  observed_at?: string | null
  trust_classification: TrustLevel
  content_summary: string
  raw_metadata?: Record<string, unknown>
}

export interface InvestigationResponse {
  incident_id: string
  title: string
  network_domain: string
  created_at: string
  is_sufficient: boolean
  missing_evidence: string[]
  contradictions: string[]
  stale_evidence: string[]
  is_transient_event: boolean
  hypotheses_count: number
  hypotheses?: IncidentHypothesisItem[]
  recommendations: DiagnosticRecommendationItem[]
  epistemic_status: string
  correlation_id: string
}

export interface AdapterHealthItem {
  adapter_id: string
  adapter_type: string
  state: 'HEALTHY' | 'DEGRADED' | 'FAILED' | 'UNAVAILABLE' | string
  last_heartbeat: string
  last_successful_ingestion?: string | null
  consecutive_failures: number
  error_message?: string | null
}
export type IntegrationsHealthResponse = AdapterHealthItem[]

export interface AuditRecordItem {
  sequence_number: number
  entry_hash: string
  prev_hash: string
  operator_id: string
  decision: string
  recommendation_id: string
  timestamp: string
  schema_version: string
  has_hmac: boolean

  // UI-6 Extended fields
  audit_id?: string
  action?: string
  previous_status?: string | null
  new_status?: string | null
  incident_id?: string | null
  reviewer_role?: string | null
  authorization_scope?: string | null
  principal_type?: string | null
  reviewer_auth_hash?: string | null
  key_id?: string | null
  hmac_signature?: string | null
  notes?: string | null
  notes_cryptographically_covered?: boolean | null
  recommendation_content_hash?: string | null
  state_sha256?: string | null
  verification_status?: string
}

export interface AuditRecordDetailResponse {
  record: AuditRecordItem
  canonical_json: string
  canonical_hash_matches: boolean
  recomputed_hash: string
  hmac_valid: boolean
  is_genesis: boolean
  checkpoint_aligned: boolean
  provenance_chain: {
    incident_id?: string | null
    recommendation_id?: string | null
    has_stored_recommendation: boolean
    operator_id: string
    reviewer_role?: string | null
    action: string
    timestamp_utc: string
    schema_version: string
    key_id?: string | null
  }
}

export interface AuditVerificationResponse {
  is_valid: boolean
  verification_status: 'VERIFIED' | 'FAILED' | 'INCOMPLETE' | 'UNAVAILABLE' | string
  total_records: number
  records_checked: number
  first_sequence?: number | null
  last_sequence?: number | null
  latest_sequence: number
  latest_hash: string | null
  hash_chain_valid: boolean
  jcs_canonicalization_valid: boolean
  hmac_signatures_valid: boolean
  checkpoint_parity_valid: boolean
  anchor_present: boolean
  anchor_sequence?: number | null
  anchor_hash?: string | null
  error?: string | null
  errors: string[]
  verified_at: string
  verification_scope: string
  limitations: string[]
}
export type AuditVerifyResponse = AuditVerificationResponse

export interface AuditSummaryResponse {
  total_records: number
  latest_sequence: number
  earliest_timestamp?: string | null
  latest_timestamp?: string | null
  actions_breakdown: Record<string, number>
  anchor_present: boolean
  anchor_sequence?: number | null
  anchor_hash?: string | null
  storage_type: string
  canonicalization_scheme: string
  hashing_algorithm: string
  mac_algorithm: string
  anchor_mechanism: string
  limitations: string[]
}

// --- UI-4 Network Intelligence Types ---

export interface NetworkOverviewResponse {
  total_elements: number
  elements_by_domain: Record<string, number>
  total_links: number
  active_alarms_count: number
  correlated_clusters_count: number
  active_anomalies_count: number
  last_sync_timestamp: string
  topology_version: string
  epistemic_status: string
  provenance: Record<string, unknown>
}

export interface NetworkNodeItem {
  element_id: string
  domain: string
  element_type: string
  site_id?: string | null
  nominal_subscribers?: number | null
  active_alarm_count: number
  has_anomaly: boolean
  epistemic_status: string
}

export interface NetworkLinkItem {
  source: string
  target: string
  relation: string
  is_dependency: boolean
  direction: 'bidirectional' | 'downstream' | string
}

export interface NetworkTopologyResponse {
  nodes: NetworkNodeItem[]
  links: NetworkLinkItem[]
  epistemic_status: string
}

export interface NetworkElementDetailResponse {
  element_id: string
  domain: string
  element_type: string
  site_id?: string | null
  nominal_subscribers?: number | null
  neighbors: string[]
  upstream_parents: string[]
  downstream_children: string[]
  active_alarms: Array<Record<string, unknown>>
  recent_telemetry_count: number
  epistemic_status: string
}

export interface NetworkImpactResponse {
  target_element?: string | null
  direct_elements: string[]
  inferred_elements: string[]
  total_element_count: number
  affected_domains: string[]
  severity_risk_level: string
  risk_score: number
  estimated_affected_subscribers?: number | null
  subscriber_impact_basis?: string | null
  epistemic_status: string
  provenance: Record<string, unknown>
}

export interface NetworkAlarmItem {
  alarm_id: string
  network_element_id: string
  network_domain: string
  alarm_code: string
  probable_cause?: string | null
  severity: string
  timestamp: string
  cluster_id?: string | null
  epistemic_status: string
}

export interface NetworkAlarmClusterItem {
  cluster_id: string
  dominant_domain: string
  event_count: number
  affected_elements: string[]
  mean_confidence: number
  rationales: string[]
  epistemic_status: string
}

export interface NetworkAlarmsResponse {
  alarms: NetworkAlarmItem[]
  clusters: NetworkAlarmClusterItem[]
  total_alarms: number
  total_clusters: number
}

export interface TelemetrySeriesItem {
  metric_name: string
  unit: string
  timestamps: string[]
  values: number[]
  is_imputed: boolean[]
}

export interface TelemetryAnomalyItem {
  anomaly_id: string
  metric_name: string
  timestamp: string
  observed_value: number
  expected_value?: number | null
  threshold_value?: number | null
  severity: string
  score: number
  epistemic_status: string
}

export interface NetworkTelemetryResponse {
  element_id: string
  series: TelemetrySeriesItem[]
  anomalies: TelemetryAnomalyItem[]
  epistemic_status: string
}

// ---------------------------------------------------------------------------
// UI-7 Integrations Workspace Contracts
// ---------------------------------------------------------------------------

export interface IntegrationConfigField {
  name: string
  field_type: string
  description: string
  sanitized_value: string
  is_secret?: boolean
}

export interface IntegrationRegistryItem {
  integration_id: string
  name: string
  category: string
  provider_type: string
  adapter_class: string
  connection_mode: string
  operational_status: 'AVAILABLE' | 'DEGRADED' | 'UNAVAILABLE' | string
  status_label: string
  capabilities: string[]
  data_direction: string
  rate_limit_rps: number
  last_heartbeat: string
  last_successful_ingestion?: string | null
  consecutive_failures: number
  error_message?: string | null
  external_connectivity?: string
  health_freshness?: string
}

export interface IntegrationSummaryResponse {
  total_adapters: number
  available_count: number
  degraded_count: number
  unavailable_count: number
  simulated_count: number
  reference_count: number
  last_health_check?: string | null
  overall_readiness: 'OPERATIONAL' | 'DEGRADED' | string
  total_dlq_count: number
  total_ingested_events: number
  categories_breakdown: Record<string, number>
  epistemic_status: string
  external_connectivity?: string
  readiness_qualification?: string
}

export interface IntegrationDetailResponse {
  integration_id: string
  name: string
  description: string
  category: string
  provider_type: string
  adapter_class: string
  connection_mode: string
  operational_status: string
  status_label: string
  capabilities: string[]
  data_direction: string
  supported_operations: string[]
  forbidden_operations: string[]
  read_only_boundary_enforced: boolean
  authentication_model: string
  required_config_fields: IntegrationConfigField[]
  health: AdapterHealth
  recent_activity: Record<string, unknown>[]
  known_limitations: string[]
  provenance_info: Record<string, unknown>
  external_connectivity?: string
}

export interface DeadLetterItem {
  item_id: string
  envelope_id: string
  source_system: string
  failure_reason: string
  error_details: string
  attempt_count: number
  first_failed_at: string
  last_failed_at: string
  raw_payload: Record<string, unknown>
  is_redacted?: boolean
  payload_size_bytes?: number
  epistemic_classification?: string
}

export interface IntegrationActivityItem {
  event_id: string
  timestamp: string
  adapter_id: string
  source_system: string
  event_type: string
  status: string
  details: string
  canonical_id?: string | null
  envelope_id?: string | null
  epistemic_tag: string
}

export interface DataFlowStageItem {
  stage_id: string
  title: string
  subtitle: string
  status: string
  epistemic_badge: string
  description: string
  is_simulated: boolean
  order: number
  active_count: number
}

export interface DataFlowEdgeItem {
  source: string
  target: string
  label: string
}

export interface DataFlowResponse {
  stages: DataFlowStageItem[]
  edges: DataFlowEdgeItem[]
  active_adapters_count: number
  quarantined_items_count: number
  pipeline_health: string
  epistemic_classification: string
}

// ---------------------------------------------------------------------------
// UI-8 System Health & Operations Workspace Contracts
// ---------------------------------------------------------------------------

export type SystemHealthState = 'HEALTHY' | 'DEGRADED' | 'UNAVAILABLE' | 'UNKNOWN'
export type ComponentCriticality = 'CRITICAL' | 'STANDARD' | 'INFORMATIONAL'
export type ObservationFreshness = 'FRESH' | 'STALE' | 'EXPIRED' | 'UNKNOWN' | 'NOT_APPLICABLE'

export interface ComponentHealthItem {
  component_id: string
  name: string
  category: string
  health_state: SystemHealthState | string
  criticality: ComponentCriticality | string
  last_observed_at?: string | null
  freshness: ObservationFreshness | string
  check_source: string
  failure_reason?: string | null
  implementation_nature: 'REAL_LOCAL' | 'SIMULATED' | 'REFERENCE_ONLY' | 'NOT_INSTRUMENTED' | string
  details: Record<string, unknown>
}

export interface SystemHealthOverviewResponse {
  aggregate_status: SystemHealthState | string
  evaluation_policy: string
  last_evaluated_at: string
  healthy_count: number
  degraded_count: number
  unavailable_count: number
  unknown_count: number
  total_components: number
  readiness_status: string
  liveness_status: string
  external_connectivity: string
  epistemic_classification: string
}

export interface IngestionHealthResponse {
  pipeline_status: string
  cumulative_ingested_events: number
  cumulative_stored_incidents: number
  cumulative_stored_alarms: number
  cumulative_stored_telemetry: number
  current_dlq_depth: number
  deduplication_cache_size: number
  registered_adapters_count: number
  last_successful_ingestion?: string | null
  last_failed_ingestion?: string | null
  rate_limit_policy: string
  data_direction: string
}

export interface IntelligenceSubsystemHealthResponse {
  engine_version: string
  investigation_status: string
  bm25_index_status: string
  bm25_total_chunks: number
  dense_index_status: string
  dense_model_name: string
  dense_is_fallback_mode: boolean
  fusion_algorithm: string
  sop_rules_count: number
  anomaly_detection_status: string
  evaluation_mode: string
}

export interface PersistenceAuditHealthResponse {
  audit_ledger_status: string
  ledger_file_accessible: boolean
  ledger_record_count: number
  ledger_head_sequence?: number | null
  checkpoint_anchor_status: string
  checkpoint_sequence?: number | null
  hmac_key_provider_status: string
  disk_fsync_supported: boolean
  last_verification_timestamp?: string | null
  external_trust_anchor_connected: boolean
  trust_anchor_limitation_disclosure: string
}

export interface SystemHealthEventItem {
  event_id: string
  timestamp: string
  component_id: string
  previous_state?: string | null
  new_state: string
  event_type: string
  source: string
  reason?: string | null
  epistemic_tag: string
}

export interface DependencyNodeItem {
  id: string
  name: string
  category: string
  health_state: string
  criticality: string
  is_external: boolean
}

export interface DependencyEdgeItem {
  source: string
  target: string
  relationship_type: string
  label: string
}

export interface SystemDependencyGraphResponse {
  nodes: DependencyNodeItem[]
  edges: DependencyEdgeItem[]
  graph_type: string
  epistemic_classification: string
}

// ---------------------------------------------------------------------------
// UI-9 Settings & Configuration Workspace Contracts
// ---------------------------------------------------------------------------

export interface DocumentationCatalogItem {
  title: string
  path: string
  category: string
  description: string
}

export interface SettingsSystemInfoResponse {
  application_name: string
  application_edition: string
  core_version: string
  api_version: string
  active_milestone: string
  environment: string
  operational_mode: string
  telecom_domains: string[]
  auth_mode: string
  rbac_enforced: boolean
  service_principals_barred: boolean
  retrieval_models: Record<string, string>
  operational_boundaries: Record<string, boolean>
  documentation_catalog: DocumentationCatalogItem[]
  epistemic_classification: string
}

export interface DisplayPreferences {
  theme: 'dark' | 'light' | 'system'
  density: 'comfortable' | 'compact'
  timezone: 'UTC' | 'LOCAL'
  timeFormat: '24H' | '12H'
  pageSize: 10 | 25 | 50
  refreshInterval: 'OFF' | '15s' | '30s' | '60s'
}


