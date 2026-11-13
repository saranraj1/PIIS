import { create } from 'zustand'

export type InterfaceDensity = 'comfortable' | 'compact'
export type TimezoneMode = 'UTC' | 'LOCAL'
export type TimeFormat = '24H' | '12H'
export type TablePageSize = 10 | 25 | 50
export type AutoRefreshInterval = 'OFF' | '15s' | '30s' | '60s'

export interface DisplayPreferencesState {
  density: InterfaceDensity
  timezone: TimezoneMode
  timeFormat: TimeFormat
  pageSize: TablePageSize
  refreshInterval: AutoRefreshInterval
  setDensity: (density: InterfaceDensity) => void
  setTimezone: (timezone: TimezoneMode) => void
  setTimeFormat: (timeFormat: TimeFormat) => void
  setPageSize: (pageSize: TablePageSize) => void
  setRefreshInterval: (interval: AutoRefreshInterval) => void
  resetToDefaults: () => void
}

const STORAGE_KEYS = {
  DENSITY: 'piis_display_density',
  TIMEZONE: 'piis_timezone_preference',
  TIME_FORMAT: 'piis_time_format',
  PAGE_SIZE: 'piis_page_size',
  REFRESH_INTERVAL: 'piis_refresh_interval',
} as const

export const DEFAULT_PREFERENCES = {
  density: 'comfortable' as InterfaceDensity,
  timezone: 'UTC' as TimezoneMode,
  timeFormat: '24H' as TimeFormat,
  pageSize: 25 as TablePageSize,
  refreshInterval: '30s' as AutoRefreshInterval,
}

const getStoredPreference = <T extends string | number>(key: string, defaultValue: T): T => {
  if (typeof window === 'undefined') return defaultValue
  try {
    const val = localStorage.getItem(key)
    if (val !== null) {
      if (typeof defaultValue === 'number') {
        const num = parseInt(val, 10)
        return (!isNaN(num) ? num : defaultValue) as T
      }
      return val as T
    }
  } catch {
    // Ignore localStorage access restrictions
  }
  return defaultValue
}

const initialDensity = getStoredPreference<InterfaceDensity>(STORAGE_KEYS.DENSITY, DEFAULT_PREFERENCES.density)
if (typeof document !== 'undefined') {
  document.documentElement.setAttribute('data-density', initialDensity)
}

export const useDisplayPreferencesStore = create<DisplayPreferencesState>((set) => ({
  density: initialDensity,
  timezone: getStoredPreference<TimezoneMode>(STORAGE_KEYS.TIMEZONE, DEFAULT_PREFERENCES.timezone),
  timeFormat: getStoredPreference<TimeFormat>(STORAGE_KEYS.TIME_FORMAT, DEFAULT_PREFERENCES.timeFormat),
  pageSize: getStoredPreference<TablePageSize>(STORAGE_KEYS.PAGE_SIZE, DEFAULT_PREFERENCES.pageSize),
  refreshInterval: getStoredPreference<AutoRefreshInterval>(STORAGE_KEYS.REFRESH_INTERVAL, DEFAULT_PREFERENCES.refreshInterval),

  setDensity: (density) => {
    localStorage.setItem(STORAGE_KEYS.DENSITY, density)
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-density', density)
    }
    set({ density })
  },

  setTimezone: (timezone) => {
    localStorage.setItem(STORAGE_KEYS.TIMEZONE, timezone)
    set({ timezone })
  },

  setTimeFormat: (timeFormat) => {
    localStorage.setItem(STORAGE_KEYS.TIME_FORMAT, timeFormat)
    set({ timeFormat })
  },

  setPageSize: (pageSize) => {
    localStorage.setItem(STORAGE_KEYS.PAGE_SIZE, String(pageSize))
    set({ pageSize })
  },

  setRefreshInterval: (refreshInterval) => {
    localStorage.setItem(STORAGE_KEYS.REFRESH_INTERVAL, refreshInterval)
    set({ refreshInterval })
  },

  resetToDefaults: () => {
    localStorage.setItem(STORAGE_KEYS.DENSITY, DEFAULT_PREFERENCES.density)
    localStorage.setItem(STORAGE_KEYS.TIMEZONE, DEFAULT_PREFERENCES.timezone)
    localStorage.setItem(STORAGE_KEYS.TIME_FORMAT, DEFAULT_PREFERENCES.timeFormat)
    localStorage.setItem(STORAGE_KEYS.PAGE_SIZE, String(DEFAULT_PREFERENCES.pageSize))
    localStorage.setItem(STORAGE_KEYS.REFRESH_INTERVAL, DEFAULT_PREFERENCES.refreshInterval)
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-density', DEFAULT_PREFERENCES.density)
    }
    set({ ...DEFAULT_PREFERENCES })
  },
}))
