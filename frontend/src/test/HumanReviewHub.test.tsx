import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '../auth/AuthContext'
import { HumanReviewPage } from '../pages/HumanReviewPage'
import { apiClient, ApiClientError } from '../api/client'
import { useIncidentContextStore } from '../store/incidentContextStore'
import type { ReviewQueueResponse, ReviewResponse, InvestigationResponse } from '../api/types'

const MOCK_REVIEW_QUEUE: ReviewQueueResponse = {
  items: [
    {
      recommendation_id: 'REC-001',
      incident_id: 'INC-2026-0001',
      incident_title: 'Degraded Throughput on Sector 4A',
      incident_severity: 'MAJOR',
      network_domain: 'RAN',
      description: 'Perform physical feeder line inspection and VSWR sweep',
      reason: 'VSWR spike observed in telemetry',
      supporting_evidence_ids: ['EVID-001'],
      source_runbook_id: 'SOP-RAN-VSWR-001',
      source_section: 'Section 2.1: Feeder Sweep',
      risk_classification: 'READ_ONLY_SAFE',
      human_approval_required: true,
      approval_status: 'PENDING_REVIEW',
      is_sufficient: true,
      has_contradictions: false,
      has_missing_evidence: false,
      created_at: '2026-11-03T10:00:00Z',
    },
    {
      recommendation_id: 'REC-002',
      incident_id: 'INC-2026-0002',
      incident_title: 'Core UPF N3 Tunnel Drop',
      incident_severity: 'CRITICAL',
      network_domain: '5G_CORE',
      description: 'Capture N3 interface GTP-U telemetry dump',
      reason: 'Packet drop alert on N3 interface',
      supporting_evidence_ids: ['EVID-002'],
      source_runbook_id: 'SOP-CORE-UPF-001',
      source_section: 'Section 3.2: Packet Capture',
      risk_classification: 'LOW_OBSERVABILITY',
      human_approval_required: true,
      approval_status: 'PENDING_REVIEW',
      is_sufficient: false,
      has_contradictions: true,
      has_missing_evidence: true,
      created_at: '2026-11-03T11:00:00Z',
    },
  ],
  total_count: 2,
  pending_count: 2,
  approved_count: 0,
  rejected_count: 0,
  limit: 50,
  offset: 0,
}

