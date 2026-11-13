import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { IntegrationsPage } from '../pages/IntegrationsPage'
import { apiClient } from '../api/client'

const MOCK_SUMMARY = {
  total_adapters: 6,
  available_count: 6,
  degraded_count: 0,
  unavailable_count: 0,
  simulated_count: 4,
  reference_count: 2,
  last_health_check: '2026-11-04T12:00:00Z',
  overall_readiness: 'OPERATIONAL',
  total_dlq_count: 0,
  total_ingested_events: 42,
  categories_breakdown: {
    ITSM: 3,
    TELEMETRY: 2,
    OSS_NMS_ALARM: 1,
  },
  epistemic_status: 'REFERENCE_DATA',
}

const MOCK_REGISTRY = [
  {
    integration_id: 'ITSM-SERVICENOW-01',
    name: 'ServiceNow Incident Connector',
    category: 'ITSM',
    provider_type: 'ServiceNow',
    adapter_class: 'ServiceNowAdapter',
    connection_mode: 'LOCAL SIMULATION',
    operational_status: 'AVAILABLE',
    status_label: 'LOCALLY VERIFIED (SIMULATED)',
    capabilities: ['READ_ONLY_INGEST', 'CANONICAL_NORMALIZATION', 'SCHEMA_VALIDATION'],
    data_direction: 'INBOUND_ONLY',
    rate_limit_rps: 25.0,
    last_heartbeat: '2026-11-04T12:00:00Z',
    last_successful_ingestion: '2026-11-04T11:59:00Z',
    consecutive_failures: 0,
    error_message: null,
  },
  {
    integration_id: 'ITSM-JIRA-01',
    name: 'Jira Service Management Connector',
    category: 'ITSM',
    provider_type: 'Jira Service Management',
    adapter_class: 'JiraServiceManagementAdapter',
    connection_mode: 'LOCAL SIMULATION',
    operational_status: 'AVAILABLE',
    status_label: 'LOCALLY VERIFIED (SIMULATED)',
    capabilities: ['READ_ONLY_INGEST', 'CANONICAL_NORMALIZATION', 'SCHEMA_VALIDATION'],
    data_direction: 'INBOUND_ONLY',
    rate_limit_rps: 20.0,
    last_heartbeat: '2026-11-04T12:00:00Z',
    last_successful_ingestion: null,
    consecutive_failures: 0,
    error_message: null,
  },
  {
    integration_id: 'TELEM-PROM-01',
    name: 'Prometheus KPI Metrics Scraper',
    category: 'TELEMETRY',
    provider_type: 'Prometheus',
    adapter_class: 'PrometheusAdapter',
    connection_mode: 'REFERENCE IMPLEMENTATION',
    operational_status: 'AVAILABLE',
    status_label: 'LOCALLY VERIFIED (REFERENCE)',
    capabilities: ['METRIC_POLLING', 'TIME_SERIES_NORMALIZATION'],
    data_direction: 'INBOUND_ONLY',
    rate_limit_rps: 100.0,
    last_heartbeat: '2026-11-04T12:00:00Z',
    last_successful_ingestion: '2026-11-04T11:58:00Z',
    consecutive_failures: 0,
    error_message: null,
  },
]

