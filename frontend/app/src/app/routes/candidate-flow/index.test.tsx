import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { CandidateFlowPage } from './index'

function queueJsonResponses(...payloads: Array<{ status?: number; body: unknown }>) {
  const queue = [...payloads]
  return vi.spyOn(window, 'fetch').mockImplementation(async (input, init) => {
    const next = queue.shift()
    if (!next) {
      throw new Error(`Unexpected fetch call for ${String(input)}`)
    }
    if (
      String(input).includes('/api/candidate-web/')
      && !String(input).endsWith('/bootstrap')
      && !String(input).includes('/api/candidate-web/public/')
    ) {
      expect((init?.headers as Headers).get('X-Candidate-Access-Session')).toBe('web-session-1')
    }
    return new Response(JSON.stringify(next.body), {
      status: next.status ?? 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
}

const journeyBase = {
  candidate: {
    user_id: 10,
    full_name: 'Browser Candidate',
    candidate_id: 10,
    city_name: 'Москва',
    status: 'lead',
  },
  timeline: [
    { key: 'launch', label: 'Вход', state: 'done', state_label: 'Готово' },
    { key: 'test1', label: 'Анкета', state: 'current', state_label: 'Сейчас' },
  ],
  primary_action: { key: 'continue_test1', label: 'Продолжить', kind: 'test1' },
  status_card: { title: 'Нужно закончить анкету', body: 'Ответьте на вопросы.', tone: 'progress' },
  active_booking: null,
}

const completedJourney = {
  ...journeyBase,
  timeline: [
    { key: 'launch', label: 'Вход', state: 'done', state_label: 'Готово' },
    { key: 'test1', label: 'Анкета', state: 'done', state_label: 'Готово' },
    { key: 'booking', label: 'Выбор времени', state: 'current', state_label: 'Сейчас' },
  ],
  primary_action: { key: 'select_slot', label: 'Выбрать время', kind: 'booking' },
  status_card: { title: 'Можно записаться', body: 'Выберите удобное время.', tone: 'success' },
}

const completedTest1 = {
  journey_step: 'booking',
  questions: [],
  draft_answers: {},
  is_completed: true,
  required_next_action: 'select_interview_slot',
  screening_decision: {
    outcome: 'invite_to_interview',
    explanation: 'Можно выбрать слот.',
    required_next_action: 'select_interview_slot',
  },
}

const unscreenedCompletedJourney = {
  ...journeyBase,
  timeline: [
    { key: 'launch', label: 'Вход', state: 'done', state_label: 'Готово' },
    { key: 'test1', label: 'Анкета', state: 'done', state_label: 'Готово' },
    { key: 'booking', label: 'Выбор времени', state: 'pending', state_label: 'Дальше' },
  ],
  primary_action: { key: 'chat_fallback', label: 'Открыть чат MAX', kind: 'chat' },
  status_card: { title: 'Ответы приняты', body: 'Мы готовим следующий шаг.', tone: 'progress' },
}

const unscreenedCompletedTest1 = {
  journey_step: 'test1_completed',
  questions: [],
  draft_answers: {},
  is_completed: true,
  required_next_action: 'recruiter_review',
  screening_decision: null,
}

const unverifiedStatus = {
  verified: false,
  booking_ready: false,
  required_before: ['booking', 'manual_availability'],
  available_channels: ['telegram'],
  telegram: {
    available: true,
    verified: false,
    status: 'available',
    label: 'Telegram',
    local_confirm_available: true,
  },
  max: {
    available: false,
    verified: false,
    status: 'unavailable',
    label: 'MAX',
    reason: 'max_unavailable_in_local_environment',
    local_confirm_available: true,
  },
  hh: {
    available: false,
    verified: false,
    status: 'unavailable',
    label: 'hh.ru',
    reason: 'hh_oauth_disabled',
    local_confirm_available: true,
  },
  hh_resume: null,
}

const verifiedStatus = {
  ...unverifiedStatus,
  verified: true,
  booking_ready: true,
  telegram: {
    available: true,
    verified: true,
    status: 'verified',
    label: 'Telegram',
    local_confirm_available: true,
  },
}

describe('CandidateFlowPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    window.sessionStorage.clear()
    Object.defineProperty(window, 'location', {
      value: {
        search: '?token=web-token-1234567890&utm_source=pilot',
        pathname: '/candidate-flow',
      },
      writable: true,
    })
  })

  it('opens Test1 from a public campaign after local Telegram handoff', async () => {
    Object.defineProperty(window, 'location', {
      value: {
        search: '?campaign=mass-flow&utm_source=qr',
        pathname: '/candidate-flow/start',
      },
      writable: true,
    })
    vi.spyOn(window, 'open').mockImplementation(() => null)
    queueJsonResponses(
      {
        body: {
          slug: 'mass-flow',
          title: 'Массовый набор Казань',
          status: 'active',
          available: true,
          allowed_providers: ['telegram', 'hh', 'max'],
          city_label: 'Казань',
          source_label: 'Web поток',
          copy: {
            title: 'Массовый набор Казань',
            subtitle: 'Подтвердите профиль, затем система откроет анкету Test1.',
          },
          availability_flags: {
            telegram: true,
            hh: false,
            max: false,
            local_confirm: true,
          },
        },
      },
      {
        body: {
          provider: 'telegram',
          available: true,
          url: 'https://t.me/recruitsmart_bot?start=public-provider-token',
          poll_token: 'public-poll-token-1234567890',
          start_param: 'public-provider-token',
          local_confirm_available: true,
        },
      },
      {
        body: {
          status: 'verified',
          provider: 'telegram',
          verified: true,
          handoff_available: true,
          handoff_code: 'public-handoff-code-1234567890',
        },
      },
      {
        body: {
          ok: true,
          candidate: { id: 10, candidate_id: 'public-id' },
          session: {
            session_id: 'web-session-1',
            journey_session_id: 20,
            status: 'active',
            surface: 'standalone_web',
            auth_method: 'signed_link',
            launch_channel: 'web',
            expires_at: '2026-04-23T12:00:00Z',
            reused: false,
          },
        },
      },
      { body: journeyBase },
      { body: verifiedStatus },
      {
        body: {
          journey_step: 'test1',
          questions: [
            {
              id: 'fio',
              prompt: 'Введите ваше <b>ФИО</b> полностью:',
              question_index: 0,
              options: [],
            },
          ],
          draft_answers: {},
          is_completed: false,
          required_next_action: null,
        },
      },
      { body: { source: 'profile', is_explicit: false } },
    )

    render(<CandidateFlowPage />)

    await waitFor(() => {
      expect(screen.getByTestId('candidate-flow-public-start')).toBeInTheDocument()
    })
    expect(screen.getByText('Глобальная ссылка не содержит персональный токен. Анкета откроется только после подтверждения личности.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Подтвердить Telegram/i }))

    await waitFor(() => {
      expect(window.sessionStorage.getItem('rs:candidate-web-public-poll:mass-flow')).toBe('public-poll-token-1234567890')
    })
    fireEvent.click(screen.getByRole('button', { name: 'Локально Telegram' }))

    await waitFor(() => {
      expect(screen.getByTestId('candidate-flow-test1')).toBeInTheDocument()
    })
    expect(window.sessionStorage.getItem('rs:candidate-web-public-poll:mass-flow')).toBeNull()
    expect(window.sessionStorage.getItem('rs:candidate-web-session')).toBe('web-session-1')
    expect(screen.getByText('Введите ваше ФИО полностью:')).toBeInTheDocument()
  })

  it('bootstraps by signed link and requires verification before Test1 without exposing the token', async () => {
    queueJsonResponses(
      {
        body: {
          ok: true,
          candidate: { id: 10, candidate_id: 'public-id' },
          session: {
            session_id: 'web-session-1',
            journey_session_id: 20,
            status: 'active',
            surface: 'standalone_web',
            auth_method: 'signed_link',
            launch_channel: 'web',
            expires_at: '2026-04-23T12:00:00Z',
            reused: false,
          },
        },
      },
      { body: journeyBase },
      { body: unverifiedStatus },
    )

    render(<CandidateFlowPage />)

    await waitFor(() => {
      expect(screen.getByTestId('candidate-flow-verification-gate')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /Личный кабинет/i })).toBeInTheDocument()
    expect(screen.getByText('Подтвердите профиль перед анкетой')).toBeInTheDocument()
    expect(screen.queryByTestId('candidate-flow-test1')).not.toBeInTheDocument()
    expect(screen.queryByText(/Browser pilot/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Не пересылайте ссылку/i)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Личный кабинет/i }))
    expect(screen.getByTestId('candidate-flow-account')).toBeInTheDocument()
    expect(screen.getByText('Browser Candidate')).toBeInTheDocument()
    expect(screen.queryByText('web-token-1234567890')).not.toBeInTheDocument()
    expect(window.sessionStorage.getItem('rs:candidate-web-session')).toBe('web-session-1')
  })

  it('unlocks Test1 after local Telegram verification', async () => {
    queueJsonResponses(
      {
        body: {
          ok: true,
          candidate: { id: 10, candidate_id: 'public-id' },
          session: {
            session_id: 'web-session-1',
            journey_session_id: 20,
            status: 'active',
            surface: 'standalone_web',
            auth_method: 'signed_link',
            launch_channel: 'web',
            expires_at: '2026-04-23T12:00:00Z',
            reused: false,
          },
        },
      },
      { body: journeyBase },
      { body: unverifiedStatus },
      {
        body: {
          ...verifiedStatus,
          telegram: {
            ...verifiedStatus.telegram,
            verified: true,
            status: 'verified',
          },
        },
      },
      { body: journeyBase },
      { body: verifiedStatus },
      {
        body: {
          journey_step: 'test1',
          questions: [
            {
              id: 'fio',
              prompt: '1‰ Введите ваше <b>ФИО</b> полностью:',
              question_index: 0,
              options: [],
            },
          ],
          draft_answers: {},
          is_completed: false,
          required_next_action: null,
        },
      },
      { body: { source: 'profile', is_explicit: false } },
    )

    render(<CandidateFlowPage />)

    await waitFor(() => {
      expect(screen.getByTestId('candidate-flow-verification-gate')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: /Локально подтвердить Telegram/i }))

    await waitFor(() => {
      expect(screen.getByTestId('candidate-flow-test1')).toBeInTheDocument()
    })
    expect(screen.getByText('Введите ваше ФИО полностью:')).toBeInTheDocument()
  })

  it('unlocks Test1 after local HH resume import', async () => {
    const hhVerifiedStatus = {
      ...verifiedStatus,
      hh: {
        available: false,
        verified: true,
        status: 'verified',
        label: 'hh.ru',
        reason: 'hh_oauth_disabled',
        local_confirm_available: true,
      },
      hh_resume: {
        resume_id: 'local-hh-resume-10',
        title: 'Специалист контактного центра',
        city: 'Москва',
        synced_at: '2026-04-24T09:00:00Z',
        import_status: 'success',
        contact_available: true,
      },
    }
    queueJsonResponses(
      {
        body: {
          ok: true,
          candidate: { id: 10, candidate_id: 'public-id' },
          session: {
            session_id: 'web-session-1',
            journey_session_id: 20,
            status: 'active',
            surface: 'standalone_web',
            auth_method: 'signed_link',
            launch_channel: 'web',
            expires_at: '2026-04-23T12:00:00Z',
            reused: false,
          },
        },
      },
      { body: journeyBase },
      { body: unverifiedStatus },
      { body: hhVerifiedStatus },
      { body: journeyBase },
      { body: hhVerifiedStatus },
      {
        body: {
          journey_step: 'test1',
          questions: [
            {
              id: 'city',
              prompt: '2‰ Ваш <b>город</b>?',
              question_index: 1,
              options: [{ label: 'Москва', value: 'Москва' }],
            },
          ],
          draft_answers: {},
          is_completed: false,
          required_next_action: null,
        },
      },
      { body: { source: 'profile', is_explicit: false } },
    )

    render(<CandidateFlowPage />)

    await waitFor(() => {
      expect(screen.getByTestId('candidate-flow-verification-gate')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: /Локально импортировать HH/i }))

    await waitFor(() => {
      expect(screen.getByTestId('candidate-flow-test1')).toBeInTheDocument()
    })
    expect(screen.getByText('Ваш город?')).toBeInTheDocument()
  })

  it('opens the booking step for local browser pilot when Test1 completed without screening decision', async () => {
    queueJsonResponses(
      {
        body: {
          ok: true,
          candidate: { id: 10, candidate_id: 'public-id' },
          session: {
            session_id: 'web-session-1',
            journey_session_id: 20,
            status: 'active',
            surface: 'standalone_web',
            auth_method: 'signed_link',
            launch_channel: 'web',
            expires_at: '2026-04-23T12:00:00Z',
            reused: false,
          },
        },
      },
      { body: unscreenedCompletedJourney },
      { body: verifiedStatus },
      { body: unscreenedCompletedTest1 },
      {
        body: {
          city_id: null,
          city_name: null,
          recruiter_id: null,
          recruiter_name: null,
          source: 'profile',
          is_explicit: false,
        },
      },
      { body: [{ city_id: 1, city_name: 'Москва', available_slots: 2, available_recruiters: 1, has_available_recruiters: true }] },
    )

    render(<CandidateFlowPage />)

    await waitFor(() => {
      expect(screen.getByTestId('candidate-flow-booking')).toBeInTheDocument()
    })
    expect(screen.getByText('Выберите слот в календаре')).toBeInTheDocument()
    expect(screen.queryByTestId('candidate-flow-verification-gate')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Москва/i })).toBeEnabled()
  })

  it('saves typed free-text drafts before completing Test1', async () => {
    const fetchSpy = queueJsonResponses(
      {
        body: {
          ok: true,
          candidate: { id: 10, candidate_id: 'public-id' },
          session: {
            session_id: 'web-session-1',
            journey_session_id: 20,
            status: 'active',
            surface: 'standalone_web',
            auth_method: 'signed_link',
            launch_channel: 'web',
            expires_at: '2026-04-23T12:00:00Z',
            reused: false,
          },
        },
      },
      { body: journeyBase },
      { body: verifiedStatus },
      {
        body: {
          journey_step: 'test1',
          questions: [
            {
              id: 'about',
              prompt: 'Расскажите о себе',
              placeholder: 'Введите ответ',
              question_index: 1,
              options: [],
            },
          ],
          draft_answers: {},
          is_completed: false,
          required_next_action: null,
        },
      },
      { body: { source: 'profile', is_explicit: false } },
      {
        body: {
          journey_step: 'test1',
          questions: [],
          draft_answers: { about: 'Хочу работать с клиентами' },
          is_completed: false,
          required_next_action: null,
        },
      },
      { body: completedTest1 },
      { body: completedJourney },
      { body: verifiedStatus },
      { body: completedTest1 },
      { body: { source: 'profile', is_explicit: false } },
      { body: [{ city_id: 1, city_name: 'Москва', available_slots: 1, available_recruiters: 1, has_available_recruiters: true }] },
    )

    render(<CandidateFlowPage />)

    await waitFor(() => {
      expect(screen.getByTestId('candidate-flow-test1')).toBeInTheDocument()
    })
    const completeButton = screen.getByRole('button', { name: 'Завершить анкету' })
    expect(completeButton).toBeDisabled()

    fireEvent.change(screen.getByPlaceholderText('Введите ответ'), {
      target: { value: 'Хочу работать с клиентами' },
    })
    expect(completeButton).toBeEnabled()
    fireEvent.click(completeButton)

    await waitFor(() => {
      expect(screen.getByTestId('candidate-flow-booking')).toBeInTheDocument()
    })
    const calls = fetchSpy.mock.calls.map(([url, init]) => ({
      url: String(url),
      method: init?.method || 'GET',
      body: init?.body,
    }))
    expect(calls).toContainEqual(expect.objectContaining({
      url: '/api/candidate-web/test1/answers',
      method: 'POST',
      body: JSON.stringify({ answers: { about: 'Хочу работать с клиентами' } }),
    }))
    expect(calls).toContainEqual(expect.objectContaining({
      url: '/api/candidate-web/test1/complete',
      method: 'POST',
    }))
  })

  it('books a slot and shows the already-booked state', async () => {
    queueJsonResponses(
      {
        body: {
          ok: true,
          candidate: { id: 10, candidate_id: 'public-id' },
          session: {
            session_id: 'web-session-1',
            journey_session_id: 20,
            status: 'active',
            surface: 'standalone_web',
            auth_method: 'signed_link',
            launch_channel: 'web',
            expires_at: '2026-04-23T12:00:00Z',
            reused: false,
          },
        },
      },
      { body: completedJourney },
      { body: verifiedStatus },
      { body: completedTest1 },
      {
        body: {
          city_id: 1,
          city_name: 'Москва',
          recruiter_id: 2,
          recruiter_name: 'Анна',
          source: 'explicit',
          is_explicit: true,
        },
      },
      { body: [{ city_id: 1, city_name: 'Москва', available_slots: 1, available_recruiters: 1, has_available_recruiters: true }] },
      { body: [{ recruiter_id: 2, recruiter_name: 'Анна', city_id: 1, available_slots: 1 }] },
      {
        body: [
          {
            slot_id: 101,
            recruiter_id: 2,
            recruiter_name: 'Анна',
            start_utc: '2026-04-24T09:00:00Z',
            end_utc: '2026-04-24T10:00:00Z',
            duration_minutes: 60,
            city_id: 1,
            city_name: 'Москва',
          },
        ],
      },
      {
        body: {
          booking_id: 101,
          slot_id: 101,
          candidate_id: 10,
          recruiter_name: 'Анна',
          start_utc: '2026-04-24T09:00:00Z',
          end_utc: '2026-04-24T10:00:00Z',
          status: 'booked',
        },
      },
      {
        body: {
          ...completedJourney,
          active_booking: {
            booking_id: 101,
            slot_id: 101,
            candidate_id: 10,
            recruiter_name: 'Анна',
            start_utc: '2026-04-24T09:00:00Z',
            end_utc: '2026-04-24T10:00:00Z',
            status: 'booked',
          },
        },
      },
      { body: verifiedStatus },
      { body: completedTest1 },
      {
        body: {
          city_id: 1,
          city_name: 'Москва',
          recruiter_id: 2,
          recruiter_name: 'Анна',
          source: 'explicit',
          is_explicit: true,
        },
      },
      { body: [{ city_id: 1, city_name: 'Москва', available_slots: 0, available_recruiters: 1, has_available_recruiters: true }] },
      { body: [{ recruiter_id: 2, recruiter_name: 'Анна', city_id: 1, available_slots: 0 }] },
      { body: [] },
    )

    render(<CandidateFlowPage />)

    await waitFor(() => {
      expect(screen.getByTestId('candidate-flow-booking')).toBeInTheDocument()
    })
    expect(screen.getByText('Выберите слот в календаре')).toBeInTheDocument()
    expect(screen.getByText('HR')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /24 апр/i }).length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: /Забронировать слот/i }))

    await waitFor(() => {
      expect(screen.getByTestId('candidate-flow-booked')).toBeInTheDocument()
    })
    expect(screen.getByText(/Ожидает подтверждения/i)).toBeInTheDocument()
  })
})
