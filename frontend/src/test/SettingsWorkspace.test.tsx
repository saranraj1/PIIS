import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SettingsPage } from '../pages/SettingsPage'
import { ThemeProvider } from '../theme/ThemeContext'
import { AuthProvider } from '../auth/AuthContext'
import { apiClient } from '../api/client'

const MOCK_SYSTEM_INFO = {
  application_name: 'Production Incident Intelligence System',
  application_edition: 'Telecom Edition (Portfolio Release)',
  core_version: '1.0.0-rc2',
  api_version: '1.0.0',
  active_milestone: 'PRODUCTION_READY',
  environment: 'development',
  operational_mode: 'read_only_decision_support',
  telecom_domains: ['RAN', 'Transport', 'Core', 'IMS', 'Cloud'],
  auth_mode: 'IN_MEMORY_JWT_OIDC',
  rbac_enforced: true,
  service_principals_barred: true,
  retrieval_models: {
    lexical_index: 'BM25 Okapi (In-Memory Index)',
    dense_bi_encoder: 'all-MiniLM-L6-v2 (Offline Local Fallback)',
    deterministic_sop_rules: '15 Registered Rules',
    anomaly_detectors: '3-Sigma Z-Score & Isolation Forest',
  },
  operational_boundaries: {
    network_mutations_allowed: false,
    production_commands_allowed: false,
    ticket_closures_allowed: false,
    external_egress_allowed: false,
    autonomous_remediation_allowed: false,
    secret_exposure_allowed: false,
  },
  documentation_catalog: [
    {
      title: 'System Release Notes',
      path: 'docs/m7/M7_PORTFOLIO_RELEASE_NOTES.md',
      category: 'PORTFOLIO',
      description: 'Release notes and architecture for Telecom Edition v1.0.0.',
    },
    {
      title: 'Security & Reliability Audit',
      path: 'docs/ui/UI8_1_INDEPENDENT_AUDIT.md',
      category: 'VERIFICATION',
      description: 'Adversarial runtime health, security, and regression audit.',
    },
    {
      title: 'System Architecture Specification',
      path: 'docs/ui/UI9_SETTINGS_WORKSPACE.md',
      category: 'SPECIFICATION',
      description: 'Settings and configuration workspace design and verification.',
    },
  ],
  epistemic_classification: 'VERIFIED_CONFIGURATION',
}

const MOCK_PERSISTENCE = {
  audit_ledger_status: 'AVAILABLE',
  audit_ledger_records_count: 2,
  ledger_head_sequence: 2,
  checkpoint_anchor_status: 'MONOTONIC_ANCHORED',
  checkpoint_sequence: 2,
  hmac_key_provider_status: 'LocalDevKeyProvider',
  disk_fsync_supported: true,
  last_verification_timestamp: '2026-11-04T12:00:00Z',
  external_trust_anchor_connected: false,
  trust_anchor_limitation_disclosure: 'Portfolio disconnected boundary',
}

const MOCK_INTEGRATIONS = [
  {
    integration_id: 'SNOW-ITSM-01',
    name: 'ServiceNow ITSM Connector',
    category: 'ITSM',
    provider_type: 'SERVICENOW',
    adapter_class: 'ServiceNowAdapter',
    connection_mode: 'REST_PULL',
    operational_status: 'AVAILABLE',
    status_label: 'LOCALLY VERIFIED',
    capabilities: ['INCIDENT_INGESTION'],
    data_direction: 'INGESTION_ONLY',
    rate_limit_rps: 50,
    last_heartbeat: '2026-11-04T12:00:00Z',
    consecutive_failures: 0,
  },
  {
    integration_id: 'PROM-TELEM-01',
    name: 'Prometheus Telemetry Scraper',
    category: 'TELEMETRY',
    provider_type: 'PROMETHEUS',
    adapter_class: 'PrometheusAdapter',
    connection_mode: 'SCRAPE_TARGET',
    operational_status: 'AVAILABLE',
    status_label: 'LOCALLY VERIFIED',
    capabilities: ['METRICS_PULL'],
    data_direction: 'INGESTION_ONLY',
    rate_limit_rps: 100,
    last_heartbeat: '2026-11-04T12:00:00Z',
    consecutive_failures: 0,
  },
]