const MOCK_DETAIL_SERVICENOW = {
  integration_id: 'ITSM-SERVICENOW-01',
  name: 'ServiceNow Incident Connector',
  description:
    'Bi-directional ingestion gateway translating ServiceNow Table API incident schemas into PIIS canonical records with automated priority mapping and field normalization.',
  category: 'ITSM',
  provider_type: 'ServiceNow',
  adapter_class: 'ServiceNowAdapter',
  connection_mode: 'LOCAL SIMULATION',
  operational_status: 'AVAILABLE',
  status_label: 'LOCALLY VERIFIED (SIMULATED)',
  capabilities: ['READ_ONLY_INGEST', 'CANONICAL_NORMALIZATION', 'SCHEMA_VALIDATION'],
  data_direction: 'INBOUND_ONLY',
  supported_operations: ['HEALTH_CHECK', 'NORMALIZE', 'READ_ONLY_INGEST'],
  forbidden_operations: [
    'ASSIGN_TICKET',
    'CLOSE_TICKET',
    'CREATE_TICKET',
    'EXECUTE_COMMAND',
    'MODIFY_CONFIG',
    'REBOOT_ELEMENT',
    'SEND_COMMUNICATION',
    'UPDATE_TICKET',
  ],
  read_only_boundary_enforced: true,
  authentication_model: 'OAuth 2.0 Bearer Token (Local Reference Token)',
  required_config_fields: [
    {
      name: 'instance_url',
      field_type: 'url',
      description: 'Target ServiceNow telecom enterprise instance URL',
      sanitized_value: 'https://telecom.service-now.com',
      is_secret: false,
    },
    {
      name: 'api_version',
      field_type: 'string',
      description: 'ServiceNow Table API REST specification version',
      sanitized_value: 'v2',
      is_secret: false,
    },
  ],
  health: {
    adapter_id: 'ITSM-SERVICENOW-01',
    adapter_type: 'ITSM',
    state: 'HEALTHY',
    last_heartbeat: '2026-11-04T12:00:00Z',
    last_successful_ingestion: '2026-11-04T11:59:00Z',
    consecutive_failures: 0,
    error_message: null,
  },
  recent_activity: [],
  known_limitations: [
    'Runs against local synthetic fixtures; no outbound live enterprise tenant connection.',
    'Mutative operations (CREATE/UPDATE/CLOSE ticket) are architecturally barred by ReadOnlyBoundaryViolationError.',
  ],
  provenance_info: {
    source_authority: 'Synthesized ServiceNow REST API Spec (Portfolio Edition)',
    verification_status: 'CONTRACT_TESTED',
    epistemic_classification: 'LOCAL_SIMULATION',
  },
}

const MOCK_DATA_FLOW = {
  stages: [
    {
      stage_id: 'STAGE_SOURCES',
      title: 'Simulated Telecom Sources',
      subtitle: 'Synthetic Feeds & Replays',
      status: 'HEALTHY',
      epistemic_badge: 'SIMULATED_DATA',
      description: 'Mock enterprise ITSM, OSS alarm brokers, and RAN telemetry time-series generators.',
      is_simulated: true,
      order: 1,
      active_count: 6,
    },
    {
      stage_id: 'STAGE_ADAPTERS',
      title: 'Integration Adapter Boundary',
      subtitle: 'Read-Only Ingestion Gateways',
      status: 'HEALTHY',
      epistemic_badge: 'OBSERVED_FACT',
      description: 'Strict read-only protocol adapters enforcing safe HTTP methods (GET/HEAD) and schema translation.',
      is_simulated: false,
      order: 2,
      active_count: 6,
    },
    {
      stage_id: 'STAGE_SECURITY',
      title: 'Security & Defanging Gate',
      subtitle: 'Sanitization & Input Validation',
      status: 'HEALTHY',
      epistemic_badge: 'DETERMINISTIC_RULE',
      description: 'Defangs command injections, script payloads, and path traversals before memory admission.',
      is_simulated: false,
      order: 3,
      active_count: 42,
    },
    {
      stage_id: 'STAGE_NORMALIZATION',
      title: 'Canonical Normalization',
      subtitle: 'Unified Telecommunications Schema',
      status: 'HEALTHY',
      epistemic_badge: 'CANONICAL_MAPPING',
      description: 'Standardizes heterogeneous vendor payloads into 3GPP-aligned contracts.',
      is_simulated: false,
      order: 4,
      active_count: 42,
    },
    {
      stage_id: 'STAGE_DEDUPLICATION',
      title: 'Correlation & Idempotency',
      subtitle: 'Signature Deduplication Engine',
      status: 'HEALTHY',
      epistemic_badge: 'DETERMINISTIC_RULE',
      description: 'Computes SHA-256 fingerprint signatures to prevent duplicate alert storms.',
      is_simulated: false,
      order: 5,
      active_count: 42,
    },
    {
      stage_id: 'STAGE_DLQ',
      title: 'Dead-Letter Quarantine',
      subtitle: 'Failed Payload Isolation',
      status: 'HEALTHY',
      epistemic_badge: 'AUDIT_RECOVERY',
      description: 'Isolates malformed or unparseable payloads for operator inspection and audited replay.',
      is_simulated: false,
      order: 6,
      active_count: 0,
    },
    {
      stage_id: 'STAGE_PROVENANCE',
      title: 'Cryptographic Provenance',
      subtitle: 'SHA-256 Lineage & Immutability',
      status: 'HEALTHY',
      epistemic_badge: 'CRYPTOGRAPHIC_PROOF',
      description: 'Attaches immutable source lineage metadata, envelope UUIDs, and observation timestamps.',
      is_simulated: false,
      order: 7,
      active_count: 42,
    },
    {
      stage_id: 'STAGE_REVIEW',
      title: 'Human Review Hub',
      subtitle: 'Advisory Decision Support & Governance',
      status: 'HEALTHY',
      epistemic_badge: 'HUMAN_GOVERNANCE',
      description: 'Delivers synthesized telecom intelligence to human incident commanders with zero autonomous mutation.',
      is_simulated: false,
      order: 8,
      active_count: 1,
    },
  ],
  edges: [
    { source: 'STAGE_SOURCES', target: 'STAGE_ADAPTERS', label: 'Raw Envelopes' },
  ],
  active_adapters_count: 6,
  quarantined_items_count: 0,
  pipeline_health: 'HEALTHY',
  epistemic_classification: 'REFERENCE_DATA',
}

