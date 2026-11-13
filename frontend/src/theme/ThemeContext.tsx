import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'

export type Theme = 'dark' | 'light'
export type ThemeMode = 'dark' | 'light' | 'system'

interface ThemeContextType {
  theme: Theme
  themeMode: ThemeMode
  toggleTheme: () => void
  setTheme: (theme: Theme) => void
  setThemeMode: (mode: ThemeMode) => void
}

const THEME_STORAGE_KEY = 'piis_theme_preference'

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

const getSystemTheme = (): Theme => {
  if (typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
    return 'light'
  }
  return 'dark'
}

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [themeMode, setThemeModeState] = useState<ThemeMode>(() => {
    try {
      const saved = localStorage.getItem(THEME_STORAGE_KEY)
      if (saved === 'dark' || saved === 'light' || saved === 'system') {
        return saved
      }
    } catch {
      // Ignore storage restrictions
    }
    return 'dark'
  })

  const [systemIsLight, setSystemIsLight] = useState<boolean>(() => {
    if (typeof window !== 'undefined' && window.matchMedia) {
      return window.matchMedia('(prefers-color-scheme: light)').matches
    }
    return false
  })

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const mediaQuery = window.matchMedia('(prefers-color-scheme: light)')
    const handleChange = (e: MediaQueryListEvent) => {
      setSystemIsLight(e.matches)
    }
    mediaQuery.addEventListener?.('change', handleChange)
    return () => mediaQuery.removeEventListener?.('change', handleChange)
  }, [])

  const theme: Theme = themeMode === 'system' ? (systemIsLight ? 'light' : 'dark') : themeMode

  useEffect(() => {
    const root = document.documentElement
    if (theme === 'dark') {
      root.classList.add('dark')
      root.setAttribute('data-theme', 'dark')
    } else {
      root.classList.remove('dark')
      root.setAttribute('data-theme', 'light')
    }
    try {
      localStorage.setItem(THEME_STORAGE_KEY, themeMode)
    } catch {
      // Ignore storage restrictions
    }
  }, [theme, themeMode])

  const toggleTheme = useCallback(() => {
    setThemeModeState((prev) => {
      const currentResolved = prev === 'system' ? getSystemTheme() : prev
      return currentResolved === 'dark' ? 'light' : 'dark'
    })
  }, [])

  const setTheme = useCallback((newTheme: Theme) => {
    setThemeModeState(newTheme)
  }, [])

  const setThemeMode = useCallback((mode: ThemeMode) => {
    setThemeModeState(mode)
  }, [])

  return (
    <ThemeContext.Provider value={{ theme, themeMode, toggleTheme, setTheme, setThemeMode }}>
      {children}
    </ThemeContext.Provider>
  )
}

export const useTheme = (): ThemeContextType => {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
