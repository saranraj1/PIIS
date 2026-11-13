import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SystemHealthPage } from '../pages/SystemHealthPage'
import { apiClient } from '../api/client'

const MOCK_OVERVIEW = {
  aggregate_status: 'HEALTHY',
  evaluation_policy: 'CRITICALITY_AWARE_STRICT',
  last_evaluated_at: '2026-11-04T12:00:00Z',
  healthy_count: 14,
  degraded_count: 0,
  unavailable_count: 0,
  unknown_count: 3,
  total_components: 17,
  readiness_status: 'READY',
  liveness_status: 'HEALTHY',
  external_connectivity: 'DISCONNECTED_PORTFOLIO_MODE',
  epistemic_classification: 'OBSERVED_STATE',
}

const MOCK_COMPONENTS = [
  {
    component_id: 'api-gateway',
    name: 'FastAPI Application Gateway',
    category: 'API',
    health_state: 'HEALTHY',
    criticality: 'CRITICAL',
    last_observed_at: '2026-11-04T12:00:00Z',
    freshness: 'FRESH',
    check_source: 'Liveness & Event Loop Probe',
    failure_reason: null,
    implementation_nature: 'REAL_LOCAL',
    details: { framework: 'FastAPI', service: 'piis-core' },
  },
  {
    component_id: 'auth-manager',
    name: 'Enterprise Auth & Access Manager',
    category: 'AUTH',
    health_state: 'HEALTHY',
    criticality: 'CRITICAL',
    last_observed_at: '2026-11-04T12:00:00Z',
    freshness: 'FRESH',
    check_source: 'AuthManager active state',
    failure_reason: null,
    implementation_nature: 'REAL_LOCAL',
    details: { active_roles: 5 },
  },
  {
    component_id: 'dead-letter-quarantine',
    name: 'Dead-Letter Quarantine (DLQ)',
    category: 'DLQ',
    health_state: 'HEALTHY',
    criticality: 'STANDARD',
    last_observed_at: '2026-11-04T12:00:00Z',
    freshness: 'FRESH',
    check_source: 'pipeline.dlq.count()',
    failure_reason: null,
    implementation_nature: 'REAL_LOCAL',
    details: { quarantine_count: 0 },
  },
  {
    component_id: 'knowledge-retrieval-dense',
    name: 'Dense Bi-Encoder Vector Index',
    category: 'RETRIEVAL',
    health_state: 'HEALTHY',
    criticality: 'STANDARD',
    last_observed_at: '2026-11-04T12:00:00Z',
    freshness: 'FRESH',
    check_source: 'DenseBiEncoderIndex.is_fallback_mode',
    failure_reason: null,
    implementation_nature: 'REAL_LOCAL',
    details: { model_name: 'sentence-transformers/all-MiniLM-L6-v2', fallback_mode: false },
  },
  {
    component_id: 'background-worker',
    name: 'Distributed Background Task Queue',
    category: 'BACKGROUND',
    health_state: 'UNKNOWN',
    criticality: 'INFORMATIONAL',
    last_observed_at: '2026-11-04T12:00:00Z',
    freshness: 'NOT_APPLICABLE',
    check_source: 'Runtime Environment Architecture Check',
    failure_reason: 'PIIS runs synchronously in-process; distributed background task workers are not instrumented.',
    implementation_nature: 'NOT_INSTRUMENTED',
    details: { runtime_mode: 'SYNCHRONOUS_IN_PROCESS' },
  },
]

const MOCK_INGESTION = {
  pipeline_status: 'OPERATIONAL',
  cumulative_ingested_events: 128,
  cumulative_stored_incidents: 42,
  cumulative_stored_alarms: 64,
  cumulative_stored_telemetry: 512,
  current_dlq_depth: 0,
  deduplication_cache_size: 128,
  registered_adapters_count: 6,
  last_successful_ingestion: '2026-11-04T12:00:00Z',
  last_failed_ingestion: null,
  rate_limit_policy: 'TOKEN_BUCKET_BURST_PROTECTED',
  data_direction: 'INBOUND_ONLY',
}

const MOCK_INTELLIGENCE = {
  engine_version: '1.0.0',
  investigation_status: 'OPERATIONAL',
  bm25_index_status: 'OPERATIONAL',
  bm25_total_chunks: 150,
  dense_index_status: 'OPERATIONAL',
  dense_model_name: 'sentence-transformers/all-MiniLM-L6-v2',
  dense_is_fallback_mode: false,
  fusion_algorithm: 'RECIPROCAL_RANK_FUSION (k=60)',
  sop_rules_count: 15,
  anomaly_detection_status: 'OPERATIONAL',
  evaluation_mode: 'OFFLINE_REFERENCE_DETERMINISTIC',
}

