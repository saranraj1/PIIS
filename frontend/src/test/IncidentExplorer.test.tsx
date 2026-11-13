import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { IncidentExplorerPage } from '../pages/IncidentExplorerPage'
import { apiClient, ApiClientError } from '../api/client'
import { useIncidentContextStore } from '../store/incidentContextStore'
import {
  MOCK_INCIDENT_LIST_RESPONSE,
  MOCK_DETAIL_RESPONSE,
} from './fixtures/incidentFixtures'

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0,
      },
    },
  })

const renderIncidentExplorer = () => {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <IncidentExplorerPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('IncidentExplorerPage Real Incident Catalog', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    useIncidentContextStore.getState().resetFilters()
    useIncidentContextStore.getState().setSelectedIncidentId(null)
  })

  it('renders incident table with actual backend fields', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(MOCK_INCIDENT_LIST_RESPONSE)

    renderIncidentExplorer()

    // 1. Table headers and records
    expect(await screen.findByText('INC-2026-0001')).toBeInTheDocument()
    expect(screen.getByText('INC-2026-0002')).toBeInTheDocument()
    expect(screen.getByText('INC-2026-0003')).toBeInTheDocument()
    expect(screen.getByText('INC-2026-0004')).toBeInTheDocument()

    // 2. Field verifications
    expect(screen.getByText('High VSWR on 5G NR Sector 4B')).toBeInTheDocument()
    expect(screen.getByText('UPF N3 Interface Packet Drops')).toBeInTheDocument()
    expect(screen.getAllByText('CRITICAL').length).toBeGreaterThan(0)
    expect(screen.getAllByText('RAN').length).toBeGreaterThan(0)
  })

  it('filters incidents by text search query', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'get').mockResolvedValue(MOCK_INCIDENT_LIST_RESPONSE)

    renderIncidentExplorer()

    expect(await screen.findByText('INC-2026-0001')).toBeInTheDocument()

    const searchInput = screen.getByLabelText(/Search incidents/i)
    await act(async () => {
      await user.type(searchInput, 'DWDM')
    })

    // DWDM incident should match
    expect(screen.getByText('INC-2026-0003')).toBeInTheDocument()
    expect(screen.queryByText('INC-2026-0001')).not.toBeInTheDocument()
    expect(screen.queryByText('INC-2026-0002')).not.toBeInTheDocument()
  })

  it('filters incidents by severity dropdown selection', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'get').mockResolvedValue(MOCK_INCIDENT_LIST_RESPONSE)

    renderIncidentExplorer()

    expect(await screen.findByText('INC-2026-0001')).toBeInTheDocument()

    const severitySelect = screen.getByLabelText(/Filter by Severity/i)
    await act(async () => {
      await user.selectOptions(severitySelect, 'CRITICAL')
    })

    expect(screen.getByText('INC-2026-0001')).toBeInTheDocument()
    expect(screen.queryByText('INC-2026-0002')).not.toBeInTheDocument()
    expect(screen.queryByText('INC-2026-0003')).not.toBeInTheDocument()
  })

  it('filters incidents by resolution status (ACTIVE vs RESOLVED)', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'get').mockResolvedValue(MOCK_INCIDENT_LIST_RESPONSE)

    renderIncidentExplorer()

    expect(await screen.findByText('INC-2026-0001')).toBeInTheDocument()

    const statusSelect = screen.getByLabelText(/Filter by Resolution Status/i)
    await act(async () => {
      await user.selectOptions(statusSelect, 'RESOLVED')
    })

    // Only resolved incidents (INC-0003, INC-0004) should remain
    expect(screen.getByText('INC-2026-0003')).toBeInTheDocument()
    expect(screen.getByText('INC-2026-0004')).toBeInTheDocument()
    expect(screen.queryByText('INC-2026-0001')).not.toBeInTheDocument()
    expect(screen.queryByText('INC-2026-0002')).not.toBeInTheDocument()
  })

  it('opens detail drawer when an incident row is clicked', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/incidents/INC-2026-0001')) return MOCK_DETAIL_RESPONSE
      if (url.includes('/api/v1/incidents')) return MOCK_INCIDENT_LIST_RESPONSE
      return {}
    })

    renderIncidentExplorer()

    const row = await screen.findByText('INC-2026-0001')
    await act(async () => {
      await user.click(row)
    })

    // Detail drawer should appear with lineage & element IDs
    expect(await screen.findByText('Correlated Elements')).toBeInTheDocument()
    expect(screen.getByText('gnb-cluster-tx-09')).toBeInTheDocument()
    expect(screen.getByText('cell-sec4b')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Launch Investigation Workspace/i })).toBeInTheDocument()
  })

  it('renders ErrorState when API request fails', async () => {
    vi.spyOn(apiClient, 'get').mockRejectedValue(
      new ApiClientError('Failed to fetch from backend', 500)
    )

    renderIncidentExplorer()

    expect(await screen.findByText('Failed to Load Incidents')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Retry Request/i })).toBeInTheDocument()
  })

  it('renders EmptyState and allows resetting filters', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'get').mockResolvedValue(MOCK_INCIDENT_LIST_RESPONSE)

    renderIncidentExplorer()

    const searchInput = await screen.findByLabelText(/Search incidents/i)
    await act(async () => {
      await user.type(searchInput, 'NONEXISTENT_QUERY_XZY')
    })

    expect(await screen.findByText('No Incidents Found')).toBeInTheDocument()

    const resetBtn = screen.getByRole('button', { name: /Reset All Filters/i })
    await act(async () => {
      await user.click(resetBtn)
    })

    // All records should be restored
    expect(await screen.findByText('INC-2026-0001')).toBeInTheDocument()
  })
})
