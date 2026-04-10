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
        portal={{
          public_url: 'https://crm.example.test',
          public_ready: true,
          runtime_status: 'blocked',
          runtime_ready: false,
          adapter_ready: true,
          public_entry_enabled: false,
          max_entry_ready: false,
          bot_profile_resolved: true,
          bot_profile_name: 'Attila MAX Bot',
          max_link_base_source: 'missing',
          dedupe_ready: false,
          dedupe_mode: 'unavailable',
          dedupe_message: 'MAX webhook blocked until Redis-backed dedupe is available.',
          webhook_public_ready: false,
          webhook_message: 'MAX_WEBHOOK_URL должен быть публичным HTTPS URL.',
          max_entry_message: 'MAX_BOT_LINK_BASE не настроен.',
          max_link_base: null,
          subscription_ready: false,
          browser_portal_fallback_allowed: true,
          telegram_business_fallback_allowed: false,
          shared_contract_mode: 'candidate_portal',
          readiness_blockers: ['max_webhook_url_not_public_https', 'max_webhook_dedupe_redis_missing'],
          shared_access: {
            store_backend: 'redis',
            production_ready: true,
            rate_limit_ready: true,
            challenge_started: 12,
            challenge_rate_limited: 2,
            verify_success: 8,
            verify_failed: 3,
            verify_expired: 1,
          },
        }}
      />,
    )

    expect(screen.getByTestId('messenger-health-portal')).toBeInTheDocument()
    expect(screen.getByTestId('messenger-health-telegram')).toBeInTheDocument()
    expect(screen.getByTestId('messenger-health-max')).toBeInTheDocument()
    expect(screen.getByText(/queue: 2 · dlq: 0/)).toBeInTheDocument()
    expect(screen.getByText(/queue: 1 · dlq: 3/)).toBeInTheDocument()
    expect(screen.getByText(/max:invalid_token/)).toBeInTheDocument()
    expect(screen.getByText(/MAX webhook blocked until Redis-backed dedupe is available/)).toBeInTheDocument()
    expect(screen.getByText(/profile: Attila MAX Bot/)).toBeInTheDocument()
    expect(screen.getByText(/webhook: blocked/)).toBeInTheDocument()
    expect(screen.getByText(/runtime: blocked · public entry: off/)).toBeInTheDocument()
    expect(screen.getByText(/subscription: blocked · dedupe: blocked/)).toBeInTheDocument()
    expect(screen.getByText(/fallback: browser allowed · Telegram forbidden/)).toBeInTheDocument()
    expect(screen.getByText(/blockers: max_webhook_url_not_public_https, max_webhook_dedupe_redis_missing/)).toBeInTheDocument()
    expect(screen.getByText(/candidate access auth: ready · store: redis · rate-limit: ready/)).toBeInTheDocument()
  })
})