const MOCK_ACTIVITY = {
  items: [
    {
      event_id: 'ACT-001',
      timestamp: '2026-11-04T12:00:00Z',
      adapter_id: 'ITSM-SERVICENOW-01',
      source_system: 'ServiceNow',
      event_type: 'INGESTION_SUCCESS',
      status: 'SUCCESS',
      details: 'Normalized incident INC-501 successfully into canonical model',
      canonical_id: 'INC-501',
      envelope_id: 'ENV-001',
      epistemic_tag: 'OBSERVED_FACT',
    },
    {
      event_id: 'ACT-002',
      timestamp: '2026-11-04T11:55:00Z',
      adapter_id: 'TELEM-PROM-01',
      source_system: 'Prometheus',
      event_type: 'METRIC_POLL',
      status: 'HEALTHY',
      details: 'Polled 24 RAN KPI vectors successfully',
      canonical_id: null,
      envelope_id: null,
      epistemic_tag: 'REFERENCE_DATA',
    },
  ],
  total_count: 2,
  limit: 15,
  offset: 0,
}

const MOCK_DLQ_EMPTY = {
  items: [],
  total_count: 0,
  limit: 20,
  offset: 0,
}

const setupApiMocks = () => {
  vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
    if (url.startsWith('/api/v1/integrations/summary')) {
      return MOCK_SUMMARY
    }
    if (url.startsWith('/api/v1/integrations/dead-letter')) {
      return MOCK_DLQ_EMPTY
    }
    if (url.startsWith('/api/v1/integrations/data-flow')) {
      return MOCK_DATA_FLOW
    }
    if (url.startsWith('/api/v1/integrations/activity')) {
      return MOCK_ACTIVITY
    }
    if (url.startsWith('/api/v1/integrations/ITSM-SERVICENOW-01')) {
      return MOCK_DETAIL_SERVICENOW
    }
    if (url.startsWith('/api/v1/integrations')) {
      if (url.includes('category=ITSM')) {
        return MOCK_REGISTRY.filter((a) => a.category === 'ITSM')
      }
      if (url.includes('search=servicenow')) {
        return MOCK_REGISTRY.filter((a) => a.name.toLowerCase().includes('servicenow'))
      }
      return MOCK_REGISTRY
    }
    return {}
  })
}

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0,
      },
    },
  })

