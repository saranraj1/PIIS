import { create } from 'zustand'

export interface IncidentFilterState {
  search: string
  domain: string
  severity: string
  status: string
  page: number
  limit: number
  sortBy: 'created_at' | 'severity' | 'incident_id'
  sortOrder: 'asc' | 'desc'
}

interface IncidentContextStoreState extends IncidentFilterState {
  selectedIncidentId: string | null
  setSelectedIncidentId: (id: string | null) => void
  setSearch: (search: string) => void
  setDomain: (domain: string) => void
  setSeverity: (severity: string) => void
  setStatus: (status: string) => void
  setPage: (page: number) => void
  setLimit: (limit: number) => void
  setSorting: (sortBy: 'created_at' | 'severity' | 'incident_id', sortOrder: 'asc' | 'desc') => void
  resetFilters: () => void
}

const getInitialPageLimit = (): number => {
  if (typeof window !== 'undefined') {
    try {
      const stored = localStorage.getItem('piis_page_size')
      if (stored) {
        const parsed = parseInt(stored, 10)
        if (!isNaN(parsed) && parsed > 0) return parsed
      }
    } catch {
      // Ignore storage restrictions
    }
  }
  return 20
}

const DEFAULT_FILTERS: IncidentFilterState = {
  search: '',
  domain: 'ALL',
  severity: 'ALL',
  status: 'ALL',
  page: 1,
  limit: getInitialPageLimit(),
  sortBy: 'created_at',
  sortOrder: 'desc',
}

export const useIncidentContextStore = create<IncidentContextStoreState>((set) => ({
  ...DEFAULT_FILTERS,
  selectedIncidentId: null,

  setSelectedIncidentId: (id) => set({ selectedIncidentId: id }),

  setSearch: (search) => set({ search, page: 1 }),

  setDomain: (domain) => set({ domain, page: 1 }),

  setSeverity: (severity) => set({ severity, page: 1 }),

  setStatus: (status) => set({ status, page: 1 }),

  setPage: (page) => set({ page }),

  setLimit: (limit) => set({ limit, page: 1 }),

  setSorting: (sortBy, sortOrder) => set({ sortBy, sortOrder }),

  resetFilters: () => set({ ...DEFAULT_FILTERS }),
}))
