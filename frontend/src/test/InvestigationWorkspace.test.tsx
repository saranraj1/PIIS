import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { InvestigationPage } from '../pages/InvestigationPage'
import { apiClient, ApiClientError } from '../api/client'
import { useIncidentContextStore } from '../store/incidentContextStore'
import {
  MOCK_INCIDENT_LIST_RESPONSE,
  MOCK_DETAIL_RESPONSE,
  MOCK_INVESTIGATION_RESPONSE,
  MOCK_STALE_INVESTIGATION_RESPONSE,
  MOCK_EMPTY_INVESTIGATION_RESPONSE,
  MOCK_EVIDENCE_ITEMS,
  MOCK_HYPOTHESES,
  MOCK_RECOMMENDATIONS,
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

const renderInvestigationWorkspace = (initialEntries = ['/investigation?id=INC-2026-0001']) => {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route path="/investigation" element={<InvestigationPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

const setupApiMocks = (overrides?: {
  investigation?: unknown
  hypotheses?: unknown
  evidence?: unknown
  recommendations?: unknown
  detail?: unknown
}) => {
  vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
    if (url.endsWith('/hypotheses')) return overrides?.hypotheses ?? MOCK_HYPOTHESES
    if (url.endsWith('/evidence')) return overrides?.evidence ?? MOCK_EVIDENCE_ITEMS
    if (url.endsWith('/recommendations')) return overrides?.recommendations ?? MOCK_RECOMMENDATIONS
    if (url.endsWith('/investigation')) return overrides?.investigation ?? MOCK_INVESTIGATION_RESPONSE
    if (url.includes('/api/v1/incidents/INC-')) return overrides?.detail ?? MOCK_DETAIL_RESPONSE
    if (url.startsWith('/api/v1/incidents')) return MOCK_INCIDENT_LIST_RESPONSE
    return {}
  })
}

describe('InvestigationPage Investigation Workspace', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    useIncidentContextStore.getState().setSelectedIncidentId('INC-2026-0001')
  })

  it('renders incident context header with actual backend fields', async () => {
    setupApiMocks()

    renderInvestigationWorkspace()

    // 1. Verify Incident Header Information
    expect(await screen.findByText('INC-2026-0001')).toBeInTheDocument()
    expect(screen.getByText('High VSWR on 5G NR Sector 4B')).toBeInTheDocument()
    expect(screen.getAllByText('CRITICAL').length).toBeGreaterThan(0)
    expect(screen.getAllByText('RAN').length).toBeGreaterThan(0)
    expect(screen.getByText('ACTIVE TICKET')).toBeInTheDocument()
    expect(screen.getByText('14,500')).toBeInTheDocument() // Subscribers
  })

  it('renders evidence sufficiency banner when evidence is sufficient', async () => {
    setupApiMocks({ investigation: MOCK_INVESTIGATION_RESPONSE })

    renderInvestigationWorkspace()

    expect(await screen.findByText('EVIDENCE SUFFICIENT & FRESH')).toBeInTheDocument()
  })

  it('renders safe abstention warnings for stale, missing, and contradictory signals', async () => {
    setupApiMocks({ investigation: MOCK_STALE_INVESTIGATION_RESPONSE })

    renderInvestigationWorkspace()

    expect(await screen.findByText(/SAFE ABSTENTION ENFORCED/i)).toBeInTheDocument()
    expect(screen.getByText(/Stale Telemetry/i)).toBeInTheDocument()
    expect(screen.getByText(/Missing Signals/i)).toBeInTheDocument()
    expect(screen.getAllByText(/Contradictory Signals/i).length).toBeGreaterThan(0)
  })

  it('renders ranked hypotheses with confidence proxies, rationale, and epistemic tags', async () => {
    setupApiMocks()

    renderInvestigationWorkspace()

    expect(await screen.findByText('HYP-001')).toBeInTheDocument()
    expect(screen.getByText(/Physical Feeder Jumper Connector Water Ingress/i)).toBeInTheDocument()
    expect(screen.getByText('88%')).toBeInTheDocument() // 0.88 confidence proxy
    expect(screen.getByText('SUPPORTED')).toBeInTheDocument()
    expect(screen.getByText('HYP-002')).toBeInTheDocument()
    expect(screen.getByText('REJECTED')).toBeInTheDocument()
  })

  it('renders honest empty state when 0 hypotheses returned (safe abstention)', async () => {
    setupApiMocks({
      hypotheses: [],
      investigation: MOCK_EMPTY_INVESTIGATION_RESPONSE,
    })

    renderInvestigationWorkspace()

    expect(await screen.findByText('No Confident Root Cause Hypothesis')).toBeInTheDocument()
    expect(screen.getByText(/Engine safely abstained from candidate ranking/i)).toBeInTheDocument()
  })

  it('renders evidence register tab with evidence items, trust levels, and raw metadata', async () => {
    const user = userEvent.setup()
    setupApiMocks()

    renderInvestigationWorkspace()

    // Click Evidence Register tab
    const evidenceTab = await screen.findByRole('button', { name: /Evidence Register/i })
    await user.click(evidenceTab)

    expect(await screen.findByText('EVID-001')).toBeInTheDocument()
    expect(screen.getByText('EVID-002')).toBeInTheDocument()
    expect(screen.getByText('EVID-003')).toBeInTheDocument()
    expect(screen.getByText('EVID-004')).toBeInTheDocument()
    expect(screen.getByText(/Do not infer verification from the mere presence of an evidence record/i)).toBeInTheDocument()
  })

  it('renders diagnostic recommendations tab with runbooks and approval status', async () => {
    const user = userEvent.setup()
    setupApiMocks()

    renderInvestigationWorkspace()

    const recsTab = await screen.findByRole('button', { name: /Recommendations & Approval/i })
    await user.click(recsTab)

    expect(await screen.findByText('REC-001')).toBeInTheDocument()
    expect(screen.getByText('READ ONLY SAFE')).toBeInTheDocument()
    expect(screen.getByText('PENDING REVIEW')).toBeInTheDocument()
    expect(screen.getByText('REC-002')).toBeInTheDocument()
    expect(screen.getByText('APPROVED')).toBeInTheDocument()
    expect(screen.getByText('noc_lead_taylor@telecom.net')).toBeInTheDocument()
  })

  it('renders chronological investigation timeline with genuine timestamps', async () => {
    const user = userEvent.setup()
    setupApiMocks()

    renderInvestigationWorkspace()

    const timelineTab = await screen.findByRole('button', { name: /Investigation Timeline/i })
    await user.click(timelineTab)

    expect(await screen.findByText('Canonical Normalization & Envelope Validation')).toBeInTheDocument()
    expect(screen.getByText('Automated Multi-Source Investigation Executed')).toBeInTheDocument()
    expect(screen.getByText(/Human Review: REC-002/i)).toBeInTheDocument()
  })

  it('navigates to evidence tab when clicking supporting evidence chip from hypothesis', async () => {
    const user = userEvent.setup()
    setupApiMocks()

    renderInvestigationWorkspace()

    // Click on supporting evidence tag EVID-001 on Hypothesis 1
    const evidChip = await screen.findByRole('button', { name: /EVID-001/i })
    await user.click(evidChip)

    // Should now be on the Evidence Register tab
    expect(await screen.findByText(/Integrity Guard: Do not infer verification/i)).toBeInTheDocument()
    expect(screen.getByText('EVID-001')).toBeInTheDocument()
  })

  it('renders ErrorState and allows retry when investigation API fails', async () => {
    vi.spyOn(apiClient, 'get').mockRejectedValue(
      new ApiClientError('Backend Gateway Timeout', 504)
    )

    renderInvestigationWorkspace()

    expect(await screen.findByText('Failed to Load Investigation Context')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Retry Request/i })).toBeInTheDocument()
  })

  it('renders ungenerated state and allows deliberate trigger when investigation is not yet generated', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.endsWith('/investigation')) {
        throw new ApiClientError(
          "Investigation not yet generated for incident 'INC-2026-0001'. Trigger investigation via POST /api/v1/incidents/INC-2026-0001/investigate.",
          404,
          undefined,
          'INVESTIGATION_NOT_YET_GENERATED'
        )
      }
      if (url.includes('/api/v1/incidents/INC-')) return MOCK_DETAIL_RESPONSE
      if (url.startsWith('/api/v1/incidents')) return MOCK_INCIDENT_LIST_RESPONSE
      return {}
    })

    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue(MOCK_INVESTIGATION_RESPONSE)

    renderInvestigationWorkspace()

    // 1. Should render deliberate ungenerated state rather than generic error
    expect(await screen.findByText('Investigation Not Yet Generated')).toBeInTheDocument()
    expect(screen.getByText('Status: Not Initiated')).toBeInTheDocument()
    expect(
      screen.getByText(/In accordance with read-only operational boundaries/i)
    ).toBeInTheDocument()

    // 2. Click Trigger Investigation button
    const triggerBtn = screen.getByRole('button', { name: /Trigger Investigation/i })
    await user.click(triggerBtn)

    // 3. Verifies deliberate POST call made with exact endpoint
    expect(postSpy).toHaveBeenCalledWith('/api/v1/incidents/INC-2026-0001/investigate')
  })

  it('distinguishes incident not found from ungenerated investigation', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/incidents/INC-')) {
        throw new ApiClientError(
          "Incident 'INC-2026-0001' not found",
          404,
          undefined,
          'INCIDENT_NOT_FOUND'
        )
      }
      return {}
    })

    renderInvestigationWorkspace()

    expect(await screen.findByText("Incident 'INC-2026-0001' not found")).toBeInTheDocument()
    expect(screen.queryByText('Investigation Not Yet Generated')).not.toBeInTheDocument()
  })
})