describe('SettingsPage Workspace (UI-9)', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, staleTime: Infinity },
      },
    })
    localStorage.clear()
    vi.restoreAllMocks()

    vi.spyOn(apiClient, 'get').mockImplementation(async (endpoint: string) => {
      if (endpoint === '/api/v1/settings/system-info') return MOCK_SYSTEM_INFO
      if (endpoint === '/api/v1/system-health/persistence') return MOCK_PERSISTENCE
      if (endpoint === '/api/v1/integrations') return MOCK_INTEGRATIONS
      return {}
    })
  })

  const renderComponent = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <AuthProvider>
            <MemoryRouter>
              <SettingsPage />
            </MemoryRouter>
          </AuthProvider>
        </ThemeProvider>
      </QueryClientProvider>
    )
  }

  it('renders top workspace header, title, and epistemic badge', async () => {
    renderComponent()

    expect(screen.getByText('Settings & Configuration Workspace')).toBeInTheDocument()
    expect(screen.getByText('PRODUCTION READY')).toBeInTheDocument()
    expect(screen.getByText('ANONYMOUS (READ-ONLY)')).toBeInTheDocument()
  })

  it('renders all 6 navigation tabs', async () => {
    renderComponent()

    expect(screen.getByRole('button', { name: /Appearance & Display/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /User & Session/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Application Config/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Security & Trust/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Integration Config/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /About & System Info/i })).toBeInTheDocument()
  })

  it('allows changing appearance preferences (Theme, Density, Timezone)', async () => {
    const user = userEvent.setup()
    renderComponent()

    // 1. Change Theme to Light
    const lightBtn = screen.getByRole('button', { name: /Light/i })
    await user.click(lightBtn)
    expect(localStorage.getItem('piis_theme_preference')).toBe('light')

    // 2. Change Density to Compact
    const compactBtn = screen.getByRole('button', { name: /Compact/i })
    await user.click(compactBtn)
    expect(localStorage.getItem('piis_display_density')).toBe('compact')

    // 3. Change Timezone to Station Local
    const localTzBtn = screen.getByRole('button', { name: /Station Local/i })
    await user.click(localTzBtn)
    expect(localStorage.getItem('piis_timezone_preference')).toBe('LOCAL')
  })

  it('allows changing page size and telemetry refresh interval', async () => {
    const user = userEvent.setup()
    renderComponent()

    // 1. Change Page Size to 50 Rows
    const rows50Btn = screen.getByRole('button', { name: /50 Rows/i })
    await user.click(rows50Btn)
    expect(localStorage.getItem('piis_page_size')).toBe('50')

    // 2. Change Refresh Interval to 60s
    const refresh60Btn = screen.getByRole('button', { name: /60s/i })
    await user.click(refresh60Btn)
    expect(localStorage.getItem('piis_refresh_interval')).toBe('60s')
  })

  it('confirms and resets preferences to NOC factory defaults', async () => {
    const user = userEvent.setup()
    renderComponent()

    // Mutate density
    await user.click(screen.getByRole('button', { name: /Compact/i }))
    expect(localStorage.getItem('piis_display_density')).toBe('compact')

    // Click Reset Preferences
    const resetTrigger = screen.getByRole('button', { name: /Reset Preferences/i })
    await user.click(resetTrigger)

    // Confirm dialog appears
    const confirmBtn = screen.getByRole('button', { name: /Confirm Reset/i })
    await user.click(confirmBtn)

    // Verify reset to defaults
    expect(localStorage.getItem('piis_display_density')).toBe('comfortable')
    expect(localStorage.getItem('piis_timezone_preference')).toBe('UTC')
    expect(localStorage.getItem('piis_theme_preference')).toBe('dark')
  })

  it('switches to User & Session tab and handles token entry and purge', async () => {
    const user = userEvent.setup()
    renderComponent()

    // Switch tab
    await user.click(screen.getByRole('button', { name: /User & Session/i }))

    expect(screen.getByText('Zero-Persistence In-Memory Authentication Guarantee:')).toBeInTheDocument()
    expect(screen.getByText('ANONYMOUS READ-ONLY')).toBeInTheDocument()

    // Mock token payload for OP-TIER2-01
    // eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJvcC10aWVyMi0wMSIsInVzZXJuYW1lIjoiQWxpY2UgQ2hlbiIsInJvbGVzIjpbIk5PQ19MMiJdLCJwZXJtaXNzaW9ucyI6WyJWSUVXX0lOQ0lERU5UUyIsIkFQUFJPVkVfTUVESVVNX1JJU0siXX0.mock
    const mockToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJvcC10aWVyMi0wMSIsInVzZXJuYW1lIjoiQWxpY2UgQ2hlbiIsInJvbGVzIjpbIk5PQ19MMiJdLCJwZXJtaXNzaW9ucyI6WyJWSUVXX0lOQ0lERU5UUyIsIkFQUFJPVkVfTUVESVVNX1JJU0siXX0.mock'

    const tokenInput = screen.getByPlaceholderText(/eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9/i)
    fireEvent.change(tokenInput, { target: { value: mockToken } })

    const applyBtn = screen.getByRole('button', { name: /Apply Token in Memory/i })
    await user.click(applyBtn)

    // Verify authenticated state
    await waitFor(() => {
      expect(screen.getByText('AUTHENTICATED')).toBeInTheDocument()
      expect(screen.getAllByText('op-tier2-01').length).toBeGreaterThan(0)
      expect(screen.getByText('NOC_L2')).toBeInTheDocument()
      expect(screen.getByText('APPROVE_MEDIUM_RISK')).toBeInTheDocument()
    })

    // Purge session
    const purgeBtn = screen.getByRole('button', { name: /Purge Session/i })
    await user.click(purgeBtn)

    await waitFor(() => {
      expect(screen.getByText('ANONYMOUS READ-ONLY')).toBeInTheDocument()
    })
  })

  it('switches to Application Config tab and renders locked boundaries', async () => {
    const user = userEvent.setup()
    renderComponent()

    await user.click(screen.getByRole('button', { name: /Application Config/i }))

    await waitFor(() => {
      expect(screen.getByText('Operational Boundary Guarantees')).toBeInTheDocument()
      expect(screen.getByText('100% READ-ONLY')).toBeInTheDocument()
      expect(screen.getAllByText('DISABLED / PROHIBITED').length).toBeGreaterThan(0)
      expect(screen.getByText('15 Rules (Code-Locked)')).toBeInTheDocument()
    })
  })

  it('switches to Security & Trust tab and displays verification posture', async () => {
    const user = userEvent.setup()
    renderComponent()

    await user.click(screen.getByRole('button', { name: /Security & Trust/i }))

    await waitFor(() => {
      expect(screen.getByText('Authentication Mode')).toBeInTheDocument()
      expect(screen.getByText('STATUS: MONOTONIC_ANCHORED')).toBeInTheDocument()
      expect(screen.getByText('LocalDevKeyProvider')).toBeInTheDocument()
      expect(screen.getByText(/Portfolio Boundary & Disconnected External Prerequisites/i)).toBeInTheDocument()
    })
  })

  it('switches to Integration Config tab and displays registered adapters', async () => {
    const user = userEvent.setup()
    renderComponent()

    await user.click(screen.getByRole('button', { name: /Integration Config/i }))

    await waitFor(() => {
      expect(screen.getByText('Telecom Protocol Adapters Pool')).toBeInTheDocument()
      expect(screen.getByText('SNOW-ITSM-01')).toBeInTheDocument()
      expect(screen.getByText('PROM-TELEM-01')).toBeInTheDocument()
      expect(screen.getAllByText('READ_ONLY=TRUE').length).toBe(2)
    })
  })

  it('switches to About tab and renders documentation catalog', async () => {
    const user = userEvent.setup()
    renderComponent()

    await user.click(screen.getByRole('button', { name: /About & System Info/i }))

    await waitFor(() => {
      expect(screen.getByText('System Architecture & Metadata')).toBeInTheDocument()
      expect(screen.getByText('v1.0.0-rc2')).toBeInTheDocument()
      expect(screen.getByText('Authoritative Documentation Suite')).toBeInTheDocument()
      expect(screen.getByText('System Release Notes')).toBeInTheDocument()
      expect(screen.getByText('Security & Reliability Audit')).toBeInTheDocument()
      expect(screen.getByText('System Architecture Specification')).toBeInTheDocument()
    })
  })
})