const MOCK_PERSISTENCE = {
  audit_ledger_status: 'VERIFIED',
  ledger_file_accessible: true,
  ledger_record_count: 24,
  ledger_head_sequence: 24,
  checkpoint_anchor_status: 'SYNCHRONIZED',
  checkpoint_sequence: 24,
  hmac_key_provider_status: 'AVAILABLE',
  disk_fsync_supported: true,
  last_verification_timestamp: '2026-11-04T12:00:00Z',
  external_trust_anchor_connected: false,
  trust_anchor_limitation_disclosure:
    'Local coordinated rollback cannot be detected without external trust anchor (DEP-M5.3-001 prerequisite).',
}

const MOCK_EVENTS = {
  items: [
    {
      event_id: 'EVT-TEST-001',
      timestamp: '2026-11-04T12:00:00Z',
      component_id: 'api-gateway',
      previous_state: null,
      new_state: 'HEALTHY',
      event_type: 'PROBE_HEARTBEAT',
      source: 'UVICORN_RUNTIME',
      reason: 'FastAPI gateway event loop responsive',
      epistemic_tag: 'OPERATIONAL_OBSERVATION',
    },
  ],
  total_count: 1,
  limit: 100,
  offset: 0,
}

const MOCK_DEPENDENCIES = {
  nodes: [
    { id: 'api-gateway', name: 'FastAPI Application Gateway', category: 'API', health_state: 'HEALTHY', criticality: 'CRITICAL', is_external: false },
    { id: 'auth-manager', name: 'Enterprise Auth & Access Manager', category: 'AUTH', health_state: 'HEALTHY', criticality: 'CRITICAL', is_external: false },
    { id: 'dead-letter-quarantine', name: 'Dead-Letter Quarantine (DLQ)', category: 'DLQ', health_state: 'HEALTHY', criticality: 'STANDARD', is_external: false },
    { id: 'background-worker', name: 'Distributed Background Task Queue', category: 'BACKGROUND', health_state: 'UNKNOWN', criticality: 'INFORMATIONAL', is_external: true },
  ],
  edges: [
    { source: 'api-gateway', target: 'auth-manager', relationship_type: 'CALLS', label: 'Bearer Token Auth Verification' },
  ],
  graph_type: 'STATIC_CODEBASE_GROUNDED',
  epistemic_classification: 'VERIFIED_ARCHITECTURE',
}

const MOCK_HEALTH = {
  status: 'ok',
  service: 'piis-core',
  mode: 'read_only_decision_support',
}

const MOCK_READY = {
  status: 'ready',
  registered_adapters_count: 6,
  degraded_adapters: [],
  incidents_count: 42,
  dead_letter_count: 0,
  audit_ledger_records: 24,
}

