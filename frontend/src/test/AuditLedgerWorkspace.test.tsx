import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuditLedgerPage } from '../pages/AuditLedgerPage'
import { apiClient, ApiClientError } from '../api/client'

const MOCK_SUMMARY = {
  total_records: 3,
  latest_sequence: 3,
  earliest_timestamp: '2026-11-04T10:00:00Z',
  latest_timestamp: '2026-11-04T10:15:00Z',
  actions_breakdown: {
    APPROVED: 1,
    REJECTED: 1,
    SUBMITTED: 1,
  },
  anchor_present: true,
  anchor_sequence: 3,
  anchor_hash: '3333ffff4444bbbb',
  storage_type: 'JSONL_APPEND_ONLY',
  canonicalization_scheme: 'RFC_8785_JCS',
  hashing_algorithm: 'SHA_256',
  mac_algorithm: 'HMAC_SHA256',
  anchor_mechanism: 'FileBasedCheckpointAnchor (Local Monotonic Parity)',
  limitations: [
    'Audit ledger persistence and verification is single-process local to this host.',
  ],
}

const MOCK_RECORDS = {
  total_count: 3,
  limit: 10,
  offset: 0,
  items: [
    {
      sequence_number: 3,
      entry_hash: '9a4f21e8b19c888877776666555544443333222211110000',
      prev_hash: '4b78c901aa32777788889999000011112222333344445555',
      operator_id: 'manager_bob',
      decision: 'REJECTED',
      recommendation_id: 'REC-002',
      timestamp: '2026-11-04T10:15:00Z',
      schema_version: '1.0.0',
      has_hmac: true,
      audit_id: 'AUD-0003',
      action: 'REJECTED',
      incident_id: 'INC-101',
      reviewer_role: 'INCIDENT_MANAGER',
      notes: 'Rejected due to scheduled maintenance window.',
      hmac_signature: 'hmac_sig_3_hex_digest',
      reviewer_auth_hash: 'auth_hash_bob_thumbprint',
    },
    {
      sequence_number: 2,
      entry_hash: '4b78c901aa32777788889999000011112222333344445555',
      prev_hash: '11c890deaf10666655554444333322221111000099998888',
      operator_id: 'operator_alice',
      decision: 'APPROVED',
      recommendation_id: 'REC-001',
      timestamp: '2026-11-04T10:10:00Z',
      schema_version: '1.0.0',
      has_hmac: true,
      audit_id: 'AUD-0002',
      action: 'APPROVED',
      incident_id: 'INC-101',
      reviewer_role: 'NOC_L2',
      notes: 'Approved after verifying optical power telemetry.',
      hmac_signature: 'hmac_sig_2_hex_digest',
      reviewer_auth_hash: 'auth_hash_alice_thumbprint',
    },
    {
      sequence_number: 1,
      entry_hash: '11c890deaf10666655554444333322221111000099998888',
      prev_hash: 'GENESIS_CHECKPOINT',
      operator_id: 'system:causal_reasoner',
      decision: 'SUBMITTED',
      recommendation_id: 'REC-001',
      timestamp: '2026-11-04T10:00:00Z',
      schema_version: '1.0.0',
      has_hmac: true,
      audit_id: 'AUD-0001',
      action: 'SUBMITTED',
      incident_id: 'INC-101',
      reviewer_role: 'SERVICE_PRINCIPAL',
      notes: null,
      hmac_signature: 'hmac_sig_1_hex_digest',
    },
  ],
}

const MOCK_VERIFY_SUCCESS = {
  is_valid: true,
  verification_status: 'VERIFIED',
  total_records: 3,
  records_checked: 3,
  first_sequence: 1,
  last_sequence: 3,
  latest_sequence: 3,
  latest_hash: '9a4f21e8b19c8888...',
  hash_chain_valid: true,
  jcs_canonicalization_valid: true,
  hmac_signatures_valid: true,
  checkpoint_parity_valid: true,
  anchor_present: true,
  anchor_sequence: 3,
  anchor_hash: '3333ffff4444bbbb',
  errors: [],
  verified_at: '2026-11-04T10:16:00Z',
  verification_scope: 'FULL_LEDGER',
  limitations: [
    'Verification is local to this single-process node.',
  ],
}

