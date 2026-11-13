import { describe, it, expect, beforeEach } from 'vitest'
import { useIncidentContextStore } from '../store/incidentContextStore'

describe('IncidentContextStore Shared State & Context Preservation', () => {
  beforeEach(() => {
    useIncidentContextStore.getState().resetFilters()
    useIncidentContextStore.getState().setSelectedIncidentId(null)
    localStorage.clear()
    sessionStorage.clear()
  })

  it('initializes with default filter and pagination values', () => {
    const state = useIncidentContextStore.getState()
    expect(state.search).toBe('')
    expect(state.domain).toBe('ALL')
    expect(state.severity).toBe('ALL')
    expect(state.status).toBe('ALL')
    expect(state.page).toBe(1)
    expect(state.limit).toBe(20)
    expect(state.sortBy).toBe('created_at')
    expect(state.sortOrder).toBe('desc')
    expect(state.selectedIncidentId).toBeNull()
  })

  it('updates selectedIncidentId without touching storage', () => {
    useIncidentContextStore.getState().setSelectedIncidentId('INC-2026-0042')
    expect(useIncidentContextStore.getState().selectedIncidentId).toBe('INC-2026-0042')

    // Invariant: Zero storage pollution
    expect(localStorage.getItem('token')).toBeNull()
    expect(sessionStorage.getItem('token')).toBeNull()
  })

  it('resets page to 1 whenever search query changes', () => {
    useIncidentContextStore.getState().setPage(5)
    expect(useIncidentContextStore.getState().page).toBe(5)

    useIncidentContextStore.getState().setSearch('gNodeB')
    expect(useIncidentContextStore.getState().search).toBe('gNodeB')
    expect(useIncidentContextStore.getState().page).toBe(1)
  })

  it('resets all filters back to default values on resetFilters()', () => {
    const store = useIncidentContextStore.getState()
    store.setSearch('test')
    store.setDomain('RAN')
    store.setSeverity('CRITICAL')
    store.setStatus('ACTIVE')
    store.setPage(3)
    store.setLimit(50)

    useIncidentContextStore.getState().resetFilters()

    const refreshed = useIncidentContextStore.getState()
    expect(refreshed.search).toBe('')
    expect(refreshed.domain).toBe('ALL')
    expect(refreshed.severity).toBe('ALL')
    expect(refreshed.status).toBe('ALL')
    expect(refreshed.page).toBe(1)
    expect(refreshed.limit).toBe(20)
  })
})