describe('SystemHealthPage (UI-8)', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0 },
      },
    })

    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/system-health/overview')) return MOCK_OVERVIEW
      if (url.includes('/api/v1/system-health/components')) return MOCK_COMPONENTS
      if (url.includes('/api/v1/system-health/ingestion')) return MOCK_INGESTION
      if (url.includes('/api/v1/system-health/intelligence')) return MOCK_INTELLIGENCE
      if (url.includes('/api/v1/system-health/persistence')) return MOCK_PERSISTENCE
      if (url.includes('/api/v1/system-health/events')) return MOCK_EVENTS
      if (url.includes('/api/v1/system-health/dependencies')) return MOCK_DEPENDENCIES
      if (url.includes('/api/v1/health')) return MOCK_HEALTH
      if (url.includes('/api/v1/ready')) return MOCK_READY
      throw new Error(`Unhandled endpoint: ${url}`)
    })
  })

  const renderComponent = () =>
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <SystemHealthPage />
        </MemoryRouter>
      </QueryClientProvider>,
    )

  it('renders top-level status banner with aggregate status, metric cards, and limitation disclaimer', async () => {
    renderComponent()

    await waitFor(() => {
      expect(screen.getByText('System Health & Operations Workspace')).toBeInTheDocument()
    })

    expect(screen.getByText('Portfolio Edition Trust & Connectivity Scope')).toBeInTheDocument()
    expect(screen.getByText(/Local coordinated rollback detection requires an external hardware or cloud trust anchor/)).toBeInTheDocument()
    expect(screen.getByText('Aggregate Status')).toBeInTheDocument()
    expect(screen.getByText('Healthy Subsystems')).toBeInTheDocument()
    expect(screen.getByText('Readiness & Liveness')).toBeInTheDocument()
  })

  it('renders component registry with criticality badges and uninstrumented disclaimers', async () => {
    renderComponent()

    await waitFor(() => {
      expect(screen.getByText('FastAPI Application Gateway')).toBeInTheDocument()
    })

    expect(screen.getByText('Enterprise Auth & Access Manager')).toBeInTheDocument()
    expect(screen.getByText('Distributed Background Task Queue')).toBeInTheDocument()
    expect(screen.getByText('NOT_INSTRUMENTED')).toBeInTheDocument()
  })

  it('filters components by search query', async () => {
    const user = userEvent.setup()
    renderComponent()

    await waitFor(() => {
      expect(screen.getByText('FastAPI Application Gateway')).toBeInTheDocument()
    })

    const searchInput = screen.getByPlaceholderText('Search component by name, ID, or fault...')
    await user.type(searchInput, 'gateway')

    expect(screen.getByText('FastAPI Application Gateway')).toBeInTheDocument()
    expect(screen.queryByText('Enterprise Auth & Access Manager')).not.toBeInTheDocument()
  })

  it('opens and closes component diagnostics drawer', async () => {
    const user = userEvent.setup()
    renderComponent()

    await waitFor(() => {
      expect(screen.getByText('FastAPI Application Gateway')).toBeInTheDocument()
    })

    const diagButtons = screen.getAllByRole('button', { name: /Diagnostics/i })
    await user.click(diagButtons[0])

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    expect(screen.getByText('Diagnostic Telemetry & Attributes')).toBeInTheDocument()

    const closeBtn = screen.getByRole('button', { name: /Close Diagnostics/i })
    await user.click(closeBtn)

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  it('switches to Ingestion tab and displays pipeline metrics', async () => {
    const user = userEvent.setup()
    renderComponent()

    const ingestionTab = screen.getByRole('button', { name: /Ingestion & DLQ Pipeline/i })
    await user.click(ingestionTab)

    await waitFor(() => {
      expect(screen.getByText('Ingested Envelopes')).toBeInTheDocument()
    })

    expect(screen.getByText('Stored Incidents')).toBeInTheDocument()
    expect(screen.getByText('Dead-Letter Quarantine (DLQ)')).toBeInTheDocument()
    expect(screen.getByText('Idempotency & Rate Limiting')).toBeInTheDocument()
    expect(screen.getByText(/TOKEN_BUCKET_BURST_PROTECTED/)).toBeInTheDocument()
  })

  it('switches to Intelligence tab and displays AI retrieval & SOP rules', async () => {
    const user = userEvent.setup()
    renderComponent()

    const intelTab = screen.getByRole('button', { name: /AI & Retrieval Subsystem/i })
    await user.click(intelTab)

    await waitFor(() => {
      expect(screen.getByText('Investigation Engine')).toBeInTheDocument()
    })

    expect(screen.getByText('Lexical BM25 Index')).toBeInTheDocument()
    expect(screen.getByText('Deterministic SOP Rules')).toBeInTheDocument()
    expect(screen.getByText('15 Rules')).toBeInTheDocument()
    expect(screen.getByText(/RECIPROCAL_RANK_FUSION/)).toBeInTheDocument()
  })

  it('switches to Persistence tab and displays ledger & checkpoint anchor status', async () => {
    const user = userEvent.setup()
    renderComponent()

    const persistTab = screen.getByRole('button', { name: /Persistence & Audit Parity/i })
    await user.click(persistTab)

    await waitFor(() => {
      expect(screen.getByText('Audit Ledger Status')).toBeInTheDocument()
    })

    expect(screen.getByText('Checkpoint Anchor Parity')).toBeInTheDocument()
    expect(screen.getByText('HMAC Key Provider')).toBeInTheDocument()
    expect(screen.getByText('Physical JSONL File Accessible on Disk:')).toBeInTheDocument()
    expect(screen.getByText('YES (READABLE)')).toBeInTheDocument()
    expect(screen.getByText('Immutable Trust Anchor Limitation Disclosure')).toBeInTheDocument()
  })

  it('switches to Events tab and renders observation timeline', async () => {
    const user = userEvent.setup()
    renderComponent()

    const eventsTab = screen.getByRole('button', { name: /Health Events Timeline/i })
    await user.click(eventsTab)

    await waitFor(() => {
      expect(screen.getByText('PROBE_HEARTBEAT')).toBeInTheDocument()
    })

    expect(screen.getByText('UVICORN_RUNTIME')).toBeInTheDocument()
    expect(screen.getByText('FastAPI gateway event loop responsive')).toBeInTheDocument()
  })

  it('switches to Topology tab and renders architecture layers and edges', async () => {
    const user = userEvent.setup()
    renderComponent()

    const topoTab = screen.getByRole('button', { name: /Dependency Topology Map/i })
    await user.click(topoTab)

    await waitFor(() => {
      expect(screen.getByText('Architecturally Grounded Dependency Topology Map')).toBeInTheDocument()
    })

    expect(screen.getByText('1. Edge & Ingestion Layer')).toBeInTheDocument()
    expect(screen.getByText('2. Intelligence & Retrieval Layer')).toBeInTheDocument()
    expect(screen.getByText('3. Review & Audit Layer')).toBeInTheDocument()
    expect(screen.getByText('Directed Subsystem Dependency Edges')).toBeInTheDocument()
    expect(screen.getAllByText('api-gateway').length).toBeGreaterThan(0)
  })
})