const MOCK_VERIFY_FAILED = {
  is_valid: false,
  verification_status: 'FAILED',
  total_records: 3,
  records_checked: 3,
  latest_sequence: 3,
  latest_hash: '000000000000...',
  hash_chain_valid: false,
  jcs_canonicalization_valid: false,
  hmac_signatures_valid: true,
  checkpoint_parity_valid: false,
  anchor_present: true,
  anchor_sequence: 2,
  errors: [
    'Broken hash chain at AUD-0002: previous_entry_sha256 mismatch',
    'External checkpoint anchor mismatch: ledger is at sequence 3 but anchor is at sequence 2',
  ],
  verified_at: '2026-11-04T10:16:00Z',
  verification_scope: 'FULL_LEDGER',
  limitations: [],
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

const renderAuditLedger = () => {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AuditLedgerPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('AuditLedgerPage Workspace & Provenance Integrity', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders workspace title and high-level ledger overview metrics', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/audit/summary')) return MOCK_SUMMARY
      if (url.includes('/api/v1/audit/records')) return MOCK_RECORDS
      return {}
    })

    renderAuditLedger()

    expect(screen.getByText('Audit Ledger Workspace')).toBeInTheDocument()
    expect(screen.getByText('READ-ONLY DECISION SUPPORT')).toBeInTheDocument()

    // Screen 1: Overview metrics
    expect(await screen.findByText('Total Ledger Blocks')).toBeInTheDocument()
    const sequenceBadges = await screen.findAllByText('#3')
    expect(sequenceBadges.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('RFC 8785 (JCS)')).toBeInTheDocument()
  })

  it('renders audit record explorer table with actual ledger records and epistemic badges', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/audit/summary')) return MOCK_SUMMARY
      if (url.includes('/api/v1/audit/records')) return MOCK_RECORDS
      return {}
    })

    renderAuditLedger()

    // Assert sequence numbers rendered
    expect(await screen.findByText('#000003')).toBeInTheDocument()
    expect(screen.getByText('#000002')).toBeInTheDocument()
    expect(screen.getByText('#000001')).toBeInTheDocument()

    // Assert actor principals and actions
    expect(screen.getByText('manager_bob')).toBeInTheDocument()
    expect(screen.getByText('operator_alice')).toBeInTheDocument()
    expect(screen.getByText('system:causal_reasoner')).toBeInTheDocument()

    // Assert epistemic badge for human-approved decision
    expect(screen.getAllByText('[HUMAN-APPROVED DECISION]').length).toBeGreaterThan(0)
  })

  it('filters records by text search input', async () => {
    const user = userEvent.setup()
    const getSpy = vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/audit/summary')) return MOCK_SUMMARY
      if (url.includes('/api/v1/audit/records')) return MOCK_RECORDS
      return {}
    })

    renderAuditLedger()
    await screen.findByText('#000003')

    const searchInput = screen.getByPlaceholderText('Filter by Incident ID...')
    await user.type(searchInput, 'INC-101')

    await waitFor(() => {
      expect(getSpy).toHaveBeenCalledWith(
        expect.stringContaining('incident_id=INC-101')
      )
    })
  })

  it('filters records by action dropdown selector', async () => {
    const user = userEvent.setup()
    const getSpy = vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/audit/summary')) return MOCK_SUMMARY
      if (url.includes('/api/v1/audit/records')) return MOCK_RECORDS
      return {}
    })

    renderAuditLedger()
    await screen.findByText('#000003')

    const actionSelect = screen.getByRole('combobox')
    await user.selectOptions(actionSelect, 'APPROVED')

    await waitFor(() => {
      expect(getSpy).toHaveBeenCalledWith(
        expect.stringContaining('action=APPROVED')
      )
    })
  })

  it('opens record detail drawer upon clicking a ledger row', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/audit/summary')) return MOCK_SUMMARY
      if (url.includes('/api/v1/audit/records')) return MOCK_RECORDS
      return {}
    })

    renderAuditLedger()
    const row = await screen.findByText('#000002')
    await user.click(row)

    // Screen 3: Detail Drawer appears
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Audit Block #2')).toBeInTheDocument()
    expect(screen.getAllByText(/Approved after verifying optical power telemetry/i).length).toBeGreaterThan(0)
    expect(screen.getByText('RFC 8785 Canonical JSON Serialization (JCS)')).toBeInTheDocument()
  })

  it('renders initial NOT YET VERIFIED state and runs cryptographic verification on demand', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/audit/summary')) return MOCK_SUMMARY
      if (url.includes('/api/v1/audit/records')) return MOCK_RECORDS
      if (url.includes('/api/v1/audit/verify')) return MOCK_VERIFY_SUCCESS
      return {}
    })

    renderAuditLedger()

    // Screen 4: Initial state is NOT YET VERIFIED
    expect(await screen.findByText('NOT YET VERIFIED')).toBeInTheDocument()

    // Click verify button
    const verifyBtn = screen.getByRole('button', { name: /Run Cryptographic Verification/i })
    await user.click(verifyBtn)

    // Verification succeeds
    expect(await screen.findByText('VERIFIED & INTACT')).toBeInTheDocument()
    expect(screen.getByText('MONOTONIC & UNBROKEN')).toBeInTheDocument()
    expect(screen.getByText('SYNCHRONIZED HEAD')).toBeInTheDocument()
  })

  it('displays explicit FAILED status and diagnostic error list when verification fails', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/audit/summary')) return MOCK_SUMMARY
      if (url.includes('/api/v1/audit/records')) return MOCK_RECORDS
      if (url.includes('/api/v1/audit/verify')) return MOCK_VERIFY_FAILED
      return {}
    })

    renderAuditLedger()

    const verifyBtn = await screen.findByRole('button', { name: /Run Cryptographic Verification/i })
    await user.click(verifyBtn)

    expect(await screen.findByText('INTEGRITY FAILED')).toBeInTheDocument()
    expect(screen.getByText('BROKEN HASH LINK')).toBeInTheDocument()
    expect(screen.getByText('ANCHOR DESYNCHRONIZED')).toBeInTheDocument()
    expect(
      screen.getByText('Broken hash chain at AUD-0002: previous_entry_sha256 mismatch')
    ).toBeInTheDocument()
  })

  it('renders honest empty state when 0 audit records exist in genesis state', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/audit/summary')) {
        return { ...MOCK_SUMMARY, total_records: 0, latest_sequence: 0 }
      }
      if (url.includes('/api/v1/audit/records')) {
        return { total_count: 0, limit: 10, offset: 0, items: [] }
      }
      return {}
    })

    renderAuditLedger()

    expect(await screen.findByText('No Audit Records Found')).toBeInTheDocument()
    expect(
      await screen.findByText(/The audit ledger is currently empty \(Genesis state\)/i)
    ).toBeInTheDocument()
  })

  it('renders ErrorState with retry button when backend API is unreachable', async () => {
    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/audit/summary')) return MOCK_SUMMARY
      if (url.includes('/api/v1/audit/records')) {
        throw new ApiClientError('Connection refused: PIIS backend offline', 0)
      }
      return {}
    })

    renderAuditLedger()

    expect(await screen.findByText('Backend Service Unreachable')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Retry Request/i })).toBeInTheDocument()
  })

  it('displays UNAVAILABLE status when cryptographic key or anchor is missing', async () => {
    const user = userEvent.setup()
    const mockUnavailable = {
      is_valid: false,
      verification_status: 'UNAVAILABLE',
      total_records: 3,
      records_checked: 3,
      first_sequence: 1,
      last_sequence: 3,
      latest_sequence: 3,
      latest_hash: '3333ffff4444bbbb',
      hash_chain_valid: true,
      jcs_canonicalization_valid: true,
      hmac_signatures_valid: false,
      checkpoint_parity_valid: false,
      anchor_present: false,
      anchor_sequence: null,
      anchor_hash: null,
      error: 'HMAC signing key unavailable; cryptographic signature verification cannot be performed.',
      errors: [
        'HMAC signing key unavailable; cryptographic signature verification cannot be performed.',
      ],
      verified_at: '2026-11-04T10:30:00Z',
      verification_scope: 'FULL_LEDGER',
      limitations: ['Verification is local to this single-process node.'],
    }

    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/audit/summary')) return MOCK_SUMMARY
      if (url.includes('/api/v1/audit/records')) return MOCK_RECORDS
      if (url.includes('/api/v1/audit/verify')) return mockUnavailable
      return {}
    })

    renderAuditLedger()

    const verifyBtn = await screen.findByRole('button', { name: /Run Cryptographic Verification/i })
    await user.click(verifyBtn)

    expect(await screen.findByText('VERIFICATION UNAVAILABLE')).toBeInTheDocument()
    expect(
      screen.getByText('HMAC signing key unavailable; cryptographic signature verification cannot be performed.')
    ).toBeInTheDocument()
  })

  it('displays INCOMPLETE status when truncated records are detected', async () => {
    const user = userEvent.setup()
    const mockIncomplete = {
      is_valid: false,
      verification_status: 'INCOMPLETE',
      total_records: 3,
      records_checked: 2,
      first_sequence: 1,
      last_sequence: 2,
      latest_sequence: 2,
      latest_hash: '2222ffff',
      hash_chain_valid: true,
      jcs_canonicalization_valid: true,
      hmac_signatures_valid: true,
      checkpoint_parity_valid: true,
      anchor_present: true,
      anchor_sequence: 3,
      anchor_hash: '3333ffff',
      error: 'Malformed or truncated record in disk ledger at line 3',
      errors: ['Malformed or truncated record in disk ledger at line 3: unexpected EOF'],
      verified_at: '2026-11-04T10:30:00Z',
      verification_scope: 'FULL_LEDGER',
      limitations: ['Verification is local to this single-process node.'],
    }

    vi.spyOn(apiClient, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/v1/audit/summary')) return MOCK_SUMMARY
      if (url.includes('/api/v1/audit/records')) return MOCK_RECORDS
      if (url.includes('/api/v1/audit/verify')) return mockIncomplete
      return {}
    })

    renderAuditLedger()

    const verifyBtn = await screen.findByRole('button', { name: /Run Cryptographic Verification/i })
    await user.click(verifyBtn)

    expect(await screen.findByText('INCOMPLETE LEDGER')).toBeInTheDocument()
    expect(
      screen.getByText('Malformed or truncated record in disk ledger at line 3: unexpected EOF')
    ).toBeInTheDocument()
  })
})
