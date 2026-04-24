import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { MaxMiniAppPage } from './index'

function queueJsonResponses(...payloads: Array<{ status?: number; body: unknown }>) {
  const queue = [...payloads]
  return vi.spyOn(window, 'fetch').mockImplementation(async (input, _init) => {
    const next = queue.shift()
    if (!next) {
      throw new Error(`Unexpected fetch call for ${String(input)}`)
    }
    return new Response(JSON.stringify(next.body), {
      status: next.status ?? 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
}

describe('MaxMiniAppPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    Object.defineProperty(window, 'location', {
      value: {
        search: '',
      },
      writable: true,
    })
    window.WebApp = {
      initData: 'signed-init-data',
      initDataUnsafe: {},
      ready: vi.fn(),
      expand: vi.fn(),
      requestContact: vi.fn(),
      enableClosingConfirmation: vi.fn(),
      disableClosingConfirmation: vi.fn(),
      openMaxLink: vi.fn(),
      openLink: vi.fn(),
      BackButton: {
        show: vi.fn(),
        hide: vi.fn(),
        onClick: vi.fn(),
        offClick: vi.fn(),
      },
    }
  })

  it('opens Test1 directly for a fresh MAX intake launch', async () => {
    queueJsonResponses(
      {
        body: {
          binding: {
            status: 'bound',
            message: 'Кандидатский доступ готов.',
            start_param: 'draft-intake-ref',
            chat_url: 'https://max.ru/test-max-bot?start=draft-intake-ref',
          },
          capabilities: {
            request_contact: true,
            open_link: true,
            open_max_link: true,
          },
          session: {
            session_id: 'session-draft',
          },
        },
      },
      {
        body: {
          timeline: [],
          primary_action: {
            key: 'continue_test1',
            label: 'Продолжить анкету',
            kind: 'test1',
          },
          status_card: {
            title: 'Нужно закончить анкету',
            body: 'Ответьте на вопросы Test1.',
            tone: 'progress',
          },
          prep_card: { title: 'Что дальше', body: 'После анкеты покажем следующий шаг.' },
          company_card: { title: 'О компании', body: 'RecruitSmart' },
          help_card: { title: 'Помощь', body: 'Откройте чат MAX, если потребуется помощь.' },
        },
      },
      {
        body: {
          journey_step: 'test1',
          questions: [
            {
              id: 'fio',
              prompt: 'Как вас зовут?',
              question_index: 0,
              options: [],
            },
          ],
          draft_answers: {},
          is_completed: false,
          required_next_action: null,
        },
      },
      {
        body: {
          source: 'test1_prefill',
          is_explicit: false,
        },
      },
    )

    render(<MaxMiniAppPage />)

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-test1')).toBeInTheDocument()
      expect(screen.getByText(/Короткая анкета/i)).toBeInTheDocument()
    })
    expect(screen.queryByText(/Ответы по анкете/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Открыть чат MAX' })).not.toBeInTheDocument()
  })

  it('fails closed outside MAX and does not call launch bootstrap without initData', async () => {
    const fetchSpy = vi.spyOn(window, 'fetch')
    window.WebApp = undefined

    render(<MaxMiniAppPage />)

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-outside-max')).toBeInTheDocument()
      expect(screen.getByText(/Откройте кабинет внутри MAX/i)).toBeInTheDocument()
    })

    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('renders dedicated manual review state instead of generic phone bind form', async () => {
    queueJsonResponses({
      body: {
        binding: {
          status: 'manual_review_required',
          message: 'Не удалось безопасно восстановить анкету автоматически. Продолжим после ручной проверки.',
          requires_contact: false,
          chat_url: 'https://max.ru/test-max-bot',
        },
        capabilities: {
          request_contact: true,
          open_link: true,
          open_max_link: true,
        },
      },
    })

    render(<MaxMiniAppPage />)

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-manual-review')).toBeInTheDocument()
      expect(screen.queryByTestId('miniapp-prebind')).not.toBeInTheDocument()
      expect(screen.queryByText('Телефон')).not.toBeInTheDocument()
    })
  })

  it('uses MAX requestContact and forwards contact payload to contact bind endpoint', async () => {
    const fetchMock = queueJsonResponses(
      {
        body: {
          binding: {
            status: 'contact_required',
            message: 'Нужен номер телефона, чтобы найти вашу анкету.',
            requires_contact: true,
            chat_url: 'https://max.ru/test-max-bot',
          },
          capabilities: {
            request_contact: true,
            open_link: true,
            open_max_link: true,
          },
        },
      },
      {
        body: {
          status: 'bound',
          message: 'Кандидат найден.',
          start_param: 'bound-contact-ref',
        },
      },
      {
        body: {
          binding: {
            status: 'bound',
            message: 'Кандидатский доступ готов.',
            start_param: 'bound-contact-ref',
            chat_url: 'https://max.ru/test-max-bot?start=bound-contact-ref',
          },
          capabilities: {
            request_contact: true,
            open_link: true,
            open_max_link: true,
          },
          session: {
            session_id: 'session-1',
          },
        },
      },
      {
        body: {
          timeline: [],
          primary_action: {
            key: 'continue_test1',
            label: 'Продолжить анкету',
            kind: 'test1',
          },
          status_card: {
            title: 'Анкета ждёт ответа',
            body: 'Ответьте на несколько вопросов.',
            tone: 'progress',
          },
          prep_card: { title: 'Что дальше', body: 'Подготовьтесь к следующему шагу.' },
          company_card: { title: 'О компании', body: 'RecruitSmart' },
          help_card: { title: 'Помощь', body: 'Откройте чат MAX, если потребуется помощь.' },
        },
      },
      {
        body: {
          journey_step: 'test1',
          questions: [
            {
              id: 'q1',
              prompt: 'Как вас зовут?',
              question_index: 0,
              options: [],
            },
          ],
          draft_answers: {},
          is_completed: false,
          required_next_action: null,
        },
      },
      {
        body: {
          source: 'test1_prefill',
          is_explicit: false,
        },
      },
    )

    const requestContactMock = vi.fn().mockResolvedValue({
      phone_number: '+7 999 123-45-67',
      first_name: 'Max',
    })
    window.WebApp = {
      ...window.WebApp,
      requestContact: requestContactMock,
    }

    render(<MaxMiniAppPage />)

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-prebind')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Взять номер из MAX' }))

    await waitFor(() => {
      expect(requestContactMock).toHaveBeenCalledTimes(1)
      expect(screen.getByTestId('miniapp-home')).toBeInTheDocument()
    })

    const contactCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/api/candidate-access/contact'))
    expect(contactCall).toBeTruthy()
    const contactPayload = JSON.parse(String(contactCall?.[1]?.body))
    expect(contactPayload).toMatchObject({
      phone: '+7 999 123-45-67',
      contact: {
        phone_number: '+7 999 123-45-67',
        first_name: 'Max',
      },
    })
  })

  it('opens help panel for a legacy chat primary action without leaving mini app', async () => {
    queueJsonResponses(
      {
        body: {
          binding: {
            status: 'bound',
            message: 'Кандидатский доступ готов.',
            chat_url: 'https://max.ru/test-max-bot?start=chat-flow',
          },
          capabilities: {
            request_contact: true,
            open_link: true,
            open_max_link: true,
          },
          session: {
            session_id: 'session-chat',
          },
        },
      },
      {
        body: {
          timeline: [],
          primary_action: {
            key: 'continue_chat',
            label: 'Продолжить в чат',
            kind: 'chat',
            detail: 'Переведём разговор в чат MAX без потери контекста.',
          },
          status_card: {
            title: 'Чат доступен',
            body: 'Если нужен человек, переходите в MAX чат.',
            tone: 'progress',
          },
          prep_card: { title: 'Что дальше', body: 'Если понадобится помощь, откройте чат MAX.' },
          company_card: { title: 'О компании', body: 'RecruitSmart' },
          help_card: { title: 'Нужна помощь', body: 'Откройте чат MAX.' },
        },
      },
      {
        body: {
          journey_step: 'booking',
          questions: [],
          draft_answers: {},
          is_completed: true,
          required_next_action: null,
        },
      },
      {
        body: {
          source: 'explicit',
          is_explicit: true,
        },
      },
      {
        body: {
          handoff_sent: true,
        },
      },
    )

    render(<MaxMiniAppPage />)

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-home')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Продолжить в чат' }))

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-help')).toBeInTheDocument()
      expect(screen.getByText(/Что делать дальше/i)).toBeInTheDocument()
    })
  })

  it('shows empty booking state when no cities are available', async () => {
    queueJsonResponses(
      {
        body: {
          binding: {
            status: 'bound',
            message: 'Кандидатский доступ готов.',
            chat_url: 'https://max.ru/test-max-bot?start=booking-empty',
          },
          capabilities: {
            request_contact: true,
            open_link: true,
            open_max_link: true,
          },
          session: {
            session_id: 'session-booking-empty',
          },
        },
      },
      {
        body: {
          timeline: [],
          primary_action: {
            key: 'booking',
            label: 'Выбрать время',
            kind: 'booking',
            detail: 'Выберите удобный слот для встречи.',
          },
          status_card: {
            title: 'Пора выбрать слот',
            body: 'Сначала выберите город.',
            tone: 'progress',
          },
          prep_card: { title: 'Памятка', body: 'Мы покажем детали после выбора слота.' },
          company_card: { title: 'О компании', body: 'RecruitSmart' },
          help_card: { title: 'Помощь', body: 'Откройте чат MAX, если нет подходящего времени.' },
        },
      },
      {
        body: {
          journey_step: 'booking',
          questions: [],
          draft_answers: {},
          is_completed: true,
          required_next_action: 'select_interview_slot',
        },
      },
      {
        body: {
          source: 'test1_prefill',
          is_explicit: false,
        },
      },
      {
        body: [],
      },
    )

    render(<MaxMiniAppPage />)

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-home')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Выбрать время' }))

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-booking-cities')).toBeInTheDocument()
      expect(screen.getByText(/Слоты ещё не опубликованы/i)).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Оставить пожелания' }))

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-manual-availability')).toBeInTheDocument()
    })
  })

  it('submits manual availability and returns to the home status screen', async () => {
    queueJsonResponses(
      {
        body: {
          binding: {
            status: 'bound',
            message: 'Кандидатский доступ готов.',
            chat_url: 'https://max.ru/test-max-bot?start=manual-availability',
          },
          capabilities: {
            request_contact: true,
            open_link: true,
            open_max_link: true,
          },
          session: {
            session_id: 'session-manual-availability',
          },
        },
      },
      {
        body: {
          timeline: [],
          primary_action: {
            key: 'select_slot',
            label: 'Выбрать время',
            kind: 'booking',
            detail: 'Выберите удобный слот для встречи.',
          },
          status_card: {
            title: 'Можно записаться на собеседование',
            body: 'Сначала проверьте доступные интервалы.',
            tone: 'progress',
          },
          prep_card: { title: 'Памятка', body: 'Мы обновим статус после записи.' },
          company_card: { title: 'О компании', body: 'RecruitSmart' },
          help_card: { title: 'Помощь', body: 'Откройте чат MAX, если нет слотов.' },
          active_booking: null,
        },
      },
      {
        body: {
          journey_step: 'booking',
          questions: [],
          draft_answers: {},
          is_completed: true,
          required_next_action: 'select_interview_slot',
        },
      },
      {
        body: {
          city_id: 1,
          city_name: 'Москва',
          source: 'test1_prefill',
          is_explicit: false,
        },
      },
      {
        body: [],
      },
      {
        body: [],
      },
      {
        body: {
          status: 'submitted',
          message: 'Пожелания по времени отправлены. Рекрутер подберёт слот и свяжется с вами.',
          recruiters_notified: true,
        },
      },
      {
        body: {
          timeline: [],
          primary_action: {
            key: 'review_manual_request',
            label: 'Проверить статус',
            kind: 'help',
            detail: 'Пожелания по времени уже отправлены.',
          },
          status_card: {
            title: 'Пожелания по времени отправлены',
            body: 'Мы передали удобное время рекрутеру.',
            tone: 'progress',
          },
          prep_card: { title: 'Что дальше', body: 'Мы обновим статус здесь и в чате MAX.' },
          company_card: { title: 'О компании', body: 'RecruitSmart' },
          help_card: { title: 'Помощь', body: 'Откройте чат MAX.' },
          active_booking: null,
        },
      },
      {
        body: {
          journey_step: 'booking',
          questions: [],
          draft_answers: {},
          is_completed: true,
          required_next_action: 'select_interview_slot',
        },
      },
      {
        body: {
          city_id: 1,
          city_name: 'Москва',
          source: 'test1_prefill',
          is_explicit: false,
        },
      },
      {
        body: [],
      },
      {
        body: [],
      },
    )

    render(<MaxMiniAppPage />)

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-home')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Выбрать время' }))

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-booking-recruiters')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Оставить пожелания' }))

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-manual-availability')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByPlaceholderText(/удобно в будни/i), {
      target: { value: 'Будни после 18:00' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Отправить пожелания' }))

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-home')).toBeInTheDocument()
      expect(screen.getByTestId('miniapp-manual-availability-success')).toBeInTheDocument()
    })
  })

  it('renders booked state after successful bootstrap', async () => {
    queueJsonResponses(
      {
        body: {
          binding: {
            status: 'bound',
            message: 'Кандидатский доступ готов.',
          },
          session: {
            session_id: 'session-1',
          },
        },
      },
      {
        body: {
          active_booking: {
            booking_id: 10,
            recruiter_name: 'MAX Recruiter',
            start_utc: '2030-01-01T10:00:00Z',
            end_utc: '2030-01-01T11:00:00Z',
            status: 'confirmed_by_candidate',
            meet_link: 'https://telemost.example/max-room',
          },
          timeline: [],
          primary_action: { key: 'review_booking', label: 'Проверить детали встречи', kind: 'booking' },
          status_card: { title: 'Собеседование уже назначено', body: 'Проверьте детали', tone: 'success' },
          prep_card: { title: 'Что дальше', body: 'Памятка' },
          company_card: { title: 'О компании', body: 'RecruitSmart' },
          help_card: { title: 'Нужна помощь', body: 'Откройте чат MAX' },
        },
      },
      {
        body: {
          journey_step: 'booking',
          questions: [],
          draft_answers: {},
          is_completed: true,
          required_next_action: 'select_interview_slot',
        },
      },
      {
        body: {
          city_id: 1,
          recruiter_id: 1,
          source: 'explicit',
          is_explicit: true,
        },
      },
      { body: [] },
      { body: [] },
      { body: [] },
    )

    render(<MaxMiniAppPage />)

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-booked')).toBeInTheDocument()
      expect(screen.getByText(/Встреча подтверждена/i)).toBeInTheDocument()
      expect(screen.getByText(/MAX Recruiter/)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Открыть конференцию' })).toBeInTheDocument()
    })
    expect(screen.getByTestId('miniapp-booking-success')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Подтвердить встречу' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Открыть чат MAX' })).not.toBeInTheDocument()
  })

  it('shows urgent confirmation copy when approved interview starts in less than two hours', async () => {
    const soonStart = new Date(Date.now() + 75 * 60 * 1000).toISOString()
    const soonEnd = new Date(Date.now() + 135 * 60 * 1000).toISOString()

    queueJsonResponses(
      {
        body: {
          binding: {
            status: 'bound',
            message: 'Кандидатский доступ готов.',
          },
          session: {
            session_id: 'session-urgent-booking',
          },
        },
      },
      {
        body: {
          active_booking: {
            booking_id: 18,
            recruiter_name: 'MAX Recruiter',
            start_utc: soonStart,
            end_utc: soonEnd,
            status: 'booked',
          },
          timeline: [],
          primary_action: { key: 'review_booking', label: 'Проверить детали встречи', kind: 'booking' },
          status_card: { title: 'Собеседование уже назначено', body: 'Проверьте детали', tone: 'success' },
          prep_card: { title: 'Что дальше', body: 'Памятка' },
          company_card: { title: 'О компании', body: 'RecruitSmart' },
          help_card: { title: 'Нужна помощь', body: 'Откройте чат MAX' },
        },
      },
      {
        body: {
          journey_step: 'booking',
          questions: [],
          draft_answers: {},
          is_completed: true,
          required_next_action: 'select_interview_slot',
        },
      },
      {
        body: {
          city_id: 1,
          recruiter_id: 1,
          source: 'explicit',
          is_explicit: true,
        },
      },
      { body: [] },
      { body: [] },
      { body: [] },
    )

    render(<MaxMiniAppPage />)

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-booked')).toBeInTheDocument()
      expect(screen.getByText(/меньше двух часов/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Подтвердить встречу' })).toBeInTheDocument()
    })
  })

  it('renders pending booking as recruiter review without candidate confirmation actions', async () => {
    queueJsonResponses(
      {
        body: {
          binding: {
            status: 'bound',
            message: 'Кандидатский доступ готов.',
          },
          session: {
            session_id: 'session-pending',
          },
        },
      },
      {
        body: {
          active_booking: {
            booking_id: 11,
            recruiter_name: 'MAX Recruiter',
            start_utc: '2030-01-01T10:00:00Z',
            end_utc: '2030-01-01T11:00:00Z',
            status: 'pending',
            candidate_can_confirm_pending: false,
          },
          timeline: [],
          primary_action: { key: 'review_pending_booking', label: 'Проверить статус заявки', kind: 'booking' },
          status_card: { title: 'Слот отправлен на согласование', body: 'Мы просматриваем ваше резюме и результаты Test1.', tone: 'progress' },
          prep_card: { title: 'Что дальше', body: 'Мы просматриваем ваше резюме и результаты Test1.' },
          company_card: { title: 'О компании', body: 'RecruitSmart' },
          help_card: { title: 'Нужна помощь', body: 'Откройте чат MAX' },
        },
      },
      {
        body: {
          journey_step: 'booking',
          questions: [],
          draft_answers: {},
          is_completed: true,
          required_next_action: 'select_interview_slot',
        },
      },
      {
        body: {
          city_id: 1,
          recruiter_id: 1,
          source: 'explicit',
          is_explicit: true,
        },
      },
      { body: [] },
      { body: [] },
      { body: [] },
    )

    render(<MaxMiniAppPage />)

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-booked')).toBeInTheDocument()
      expect(screen.getByText(/Слот на согласовании/i)).toBeInTheDocument()
      expect(screen.getAllByText(/Мы просматриваем ваше резюме/i).length).toBeGreaterThan(0)
    })
    expect(screen.queryByRole('button', { name: 'Подтвердить встречу' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Выбрать другое время' })).not.toBeInTheDocument()
  })

  it('renders recruiter pending offer with confirm action only', async () => {
    queueJsonResponses(
      {
        body: {
          binding: {
            status: 'bound',
            message: 'Кандидатский доступ готов.',
          },
          session: {
            session_id: 'session-pending-offer',
          },
        },
      },
      {
        body: {
          active_booking: {
            booking_id: 12,
            recruiter_name: 'MAX Recruiter',
            start_utc: '2030-01-01T10:00:00Z',
            end_utc: '2030-01-01T11:00:00Z',
            status: 'pending',
            candidate_can_confirm_pending: true,
          },
          timeline: [],
          primary_action: { key: 'confirm_pending_offer', label: 'Подтвердить предложенное время', kind: 'booking' },
          status_card: { title: 'Мы предлагаем время собеседования', body: 'Если этот слот вам подходит, подтвердите встречу в mini app.', tone: 'progress' },
          prep_card: { title: 'Что дальше', body: 'Если время подходит, подтвердите встречу в mini app.' },
          company_card: { title: 'О компании', body: 'RecruitSmart' },
          help_card: { title: 'Нужна помощь', body: 'RecruitSmart' },
        },
      },
      {
        body: {
          journey_step: 'booking',
          questions: [],
          draft_answers: {},
          is_completed: true,
          required_next_action: 'select_interview_slot',
        },
      },
      {
        body: {
          city_id: 1,
          recruiter_id: 1,
          source: 'explicit',
          is_explicit: true,
        },
      },
      { body: [] },
      { body: [] },
      { body: [] },
    )

    render(<MaxMiniAppPage />)

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-booked')).toBeInTheDocument()
      expect(screen.getByText(/Мы предлагаем время собеседования/i)).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: 'Подтвердить встречу' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Выбрать другое время' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Отменить запись' })).not.toBeInTheDocument()
  })

  it('shows final Test1 review instead of restarting from the first question when all answers are captured', async () => {
    queueJsonResponses(
      {
        body: {
          binding: {
            status: 'bound',
            message: 'Кандидатский доступ готов.',
          },
          session: {
            session_id: 'session-test1-review',
          },
        },
      },
      {
        body: {
          timeline: [],
          primary_action: { key: 'continue_test1', label: 'Продолжить анкету', kind: 'test1' },
          status_card: { title: 'Нужно закончить анкету', body: 'Ответьте на вопросы Test1.', tone: 'progress' },
          prep_card: { title: 'Что дальше', body: 'После анкеты покажем следующий шаг.' },
          company_card: { title: 'О компании', body: 'RecruitSmart' },
          help_card: { title: 'Нужна помощь', body: 'Откройте чат MAX' },
        },
      },
      {
        body: {
          journey_step: 'test1',
          questions: [
            {
              id: 'fio',
              prompt: 'Введите <b>ФИО</b>',
              question_index: 0,
              options: [],
            },
          ],
          draft_answers: { fio: 'Иванов Иван Иванович' },
          is_completed: false,
          required_next_action: null,
        },
      },
      {
        body: {
          source: 'profile',
          is_explicit: false,
        },
      },
    )

    render(<MaxMiniAppPage />)

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-test1-review')).toBeInTheDocument()
      expect(screen.getByText(/Проверьте анкету и завершите Test 1/i)).toBeInTheDocument()
    })
    expect(screen.queryByText(/<b>ФИО<\/b>/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Введите ФИО/i)).not.toBeInTheDocument()
  })

  it('opens Test2 immediately on bootstrap when the journey is already at test2', async () => {
    queueJsonResponses(
      {
        body: {
          binding: {
            status: 'bound',
            message: 'Кандидатский доступ готов.',
          },
          session: {
            session_id: 'session-test2-direct',
          },
        },
      },
      {
        body: {
          timeline: [],
          primary_action: {
            key: 'continue_test2',
            label: 'Пройти Тест 2',
            kind: 'test2',
            detail: 'Продолжите Тест 2.',
          },
          status_card: {
            title: 'Открыт Тест 2',
            body: 'Продолжите следующий шаг.',
            tone: 'progress',
          },
          prep_card: { title: 'Что дальше', body: 'После Теста 2 покажем следующий шаг.' },
          company_card: { title: 'О компании', body: 'RecruitSmart' },
          help_card: { title: 'Помощь', body: 'Откройте чат MAX.' },
        },
      },
      {
        body: {
          journey_step: 'test1',
          questions: [
            {
              id: 'fio',
              prompt: 'Введите <b>ФИО</b>',
              question_index: 0,
              options: [],
            },
          ],
          draft_answers: {},
          is_completed: false,
          required_next_action: null,
        },
      },
      {
        body: {
          source: 'explicit',
          is_explicit: true,
        },
      },
      {
        body: {
          journey_step: 'test2',
          questions: [
            {
              id: 'test2-0',
              prompt: 'Выберите правильный вариант',
              question_index: 0,
              options: [
                { label: 'Ответ 1', value: '0' },
                { label: 'Ответ 2', value: '1' },
              ],
            },
          ],
          current_question_index: 0,
          attempts: {},
          is_started: true,
          is_completed: false,
          total_questions: 1,
          passed: null,
        },
      },
    )

    render(<MaxMiniAppPage />)

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-test2')).toBeInTheDocument()
      expect(screen.getByText(/Выберите правильный вариант/i)).toBeInTheDocument()
    })
    expect(screen.queryByTestId('miniapp-test1-review')).not.toBeInTheDocument()
  })

  it('opens Test2 from the home action and submits an answer', async () => {
    queueJsonResponses(
      {
        body: {
          binding: {
            status: 'bound',
            message: 'Кандидатский доступ готов.',
          },
          session: {
            session_id: 'session-test2',
          },
        },
      },
      {
        body: {
          timeline: [],
          primary_action: {
            key: 'continue_test2',
            label: 'Пройти Тест 2',
            kind: 'test2',
            detail: 'Откройте Тест 2 в mini app.',
          },
          status_card: {
            title: 'Открыт Тест 2',
            body: 'Пройдите пост-интервью шаг.',
            tone: 'progress',
          },
          prep_card: { title: 'Что дальше', body: 'После Теста 2 покажем следующий шаг.' },
          company_card: { title: 'О компании', body: 'RecruitSmart' },
          help_card: { title: 'Помощь', body: 'Откройте чат MAX.' },
        },
      },
      {
        body: {
          journey_step: 'test2',
          questions: [],
          draft_answers: {},
          is_completed: true,
          required_next_action: null,
        },
      },
      {
        body: {
          source: 'explicit',
          is_explicit: true,
        },
      },
      {
        body: {
          journey_step: 'test2',
          questions: [
            {
              id: 'test2-0',
              prompt: 'Выберите правильный вариант',
              question_index: 0,
              options: [
                { label: 'Ответ 1', value: '0' },
                { label: 'Ответ 2', value: '1' },
              ],
            },
          ],
          current_question_index: 0,
          attempts: {},
          is_started: true,
          is_completed: false,
          total_questions: 1,
          passed: null,
        },
      },
      {
        body: {
          journey_step: 'intro_day',
          questions: [
            {
              id: 'test2-0',
              prompt: 'Выберите правильный вариант',
              question_index: 0,
              options: [
                { label: 'Ответ 1', value: '0' },
                { label: 'Ответ 2', value: '1' },
              ],
            },
          ],
          current_question_index: null,
          attempts: {
            '0': {
              answers: [{ answer: 1, time: '2030-01-01T10:00:00Z', overtime: false }],
              is_correct: true,
              start_time: '2030-01-01T09:59:00Z',
            },
          },
          is_started: true,
          is_completed: true,
          score: 10,
          correct_answers: 1,
          total_questions: 1,
          passed: true,
          rating: 'A',
          required_next_action: 'wait_intro_day_invitation',
          result_message: 'Тест 2 завершён.',
        },
      },
      {
        body: {
          timeline: [],
          primary_action: {
            key: 'review_intro_day',
            label: 'Проверить детали ознакомительного дня',
            kind: 'intro_day',
          },
          status_card: {
            title: 'Тест 2 завершён',
            body: 'Ожидайте приглашение.',
            tone: 'success',
          },
          prep_card: { title: 'Что дальше', body: 'Следим за приглашением.' },
          company_card: { title: 'О компании', body: 'RecruitSmart' },
          help_card: { title: 'Помощь', body: 'Откройте чат MAX.' },
        },
      },
      {
        body: {
          journey_step: 'test2',
          questions: [],
          draft_answers: {},
          is_completed: true,
          required_next_action: null,
        },
      },
      {
        body: {
          source: 'explicit',
          is_explicit: true,
        },
      },
      {
        status: 409,
        body: {
          detail: 'Intro day details are not available yet.',
        },
      },
    )

    render(<MaxMiniAppPage />)

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-test2')).toBeInTheDocument()
      expect(screen.getByText(/Выберите правильный вариант/i)).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Ответ 2' }))

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-home')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Проверить детали ознакомительного дня' })).toBeInTheDocument()
    })
  })

  it('opens intro day details and confirms participation', async () => {
    queueJsonResponses(
      {
        body: {
          binding: {
            status: 'bound',
            message: 'Кандидатский доступ готов.',
          },
          session: {
            session_id: 'session-intro-day',
          },
        },
      },
      {
        body: {
          timeline: [],
          primary_action: {
            key: 'review_intro_day',
            label: 'Проверить детали ознакомительного дня',
            kind: 'intro_day',
          },
          status_card: {
            title: 'Ознакомительный день назначен',
            body: 'Проверьте детали и подтвердите участие.',
            tone: 'success',
          },
          prep_card: { title: 'Памятка', body: 'Возьмите паспорт.' },
          company_card: { title: 'О компании', body: 'RecruitSmart' },
          help_card: { title: 'Помощь', body: 'Откройте чат MAX.' },
        },
      },
      {
        body: {
          journey_step: 'intro_day',
          questions: [],
          draft_answers: {},
          is_completed: true,
          required_next_action: null,
        },
      },
      {
        body: {
          source: 'explicit',
          is_explicit: true,
        },
      },
      {
        body: {
          booking_id: 77,
          city_name: 'Москва',
          recruiter_name: 'MAX Recruiter',
          start_utc: '2030-01-01T10:00:00Z',
          end_utc: '2030-01-01T11:00:00Z',
          address: 'ул. Пример, 1',
          contact_name: 'Ирина',
          contact_phone: '+7 999 000-00-00',
          status: 'booked',
        },
      },
      {
        body: {
          booking_id: 77,
          city_name: 'Москва',
          recruiter_name: 'MAX Recruiter',
          start_utc: '2030-01-01T10:00:00Z',
          end_utc: '2030-01-01T11:00:00Z',
          address: 'ул. Пример, 1',
          contact_name: 'Ирина',
          contact_phone: '+7 999 000-00-00',
          status: 'confirmed_by_candidate',
        },
      },
      {
        body: {
          timeline: [],
          primary_action: {
            key: 'review_intro_day',
            label: 'Проверить детали ознакомительного дня',
            kind: 'intro_day',
          },
          status_card: {
            title: 'Ознакомительный день назначен',
            body: 'Проверьте детали и подтвердите участие.',
            tone: 'success',
          },
          prep_card: { title: 'Памятка', body: 'Возьмите паспорт.' },
          company_card: { title: 'О компании', body: 'RecruitSmart' },
          help_card: { title: 'Помощь', body: 'Откройте чат MAX.' },
        },
      },
      {
        body: {
          journey_step: 'intro_day',
          questions: [],
          draft_answers: {},
          is_completed: true,
          required_next_action: null,
        },
      },
      {
        body: {
          source: 'explicit',
          is_explicit: true,
        },
      },
    )

    render(<MaxMiniAppPage />)

    await waitFor(() => {
      expect(screen.getByTestId('miniapp-intro-day')).toBeInTheDocument()
      expect(screen.getByText(/ул. Пример, 1/i)).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить участие' }))

    await waitFor(() => {
      expect(screen.getByText(/Участие подтверждено/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Вернуться на главный экран' })).toBeInTheDocument()
    })
  })
})
