import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { CandidateActions } from './CandidateActions'

describe('CandidateActions', () => {
  it('prefers explicit resend_test2 action when interview outcome action is also present', () => {
    const onActionClick = vi.fn()

    render(
      <CandidateActions
        candidate={{
          slots: [{ status: 'CONFIRMED_BY_CANDIDATE', purpose: 'interview' }],
          telegram_id: null,
          telegram_username: null,
          linked_channels: { telegram: false, max: true },
          max: { linked: true },
          hh_profile_url: null,
          hh_resume_id: null,
          hh_negotiation_id: null,
          hh_sync_status: null,
          telemost_url: null,
          candidate_status_slug: 'interview_confirmed',
          candidate_status_display: 'Собеседование подтверждено',
          lifecycle_summary: { stage: 'interview', stage_label: 'Интервью' },
          scheduling_summary: { active: true },
          candidate_next_action: {
            version: 1,
            lifecycle_stage: 'interview',
            record_state: 'active',
            worklist_bucket: 'awaiting_recruiter',
            urgency: 'normal',
            primary_action: {
              type: 'wait_for_recruiter',
              label: 'Ожидаем решение рекрутера',
              enabled: false,
              owner_role: 'recruiter',
              ui_action: null,
              legacy_action_key: null,
              blocking_reasons: ['manual_review_pending'],
            },
            explanation: 'Рекрутер еще не завершил текущий шаг.',
          },
          operational_summary: {},
          state_reconciliation: { issues: [] },
          candidate_actions: [
            {
              key: 'interview_passed',
              label: 'Прошел собеседование (отправить Тест 2)',
              variant: 'primary',
              method: 'POST',
              target_status: 'test2_sent',
              url_pattern: '/api/candidates/{id}/actions/interview_passed',
            },
            {
              key: 'resend_test2',
              label: 'Отправить Тест 2',
              variant: 'secondary',
              method: 'POST',
              target_status: 'test2_sent',
              url_pattern: '/api/candidates/{id}/actions/resend_test2',
            },
          ],
        } as any}
        statusSlug="interview_confirmed"
        actionPending={false}
        onOpenChat={vi.fn()}
        onOpenTests={vi.fn()}
        onOpenInsights={vi.fn()}
        onOpenHh={vi.fn()}
        onScheduleSlot={vi.fn()}
        onScheduleIntroDay={vi.fn()}
        onActionClick={onActionClick}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Отправить Тест 2' }))

    expect(onActionClick).toHaveBeenCalledTimes(1)
    expect(onActionClick.mock.calls[0]?.[0]?.key).toBe('resend_test2')
  })
})
