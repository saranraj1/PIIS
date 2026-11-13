import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EpistemicBadge, EPISTEMIC_CONFIG, type EpistemicCategory } from '../components/epistemic/EpistemicBadge'

describe('EpistemicBadge Component', () => {
  const categories: EpistemicCategory[] = [
    'OBSERVED_FACT',
    'MODEL_PREDICTION',
    'HYPOTHESIS',
    'RECOMMENDATION',
    'HUMAN_APPROVED_DECISION',
    'CONFIRMED_ROOT_CAUSE',
  ]

  it.each(categories)('renders badge for %s with correct epistemic text and aria-label', (category) => {
    render(<EpistemicBadge category={category} />)

    const definition = EPISTEMIC_CONFIG[category]
    const badge = screen.getByLabelText(`${definition.label}: ${definition.ariaRole}`)

    expect(badge).toBeInTheDocument()
    expect(badge).toHaveTextContent(definition.label)
  })

  it('renders custom text when label override is provided', () => {
    render(<EpistemicBadge category="OBSERVED_FACT" label="Telemetry Verified" />)
    expect(screen.getByText('Telemetry Verified')).toBeInTheDocument()
  })

  it('renders different size classes appropriately', () => {
    const { rerender } = render(<EpistemicBadge category="HYPOTHESIS" size="sm" />)
    const badgeSm = screen.getByRole('status')
    expect(badgeSm.className).toContain('text-[0.65rem]')

    rerender(<EpistemicBadge category="HYPOTHESIS" size="lg" />)
    const badgeLg = screen.getByRole('status')
    expect(badgeLg.className).toContain('text-xs')
  })
})