const renderIntegrations = () => {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <IntegrationsPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('IntegrationsWorkspace UI-7 Workspace', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    setupApiMocks()
  })

  it('renders workspace title, governance notice banner, and ecosystem metrics', async () => {
    renderIntegrations()

    // Title & Badges
    expect(await screen.findByText('Integrations Workspace')).toBeInTheDocument()
    expect(screen.getByText(/STRICT READ-ONLY BOUNDARY/i)).toBeInTheDocument()
    expect(screen.getByText(/PORTFOLIO EDITION/i)).toBeInTheDocument()

    // Summary Metric Cards (waited via async findByText)
    expect(await screen.findByText('OPERATIONAL')).toBeInTheDocument()
    expect(screen.getByText('Total Adapters')).toBeInTheDocument()
    expect(screen.getByText('Readiness State')).toBeInTheDocument()
    expect(screen.getByText('INBOUND ONLY')).toBeInTheDocument()
    expect(screen.getByText(/4 Sim \/ 2 Ref/i)).toBeInTheDocument()
  })

  it('renders configured adapter registry items and handles category filtering', async () => {
    renderIntegrations()

    // Default renders all registry items (present in both table and heartbeat cards)
    const snowElements = await screen.findAllByText('ITSM-SERVICENOW-01')
    expect(snowElements[0]).toBeInTheDocument()

    const jiraElements = await screen.findAllByText('ITSM-JIRA-01')
    expect(jiraElements[0]).toBeInTheDocument()

    const promElements = await screen.findAllByText('TELEM-PROM-01')
    expect(promElements[0]).toBeInTheDocument()

    // Click ITSM category button
    const itsmFilterBtn = screen.getByRole('button', { name: 'ITSM' })
    await userEvent.click(itsmFilterBtn)

    await waitFor(() => {
      expect(screen.getAllByText('ITSM-SERVICENOW-01')[0]).toBeInTheDocument()
      expect(screen.getAllByText('ITSM-JIRA-01')[0]).toBeInTheDocument()
      expect(screen.queryByText('TELEM-PROM-01')).not.toBeInTheDocument()
    })
  })

  it('filters adapter registry by search input', async () => {
    renderIntegrations()

    const searchInput = await screen.findByPlaceholderText(/Search adapters by name/i)
    await userEvent.type(searchInput, 'servicenow')

    await waitFor(() => {
      expect(screen.getAllByText('ITSM-SERVICENOW-01')[0]).toBeInTheDocument()
      expect(screen.queryByText('TELEM-PROM-01')).not.toBeInTheDocument()
    })
  })

  it('opens slide-over detail drawer when an adapter row is clicked and verifies secret omission', async () => {
    renderIntegrations()

    const snowRows = await screen.findAllByText('ITSM-SERVICENOW-01')
    await userEvent.click(snowRows[0])

    // Verify drawer opened
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toBeInTheDocument()

    // Verify Read-Only boundary chips
    expect(await screen.findByText(/ENFORCED \(IMMUTABLE\)/i)).toBeInTheDocument()
    expect(screen.getByText(/✓ NORMALIZE/i)).toBeInTheDocument()
    expect(screen.getByText(/✕ CREATE_TICKET/i)).toBeInTheDocument()
    expect(screen.getByText(/✕ EXECUTE_COMMAND/i)).toBeInTheDocument()

    // Verify Sanitized parameters (secrets omitted)
    expect(screen.getByText('instance_url')).toBeInTheDocument()
    expect(screen.getByText('https://telecom.service-now.com')).toBeInTheDocument()
    expect(screen.queryByText(/password/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/secret_key/i)).not.toBeInTheDocument()

    // Close drawer
    const closeBtn = screen.getByRole('button', { name: /Close detail drawer/i })
    await userEvent.click(closeBtn)

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  it('switches to Pipeline Data Flow Topology tab and renders 8 pipeline stages', async () => {
    renderIntegrations()

    const dataFlowTab = await screen.findByRole('button', { name: /Pipeline Data Flow Topology/i })
    await userEvent.click(dataFlowTab)

    expect(await screen.findByText(/End-to-End Telecom Intelligence Data Flow/i)).toBeInTheDocument()
    expect(screen.getByText('Simulated Telecom Sources')).toBeInTheDocument()
    expect(screen.getByText('Integration Adapter Boundary')).toBeInTheDocument()
    expect(screen.getByText('Security & Defanging Gate')).toBeInTheDocument()
    expect(screen.getAllByText('Canonical Normalization')[0]).toBeInTheDocument()
    expect(screen.getAllByText('Correlation & Idempotency')[0]).toBeInTheDocument()
    expect(screen.getByText('Dead-Letter Quarantine')).toBeInTheDocument()
    expect(screen.getByText('Cryptographic Provenance')).toBeInTheDocument()
    expect(screen.getAllByText('Human Review Hub')[0]).toBeInTheDocument()
  })

  it('switches to Activity Stream tab and renders paginated integration events', async () => {
    renderIntegrations()

    const activityTab = await screen.findByRole('button', { name: /Activity Stream/i })
    await userEvent.click(activityTab)

    expect(await screen.findByText('ACT-001')).toBeInTheDocument()
    expect(screen.getByText('ACT-002')).toBeInTheDocument()
    expect(screen.getByText(/Normalized incident INC-501 successfully/i)).toBeInTheDocument()
    expect(screen.getByText(/Polled 24 RAN KPI vectors successfully/i)).toBeInTheDocument()
  })

  it('switches to Dead-Letter Quarantine tab and renders clean state when DLQ is empty', async () => {
    renderIntegrations()

    const dlqTab = await screen.findByRole('button', { name: /Dead-Letter Quarantine/i })
    await userEvent.click(dlqTab)

    expect(await screen.findByText('Quarantine Clean')).toBeInTheDocument()
    expect(
      screen.getByText(/Zero unparseable or rejected payloads are currently held/i)
    ).toBeInTheDocument()
  })
})