const MOCK_INVESTIGATION: InvestigationResponse = {
  incident_id: 'INC-2026-0001',
  title: 'Degraded Throughput on Sector 4A',
  network_domain: 'RAN',
  created_at: '2026-11-03T10:00:00Z',
  is_sufficient: true,
  missing_evidence: [],
  contradictions: [],
  stale_evidence: [],
  is_transient_event: false,
  hypotheses_count: 1,
  hypotheses: [
    {
      hypothesis_id: 'HYP-001',
      description: 'Feeder line degradation causing elevated VSWR reflection',
      supporting_evidence_ids: ['EVID-001'],
      contradicting_evidence_ids: [],
      evidence_source: 'ML_CORRELATION',
      confidence_proxy: 0.88,
      confidence_rationale: 'Telemetry spike matches feeder impairment pattern',
      status: 'SUPPORTED',
    },
  ],
  recommendations: [],
  epistemic_status: 'EVALUATED',
  correlation_id: 'CORR-TEST-001',
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

const renderHumanReviewHub = () => {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={['/human-review']}>
          <Routes>
            <Route path="/human-review" element={<HumanReviewPage />} />
            <Route path="/investigation" element={<div data-testid="investigation-page">Investigation Workspace Page</div>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}

describe('HumanReviewPage & Human Review Hub', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useIncidentContextStore.getState().resetFilters()
    useIncidentContextStore.getState().setSelectedIncidentId(null)
  })

  it('renders governance notice banner and summary queue metrics', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/incidents/reviews/queue')) {
        return MOCK_REVIEW_QUEUE
      }
      if (url.includes('/investigation')) {
        return MOCK_INVESTIGATION
      }
      return {}
    })

    renderHumanReviewHub()

    // 1. Governance notice
    expect(
      await screen.findByText(/Human Review Gateway & Decision Notarization/i)
    ).toBeInTheDocument()
    expect(
      screen.getByText(/PIIS remains strictly an analytical and advisory decision-support platform/i)
    ).toBeInTheDocument()

    // 2. Metrics bar
    expect(screen.getByText('Total Queue')).toBeInTheDocument()
    expect(screen.getAllByText('Pending').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Approved').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Rejected').length).toBeGreaterThan(0)
  })

  it('renders queue recommendation items and auto-selects first item', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/incidents/reviews/queue')) {
        return MOCK_REVIEW_QUEUE
      }
      if (url.includes('/investigation')) {
        return MOCK_INVESTIGATION
      }
      return {}
    })

    renderHumanReviewHub()

    // First recommendation displayed in queue
    const rec1Matches = await screen.findAllByText('REC-001')
    expect(rec1Matches.length).toBeGreaterThan(0)
    expect(screen.getByText('REC-002')).toBeInTheDocument()

    // Auto-selected item rendered in workspace
    expect(
      screen.getAllByText('Perform physical feeder line inspection and VSWR sweep').length
    ).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('SOP-RAN-VSWR-001')).toBeInTheDocument()
    expect(screen.getByText(/Section 2.1: Feeder Sweep/i)).toBeInTheDocument()
  })

  it('displays contradiction and missing evidence alerts when present', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/incidents/reviews/queue')) {
        return MOCK_REVIEW_QUEUE
      }
      if (url.includes('/investigation')) {
        return MOCK_INVESTIGATION
      }
      return {}
    })

    const user = userEvent.setup()
    renderHumanReviewHub()

    // Click REC-002 (which has contradictions & missing evidence)
    const rec2Card = await screen.findByText('REC-002')
    await user.click(rec2Card)

    // Verify contradiction alert is rendered
    expect(
      await screen.findByText(/Contradictory Telemetry Signals Detected/i)
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Conflicting evidence exists in the incident evidence register/i)
    ).toBeInTheDocument()

    // Verify missing telemetry alert is rendered
    expect(
      screen.getByText(/Incomplete Telemetry Windows:/i)
    ).toBeInTheDocument()
  })

  it('validates mandatory reviewer notes before opening confirmation dialog', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/incidents/reviews/queue')) {
        return MOCK_REVIEW_QUEUE
      }
      if (url.includes('/investigation')) {
        return MOCK_INVESTIGATION
      }
      return {}
    })

    const user = userEvent.setup()
    renderHumanReviewHub()

    const rec1Matches = await screen.findAllByText('REC-001')
    expect(rec1Matches.length).toBeGreaterThan(0)

    // Click submit without entering notes
    const submitBtn = screen.getByRole('button', { name: /Review & Notarize Decision/i })
    await user.click(submitBtn)

    // Validation error displayed
    expect(
      screen.getByText(/Operator technical rationale notes are mandatory/i)
    ).toBeInTheDocument()
  })

  it('submits human review decision and displays cryptographic receipt', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/incidents/reviews/queue')) {
        return MOCK_REVIEW_QUEUE
      }
      if (url.includes('/investigation')) {
        return MOCK_INVESTIGATION
      }
      return {}
    })

    const mockReceipt: ReviewResponse = {
      incident_id: 'INC-2026-0001',
      recommendation_id: 'REC-001',
      decision: 'APPROVED',
      reviewed_by: 'OP-NOC-TEST',
      review_timestamp: '2026-11-03T12:00:00Z',
      audit_entry_hash: 'abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
      ledger_sequence: 42,
      status: 'RECORDED_IN_AUDIT_CHAIN',
      receipt_id: 'RCPT-ABCDEF1234567890',
    }

    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue(mockReceipt)

    const user = userEvent.setup()
    renderHumanReviewHub()

    const rec1Matches = await screen.findAllByText('REC-001')
    expect(rec1Matches.length).toBeGreaterThan(0)

    // Enter technical notes
    const textarea = screen.getByPlaceholderText(/Record technical rationale/i)
    await user.type(textarea, 'Verified VSWR reflection spike; safe for field inspection sweep.')

    // Click submit to open confirmation dialog
    const submitBtn = screen.getByRole('button', { name: /Review & Notarize Decision/i })
    await user.click(submitBtn)

    // Modal opens
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText(/Confirm Human Review Decision/i)).toBeInTheDocument()
    expect(screen.getAllByText(/Verified VSWR reflection spike/i).length).toBeGreaterThanOrEqual(1)

    // Click confirm in modal
    const confirmBtn = screen.getByRole('button', { name: /Confirm & Sign Cryptographically/i })
    await user.click(confirmBtn)

    // Verify POST was called with expected payload
    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        '/api/v1/incidents/INC-2026-0001/reviews',
        {
          recommendation_id: 'REC-001',
          decision: 'APPROVED',
          review_notes: 'Verified VSWR reflection spike; safe for field inspection sweep.',
        }
      )
    })

    // Verify cryptographic receipt rendered
    expect(
      await screen.findByText(/Review Decision Cryptographically Sealed/i)
    ).toBeInTheDocument()
    expect(screen.getByText('RCPT-ABCDEF1234567890')).toBeInTheDocument()
    expect(screen.getByText('#42')).toBeInTheDocument()
  })

  it('handles backend 409 conflict error (duplicate / terminal replay)', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/incidents/reviews/queue')) {
        return MOCK_REVIEW_QUEUE
      }
      if (url.includes('/investigation')) {
        return MOCK_INVESTIGATION
      }
      return {}
    })

    vi.spyOn(apiClient, 'post').mockRejectedValue(
      new ApiClientError('Conflict: already in terminal state', 409)
    )

    const user = userEvent.setup()
    renderHumanReviewHub()

    const rec1Matches = await screen.findAllByText('REC-001')
    expect(rec1Matches.length).toBeGreaterThan(0)

    const textarea = screen.getByPlaceholderText(/Record technical rationale/i)
    await user.type(textarea, 'Attempting duplicate review')

    const submitBtn = screen.getByRole('button', { name: /Review & Notarize Decision/i })
    await user.click(submitBtn)

    const confirmBtn = screen.getByRole('button', { name: /Confirm & Sign Cryptographically/i })
    await user.click(confirmBtn)

    // Error alert displayed
    expect(
      await screen.findByText(/Conflict \(409\): Recommendation is already in a terminal state/i)
    ).toBeInTheDocument()
  })

  it('handles backend 403 forbidden error (service accounts barred / unauthorized role)', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/incidents/reviews/queue')) {
        return MOCK_REVIEW_QUEUE
      }
      if (url.includes('/investigation')) {
        return MOCK_INVESTIGATION
      }
      return {}
    })

    vi.spyOn(apiClient, 'post').mockRejectedValue(
      new ApiClientError('Forbidden: Service principal barred', 403)
    )

    const user = userEvent.setup()
    renderHumanReviewHub()

    const rec1Matches = await screen.findAllByText('REC-001')
    expect(rec1Matches.length).toBeGreaterThan(0)

    const textarea = screen.getByPlaceholderText(/Record technical rationale/i)
    await user.type(textarea, 'Unauthorized review attempt')

    const submitBtn = screen.getByRole('button', { name: /Review & Notarize Decision/i })
    await user.click(submitBtn)

    const confirmBtn = screen.getByRole('button', { name: /Confirm & Sign Cryptographically/i })
    await user.click(confirmBtn)

    expect(
      await screen.findByText(/Forbidden \(403\): You lack operational review privileges/i)
    ).toBeInTheDocument()
  })

  it('filters queue items by search text query', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/incidents/reviews/queue')) {
        return MOCK_REVIEW_QUEUE
      }
      if (url.includes('/investigation')) {
        return MOCK_INVESTIGATION
      }
      return {}
    })

    const user = userEvent.setup()
    renderHumanReviewHub()

    const rec1Matches = await screen.findAllByText('REC-001')
    expect(rec1Matches.length).toBeGreaterThan(0)
    expect(screen.getByText('REC-002')).toBeInTheDocument()

    // Type "UPF" into search bar
    const searchInput = screen.getByPlaceholderText(/Search by REC ID/i)
    await user.type(searchInput, 'UPF')

    // REC-002 matches; REC-001 filtered out from queue list
    expect(screen.getByText('REC-002')).toBeInTheDocument()
    // Select REC-002 in workspace as well
    await user.click(screen.getByText('REC-002'))
    expect(screen.queryByText('REC-001')).not.toBeInTheDocument()
  })

  it('displays empty state when review queue is empty', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/incidents/reviews/queue')) {
        return {
          items: [],
          total_count: 0,
          pending_count: 0,
          approved_count: 0,
          rejected_count: 0,
          limit: 50,
          offset: 0,
        }
      }
      return {}
    })

    renderHumanReviewHub()

    expect(await screen.findByText('Review Queue Empty')).toBeInTheDocument()
    expect(
      screen.getByText(/No actionable diagnostic recommendations currently awaiting review/i)
    ).toBeInTheDocument()
  })

  it('displays restored evidence unavailable alert and blocks approval when evidence is missing', async () => {
    const RESTORED_QUEUE: ReviewQueueResponse = {
      items: [
        {
          recommendation_id: 'REC-RESTORED-999',
          incident_id: 'INC-RESTORED-100',
          incident_title: 'Restored Incident After Reboot',
          incident_severity: 'MAJOR',
          network_domain: 'RAN',
          description: 'Restored diagnostic action from ledger',
          reason: 'Restored from persistent ledger checkpoint',
          supporting_evidence_ids: [],
          source_runbook_id: 'RESTORED_LEDGER',
          source_section: 'RESTORED',
          risk_classification: 'READ_ONLY_SAFE',
          human_approval_required: true,
          approval_status: 'PENDING_REVIEW',
          is_sufficient: false,
          has_contradictions: false,
          has_missing_evidence: true,
          created_at: '2026-11-03T12:00:00Z',
        },
      ],
      total_count: 1,
      pending_count: 1,
      approved_count: 0,
      rejected_count: 0,
      limit: 50,
      offset: 0,
    }

    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/incidents/reviews/queue')) {
        return RESTORED_QUEUE
      }
      return null
    })

    const user = userEvent.setup()
    renderHumanReviewHub()

    // 1. Verify Restored Evidence Unavailable banner is rendered
    expect(
      await screen.findByText('Restored Evidence Context Unavailable')
    ).toBeInTheDocument()
    expect(
      screen.getByText(/This recommendation was restored from a persistent audit ledger checkpoint/i)
    ).toBeInTheDocument()

    // 2. Verify Approval Blocked by Evidence Policy warning is rendered
    expect(
      screen.getByText('Approval Blocked by Evidence Policy')
    ).toBeInTheDocument()

    // 3. Enter notes and attempt to submit approval
    const notesInput = screen.getByLabelText(/Mandatory Technical Rationale/i)
    await user.type(notesInput, 'Attempting approval on restored recommendation without evidence')

    const submitBtn = screen.getByRole('button', { name: /Review & Notarize Decision/i })
    await user.click(submitBtn)

    // 4. Verify validation error blocks modal from opening
    expect(
      screen.getByText(/Approval blocked: Evidence is missing or unavailable/i)
    ).toBeInTheDocument()
    expect(screen.queryByText(/Confirm Human Review Decision/i)).not.toBeInTheDocument()
  })
})
