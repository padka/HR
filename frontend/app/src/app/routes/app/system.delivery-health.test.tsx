import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { MessengerHealthCards } from './system.delivery-health'

describe('MessengerHealthCards', () => {
  it('renders per-channel delivery health cards', () => {
    render(
      <MessengerHealthCards
        channels={{
          telegram: {
            channel: 'telegram',
            queue_depth: 2,
            dead_letter_count: 0,
            oldest_pending_age_seconds: 45,
            degraded: false,
            status: 'healthy',
            degraded_reason: null,
          },
          max: {
            channel: 'max',
            queue_depth: 1,
            dead_letter_count: 3,
            oldest_pending_age_seconds: 120,
            degraded: true,
            status: 'degraded',
            degraded_reason: 'max:invalid_token',
          },
        }}
      />,
    )

    expect(screen.getByTestId('messenger-health-telegram')).toBeInTheDocument()
    expect(screen.getByTestId('messenger-health-max')).toBeInTheDocument()
    expect(screen.getByText(/queue: 2 · dlq: 0/)).toBeInTheDocument()
    expect(screen.getByText(/queue: 1 · dlq: 3/)).toBeInTheDocument()
    expect(screen.getByText(/max:invalid_token/)).toBeInTheDocument()
  })
})
