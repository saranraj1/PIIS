import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider, useTheme } from '../theme/ThemeContext'

const ThemeTestComponent = () => {
  const { theme, toggleTheme, setTheme } = useTheme()
  return (
    <div>
      <span data-testid="current-theme">{theme}</span>
      <button onClick={toggleTheme}>Toggle</button>
      <button onClick={() => setTheme('light')}>Set Light</button>
      <button onClick={() => setTheme('dark')}>Set Dark</button>
    </div>
  )
}

describe('ThemeContext', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove('dark')
  })

  it('provides default theme and updates localStorage on toggle', async () => {
    const user = userEvent.setup()
    render(
      <ThemeProvider>
        <ThemeTestComponent />
      </ThemeProvider>
    )

    const themeDisplay = screen.getByTestId('current-theme')
    const initialTheme = themeDisplay.textContent

    expect(initialTheme).toMatch(/dark|light/)

    const toggleBtn = screen.getByRole('button', { name: 'Toggle' })
    await act(async () => {
      await user.click(toggleBtn)
    })

    const expectedNewTheme = initialTheme === 'dark' ? 'light' : 'dark'
    expect(themeDisplay.textContent).toBe(expectedNewTheme)
    expect(localStorage.getItem('piis_theme_preference')).toBe(expectedNewTheme)
  })

  it('respects stored preference from localStorage', () => {
    localStorage.setItem('piis_theme_preference', 'light')

    render(
      <ThemeProvider>
        <ThemeTestComponent />
      </ThemeProvider>
    )

    expect(screen.getByTestId('current-theme').textContent).toBe('light')
  })
})
