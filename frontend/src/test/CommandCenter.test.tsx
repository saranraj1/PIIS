import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CommandCenterPage } from '../pages/CommandCenterPage'
import { apiClient, ApiClientError } from '../api/client'
import {
  MOCK_INCIDENT_LIST_RESPONSE,
  MOCK_EMPTY_INCIDENT_LIST_RESPONSE,
  MOCK_HEALTH_RESPONSE,
  MOCK_READY_RESPONSE,
  MOCK_ADAPTERS_RESPONSE,
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

const renderCommandCenter = () => {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <CommandCenterPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('CommandCenterPage Operational Overview', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders operational summary metrics derived from backend responses', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/health')) return MOCK_HEALTH_RESPONSE
      if (url.includes('/api/v1/ready')) return MOCK_READY_RESPONSE
      if (url.includes('/api/v1/incidents')) return MOCK_INCIDENT_LIST_RESPONSE
      if (url.includes('/api/v1/integrations/health')) return MOCK_ADAPTERS_RESPONSE
      return {}
    })

    renderCommandCenter()

    // 1. Operational header & epistemic standards
    expect(await screen.findByText(/NOC Supervisory Command Center/i)).toBeInTheDocument()

    // 2. Metric Cards derived from responses
    expect(await screen.findByText('Total Incidents')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument() // 4 total incidents

    expect(screen.getByText('Critical / High Severity')).toBeInTheDocument()
    expect(screen.getByText(/\/ 1 Major/i)).toBeInTheDocument()
    expect(screen.getByText(/2 high-severity incidents require immediate investigation/i)).toBeInTheDocument()

    // 3. API status card
    expect(screen.getByText('FastAPI Core Status')).toBeInTheDocument()
    expect(screen.getByText(/ONLINE \(READY\)/i)).toBeInTheDocument()

    // 4. Cryptographic audit card
    expect(screen.getByText('Cryptographic Audit Blocks')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument() // 12 audit records

    // 5. Subsystems and transparent simulated labels
    expect(screen.getByText('SIMULATED (LOCAL)')).toBeInTheDocument()
    expect(screen.getByText('LOCAL VERIFIED')).toBeInTheDocument()

    // 6. Distribution Charts
    expect(screen.getByText('Incident Severity Distribution')).toBeInTheDocument()
    expect(screen.getByText('Network Domain Breakdown')).toBeInTheDocument()

    // 7. Recent incident items
    expect(screen.getByText('INC-2026-0001')).toBeInTheDocument()
    expect(screen.getByText('INC-2026-0002')).toBeInTheDocument()
    expect(screen.getByText('High VSWR on 5G NR Sector 4B')).toBeInTheDocument()
  })

  it('renders honest empty state when 0 incidents exist in backend', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/health')) return MOCK_HEALTH_RESPONSE
      if (url.includes('/api/v1/ready')) return { ...MOCK_READY_RESPONSE, incidents_count: 0 }
      if (url.includes('/api/v1/incidents')) return MOCK_EMPTY_INCIDENT_LIST_RESPONSE
      if (url.includes('/api/v1/integrations/health')) return MOCK_ADAPTERS_RESPONSE
      return {}
    })

    renderCommandCenter()

    expect(await screen.findByText('No Ingested Incidents')).toBeInTheDocument()
    expect(screen.getByText(/The backend pipeline currently has no active incidents stored in memory/i)).toBeInTheDocument()
  })

  it('renders ErrorState with retry button when backend API is unreachable', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/health')) return MOCK_HEALTH_RESPONSE
      if (url.includes('/api/v1/ready')) return MOCK_READY_RESPONSE
      if (url.includes('/api/v1/incidents')) {
        throw new ApiClientError('Failed to connect to /api/v1/incidents', 0)
      }
      return {}
    })

    renderCommandCenter()

    expect(await screen.findByText('Backend Service Unreachable')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Retry Request/i })).toBeInTheDocument()
  })
})
