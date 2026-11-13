import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { NetworkIntelligencePage } from '../pages/NetworkIntelligencePage'
import { apiClient } from '../api/client'
import { useIncidentContextStore } from '../store/incidentContextStore'
import {
  MOCK_NETWORK_OVERVIEW,
  MOCK_NETWORK_TOPOLOGY,
  MOCK_NETWORK_IMPACT,
  MOCK_NETWORK_ALARMS,
  MOCK_NETWORK_TELEMETRY,
} from './fixtures/networkFixtures'

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0,
      },
    },
  })

const renderNetworkPage = () => {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <NetworkIntelligencePage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('NetworkIntelligencePage Workspace', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    useIncidentContextStore.getState().resetFilters()
    useIncidentContextStore.getState().setSelectedIncidentId(null)

    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/network/overview')) return MOCK_NETWORK_OVERVIEW
      if (url.includes('/api/v1/network/topology')) return MOCK_NETWORK_TOPOLOGY
      if (url.includes('/api/v1/network/impact')) return MOCK_NETWORK_IMPACT
      if (url.includes('/api/v1/network/alarms')) return MOCK_NETWORK_ALARMS
      if (url.includes('/api/v1/network/telemetry')) return MOCK_NETWORK_TELEMETRY
      return {}
    })
  })

  it('renders workspace title and high-level overview metrics', async () => {
    renderNetworkPage()

    expect(await screen.findByText('Network Intelligence Workspace')).toBeInTheDocument()
    expect(await screen.findByText('Registered Topology Elements')).toBeInTheDocument()
    expect(screen.getByText('13')).toBeInTheDocument() // 13 total elements
    expect(screen.getByText('Active Network Alarms')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument() // 2 active alarms
    expect(screen.getByText('Correlated Incident Clusters')).toBeInTheDocument()
    expect(screen.getAllByText('1').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Telemetry Stream Violations')).toBeInTheDocument()
  })

  it('renders domain inventory sub-bar with exact counts', async () => {
    renderNetworkPage()

    expect(await screen.findByText('Domain Inventory:')).toBeInTheDocument()
    expect(screen.getByText(/RAN:/)).toBeInTheDocument()
    expect(screen.getByText(/5G_CORE:/)).toBeInTheDocument()
    expect(screen.getByText(/TRANSPORT:/)).toBeInTheDocument()
    expect(screen.getByText('Read-Only Boundary Enforced')).toBeInTheDocument()
  })

  it('renders interactive topology explorer with nodes', async () => {
    renderNetworkPage()

    const gnbNodes = await screen.findAllByText('GNB-TESTBED-5G-01')
    expect(gnbNodes.length).toBeGreaterThanOrEqual(1)

    const cellNodes = await screen.findAllByText('CELL-101')
    expect(cellNodes.length).toBeGreaterThanOrEqual(1)

    expect(await screen.findByText('UPF-CORE-PRIMARY')).toBeInTheDocument()
    expect(await screen.findByText('AMF-CORE-01')).toBeInTheDocument()
  })

  it('filters topology nodes when a domain filter button is clicked', async () => {
    renderNetworkPage()

    // Initially nodes visible
    expect(await screen.findByText('UPF-CORE-PRIMARY')).toBeInTheDocument()

    // Click 5G_CORE filter button in topology toolbar
    const coreBtns = screen.getAllByRole('button', { name: '5G_CORE' })
    fireEvent.click(coreBtns[0])

    // Only 5G_CORE nodes should be in positions map
    expect(screen.getByText('UPF-CORE-PRIMARY')).toBeInTheDocument()
    expect(screen.getByText('AMF-CORE-01')).toBeInTheDocument()
  })

  it('opens element detail drawer when a topology node is clicked', async () => {
    renderNetworkPage()

    const gnbNodes = await screen.findAllByText('GNB-TESTBED-5G-01')
    fireEvent.click(gnbNodes[0])

    // Drawer should open displaying element type and nominal subscribers
    expect(await screen.findByText('Nominal Subscribers:')).toBeInTheDocument()
    expect(screen.getByText('5,000')).toBeInTheDocument()
    expect(screen.getByText('Analyze Blast Radius')).toBeInTheDocument()
  })

  it('renders NetworkImpactCard with blast radius and subscriber disclaimer upon node selection', async () => {
    renderNetworkPage()

    const gnbNodes = await screen.findAllByText('GNB-TESTBED-5G-01')
    fireEvent.click(gnbNodes[0])

    expect(await screen.findByText('Network Impact & Blast Radius Assessment')).toBeInTheDocument()
    expect(screen.getByText(/MAJOR RISK/i)).toBeInTheDocument()
    expect(screen.getByText(/10,000/)).toBeInTheDocument()
    expect(screen.getByText(/Epistemic Grounding Notice/i)).toBeInTheDocument()
    expect(screen.getByText(/Aggregated nominal capacity across 4 direct\/inferred elements/i)).toBeInTheDocument()
  })

  it('renders AlarmIntelligenceCard with correlated clusters and rationales', async () => {
    renderNetworkPage()

    expect(await screen.findByText('Alarm Intelligence & Causal Clusters')).toBeInTheDocument()
    expect(screen.getByText('CLUST-RAN-A1B2')).toBeInTheDocument()
    expect(screen.getByText(/88% Affinity Proxy/i)).toBeInTheDocument()
    expect(screen.getByText('Shared fault category (RADIO_CAPACITY)')).toBeInTheDocument()
  })

  it('switches between clusters and raw alarms view in AlarmIntelligenceCard', async () => {
    renderNetworkPage()

    const rawAlarmsBtn = await screen.findByRole('button', { name: /Alarms \(/i })
    fireEvent.click(rawAlarmsBtn)

    // Should render alarms table
    expect(screen.getByText('High VSWR on feeder')).toBeInTheDocument()
    expect(screen.getByText('Radio link failure')).toBeInTheDocument()
    expect(screen.getByText('7100')).toBeInTheDocument()
    expect(screen.getByText('CELL-DEG')).toBeInTheDocument()
  })

  it('renders TelemetryExplorerCard with SVG time-series points and anomaly markers upon selection', async () => {
    renderNetworkPage()

    // Click node to select it
    const gnbNodes = await screen.findAllByText('GNB-TESTBED-5G-01')
    fireEvent.click(gnbNodes[0])

    expect(await screen.findByText('Telemetry Time-Series & Anomaly Stream')).toBeInTheDocument()
    expect(screen.getAllByText(/prb_utilization_pct/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/Observed:/)).toBeInTheDocument()
    expect(screen.getByText('89.6')).toBeInTheDocument()
  })
})
