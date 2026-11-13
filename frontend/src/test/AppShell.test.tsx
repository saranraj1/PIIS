import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '../theme/ThemeContext'
import { AuthProvider } from '../auth/AuthContext'
import { RootLayout } from '../components/layout/RootLayout'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
  },
})

const renderAppShell = (initialRoute = '/') => {
  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <MemoryRouter initialEntries={[initialRoute]}>
            <RootLayout />
          </MemoryRouter>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

describe('Application Shell Layout & Navigation', () => {
  it('renders operational boundary status and safeguards', () => {
    renderAppShell()

    expect(screen.getByText(/Read-Only Decision Support/i)).toBeInTheDocument()
    expect(screen.getByText(/STRICTLY PROHIBITED/i)).toBeInTheDocument()
  })

  it('renders epistemic legend with all 6 reasoning classifications', () => {
    renderAppShell()

    expect(screen.getByText(/OBSERVED FACT/i)).toBeInTheDocument()
    expect(screen.getByText(/MODEL PREDICTION/i)).toBeInTheDocument()
    expect(screen.getByText(/HYPOTHESIS/i)).toBeInTheDocument()
    expect(screen.getByText(/RECOMMENDATION/i)).toBeInTheDocument()
    expect(screen.getByText(/HUMAN-APPROVED DECISION/i)).toBeInTheDocument()
    expect(screen.getByText(/CONFIRMED ROOT CAUSE/i)).toBeInTheDocument()
  })

  it('renders all 9 primary navigation items', () => {
    renderAppShell()

    const nav = screen.getByRole('navigation', { name: /Main Navigation/i })
    expect(nav).toBeInTheDocument()

    const expectedViews = [
      'Command Center',
      'Incident Explorer',
      'Investigation',
      'Network Intelligence',
      'Human Review',
      'Audit & Provenance',
      'Integrations & DLQ',
      'System Health',
      'Settings & Profile',
    ]

    expectedViews.forEach((viewName) => {
      expect(screen.getByRole('link', { name: new RegExp(viewName, 'i') })).toBeInTheDocument()
    })
  })

  it('renders the header title and read-only badge', () => {
    renderAppShell()

    expect(screen.getByText('Production Incident Intelligence System')).toBeInTheDocument()
    expect(screen.getByText('Telecom Operations Console')).toBeInTheDocument()
    expect(screen.getByText('STRICT READ-ONLY BOUNDARY')).toBeInTheDocument()
  })
})
