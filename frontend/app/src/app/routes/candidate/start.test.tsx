import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { CandidateStartPage } from './start'

const exchangeCandidatePortalTokenMock = vi.fn()
const fetchCandidatePortalJourneyMock = vi.fn()
const parseCandidatePortalErrorMock = vi.fn()
const resolveCandidateEntryGatewayMock = vi.fn()
const selectCandidateEntryChannelMock = vi.fn()
const startCandidateSharedAccessChallengeMock = vi.fn()
const switchCandidateEntryChannelMock = vi.fn()
const verifyCandidateSharedAccessCodeMock = vi.fn()
const navigateMock = vi.fn()
const setQueryDataMock = vi.fn()
const useParamsMock = vi.fn()

vi.mock('@/api/candidate', () => ({
  exchangeCandidatePortalToken: (...args: unknown[]) => exchangeCandidatePortalTokenMock(...args),
  fetchCandidatePortalJourney: (...args: unknown[]) => fetchCandidatePortalJourneyMock(...args),
  parseCandidatePortalError: (...args: unknown[]) => parseCandidatePortalErrorMock(...args),
  resolveCandidateEntryGateway: (...args: unknown[]) => resolveCandidateEntryGatewayMock(...args),
  selectCandidateEntryChannel: (...args: unknown[]) => selectCandidateEntryChannelMock(...args),
  startCandidateSharedAccessChallenge: (...args: unknown[]) => startCandidateSharedAccessChallengeMock(...args),
  switchCandidateEntryChannel: (...args: unknown[]) => switchCandidateEntryChannelMock(...args),
  verifyCandidateSharedAccessCode: (...args: unknown[]) => verifyCandidateSharedAccessCodeMock(...args),
}))

vi.mock('@/api/client', () => ({
  queryClient: {
    setQueryData: (...args: unknown[]) => setQueryDataMock(...args),
  },
}))

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => navigateMock,
  useParams: () => useParamsMock(),
}))

describe('CandidateStartPage', () => {
  beforeEach(() => {
    exchangeCandidatePortalTokenMock.mockReset()
    fetchCandidatePortalJourneyMock.mockReset()
    parseCandidatePortalErrorMock.mockReset()
    resolveCandidateEntryGatewayMock.mockReset()
    selectCandidateEntryChannelMock.mockReset()
    startCandidateSharedAccessChallengeMock.mockReset()
    switchCandidateEntryChannelMock.mockReset()
    verifyCandidateSharedAccessCodeMock.mockReset()
    navigateMock.mockReset()
    setQueryDataMock.mockReset()
    useParamsMock.mockReturnValue({ token: 'signed-token' })
    window.history.pushState({}, '', '/candidate/start')
    window.sessionStorage.clear()
    window.localStorage.clear()
    ;(window as typeof window & { WebApp?: unknown }).WebApp = undefined
    ;(window as typeof window & { Telegram?: unknown }).Telegram = undefined
  })

  it('exchanges token and redirects into journey', async () => {
    exchangeCandidatePortalTokenMock.mockResolvedValue({
      candidate: { id: 1, candidate_id: 'cid' },
      journey: { current_step: 'profile' },
    })

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(exchangeCandidatePortalTokenMock).toHaveBeenCalledWith('signed-token')
      expect(setQueryDataMock).toHaveBeenCalledWith(
        ['candidate-portal-journey'],
        expect.objectContaining({
          candidate: expect.objectContaining({ id: 1 }),
        }),
      )
      expect(navigateMock).toHaveBeenCalledWith({ to: '/candidate/journey' })
    })
  })

  it('shows portal error when exchange fails', async () => {
    exchangeCandidatePortalTokenMock.mockRejectedValue(new Error('Ссылка устарела'))
    parseCandidatePortalErrorMock.mockReturnValue({
      message: 'Ссылка устарела',
      state: 'needs_new_link',
      status: 401,
    })

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(screen.getByText('Продолжим через выбор канала')).toBeInTheDocument()
      expect(screen.getByText('Ссылка устарела')).toBeInTheDocument()
    })
  })

  it('falls back to the existing portal session when exchange token is stale', async () => {
    exchangeCandidatePortalTokenMock.mockRejectedValue(
      Object.assign(new Error('Ссылка устарела'), { status: 401 }),
    )
    fetchCandidatePortalJourneyMock.mockResolvedValue({
      candidate: { id: 1, candidate_id: 'cid' },
      journey: { current_step: 'profile' },
    })

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(fetchCandidatePortalJourneyMock).toHaveBeenCalled()
      expect(setQueryDataMock).toHaveBeenCalledWith(
        ['candidate-portal-journey'],
        expect.objectContaining({
          candidate: expect.objectContaining({ id: 1 }),
        }),
      )
      expect(navigateMock).toHaveBeenCalledWith({ to: '/candidate/journey' })
    })
  })

  it('shows a neutral candidate entry landing on bare start without tokens', async () => {
    useParamsMock.mockReturnValue({ token: '' })
    window.sessionStorage.clear()

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(screen.getByText('Телефон из вашего отклика')).toBeInTheDocument()
      expect(fetchCandidatePortalJourneyMock).not.toHaveBeenCalled()
      expect(exchangeCandidatePortalTokenMock).not.toHaveBeenCalled()
    })
  })

  it('starts shared access challenge and shows code verification', async () => {
    useParamsMock.mockReturnValue({ token: '' })
    startCandidateSharedAccessChallengeMock.mockResolvedValue({
      ok: true,
      challenge_token: 'challenge-token',
      expires_in_seconds: 600,
      retry_after_seconds: 60,
      message: 'Если номер найден, мы отправили код в связанный канал кандидата.',
    })

    render(<CandidateStartPage />)

    const phoneInput = await screen.findByPlaceholderText('+7 900 000 00 00')
    fireEvent.change(phoneInput, {
      target: { value: '+7 999 000 00 00' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Получить код входа' }))

    await waitFor(() => {
      expect(startCandidateSharedAccessChallengeMock).toHaveBeenCalledWith('+7 999 000 00 00')
      expect(screen.getByText('Код отправлен')).toBeInTheDocument()
    })
  })

  it('verifies shared access code and shows the chooser', async () => {
    useParamsMock.mockReturnValue({ token: '' })
    startCandidateSharedAccessChallengeMock.mockResolvedValue({
      ok: true,
      challenge_token: 'challenge-token',
      expires_in_seconds: 600,
      retry_after_seconds: 60,
      message: 'Если номер найден, мы отправили код в связанный канал кандидата.',
    })
    verifyCandidateSharedAccessCodeMock.mockResolvedValue({
      candidate: {
        id: 1,
        candidate_id: 'cid',
        fio: 'Иван Петров',
        city: 'Москва',
        vacancy_label: 'Оператор склада',
        status: 'waiting_slot',
        status_label: 'Ожидает слот',
      },
      company: {
        name: 'SMART SERVICE',
        summary: 'Выберите мессенджер.',
        highlights: ['Test 1', 'Слот'],
      },
      journey: {
        session_id: 7,
        current_step: 'screening',
        current_step_label: 'Анкета',
        next_action: 'Выберите удобный канал.',
        last_entry_channel: 'web',
        available_channels: ['web', 'max', 'telegram'],
        channel_options: {
          web: { channel: 'web', enabled: true, launch_url: '/candidate/journey', type: 'cabinet' },
          max: { channel: 'max', enabled: true, launch_url: 'https://max.ru/id1_bot?startapp=token', type: 'external' },
          telegram: { channel: 'telegram', enabled: true, launch_url: 'https://t.me/test_bot?start=token', type: 'external' },
        },
      },
    })

    render(<CandidateStartPage />)

    const phoneInput = await screen.findByPlaceholderText('+7 900 000 00 00')
    fireEvent.change(phoneInput, {
      target: { value: '+7 999 000 00 00' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Получить код входа' }))

    await waitFor(() => {
      expect(startCandidateSharedAccessChallengeMock).toHaveBeenCalled()
    })

    fireEvent.change(screen.getByPlaceholderText('123456'), {
      target: { value: '123456' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить код' }))

    await waitFor(() => {
      expect(verifyCandidateSharedAccessCodeMock).toHaveBeenCalledWith('challenge-token', '123456')
      expect(screen.getByText('Выберите мессенджер')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Открыть MAX' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Открыть Telegram' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Открыть в браузере' })).toBeInTheDocument()
    })
  })

  it('shows active-stage copy when candidate already has progress in the system', async () => {
    useParamsMock.mockReturnValue({ token: '' })
    startCandidateSharedAccessChallengeMock.mockResolvedValue({
      ok: true,
      challenge_token: 'challenge-token',
      expires_in_seconds: 600,
      retry_after_seconds: 60,
      message: 'Если номер найден, мы отправили код в связанный канал кандидата.',
    })
    verifyCandidateSharedAccessCodeMock.mockResolvedValue({
      candidate: {
        id: 1,
        candidate_id: 'cid',
        fio: 'Иван Петров',
        city: 'Москва',
        vacancy_label: 'Оператор склада',
        status: 'interview_scheduled',
        status_label: 'Назначено собеседование',
      },
      company: {
        name: 'SMART SERVICE',
        summary: 'Откройте текущий этап в нужном мессенджере.',
        highlights: ['Собеседование', 'История'],
      },
      journey: {
        session_id: 7,
        current_step: 'status',
        current_step_label: 'Статус',
        next_action: 'У вас уже есть назначенное собеседование. Откройте текущий путь кандидата.',
        last_entry_channel: 'telegram',
        available_channels: ['web', 'max', 'telegram'],
        channel_options: {
          web: { channel: 'web', enabled: true, launch_url: '/candidate/journey', type: 'cabinet' },
          max: { channel: 'max', enabled: true, launch_url: 'https://max.ru/id1_bot?startapp=token', type: 'external' },
          telegram: { channel: 'telegram', enabled: true, launch_url: 'https://t.me/test_bot?start=token', type: 'external' },
        },
      },
    })

    render(<CandidateStartPage />)

    fireEvent.change(await screen.findByPlaceholderText('+7 900 000 00 00'), {
      target: { value: '+7 999 000 00 00' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Получить код входа' }))

    await waitFor(() => {
      expect(startCandidateSharedAccessChallengeMock).toHaveBeenCalled()
    })

    fireEvent.change(screen.getByPlaceholderText('123456'), {
      target: { value: '123456' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить код' }))

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'У вас уже есть активный этап' })).toBeInTheDocument()
      expect(screen.getByText('Текущая активность')).toBeInTheDocument()
      expect(screen.getByText(/не запустит процесс заново/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Открыть в браузере' })).toBeInTheDocument()
    })
  })

  it('continues existing portal session when a stored access token exists', async () => {
    useParamsMock.mockReturnValue({ token: '' })
    window.sessionStorage.setItem('candidate-portal:access-token', 'stored-access-token')
    exchangeCandidatePortalTokenMock.mockResolvedValue({
      candidate: { id: 1, candidate_id: 'cid' },
      journey: { current_step: 'profile' },
    })

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(exchangeCandidatePortalTokenMock).toHaveBeenCalledWith('stored-access-token')
      expect(navigateMock).toHaveBeenCalledWith({ to: '/candidate/journey' })
    })
  })

  it('uses MAX start_param from bridge when direct token is missing', async () => {
    useParamsMock.mockReturnValue({ token: '' })
    window.sessionStorage.clear()
    window.history.pushState({}, '', '/candidate/start')
    const readyMock = vi.fn()
    ;(window as typeof window & { WebApp?: { initData?: string; initDataUnsafe?: { start_param?: string }; ready?: () => void } }).WebApp = {
      initData: 'auth_date=123&user=%7B%22id%22%3A%22mx-user%22%7D&hash=test',
      initDataUnsafe: { start_param: 'max-invite-token' },
      ready: readyMock,
    }
    exchangeCandidatePortalTokenMock.mockResolvedValue({
      candidate: { id: 1, candidate_id: 'cid' },
      journey: { current_step: 'profile' },
    })

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(readyMock).toHaveBeenCalled()
      expect(exchangeCandidatePortalTokenMock).toHaveBeenCalledWith('max-invite-token', {
        maxWebAppData: 'auth_date=123&user=%7B%22id%22%3A%22mx-user%22%7D&hash=test',
      })
      expect(navigateMock).toHaveBeenCalledWith({ to: '/candidate/journey' })
    })
  })

  it('supports startapp query parameter fallback', async () => {
    useParamsMock.mockReturnValue({ token: '' })
    window.sessionStorage.clear()
    window.history.pushState({}, '', '/candidate/start?startapp=query-token')
    exchangeCandidatePortalTokenMock.mockResolvedValue({
      candidate: { id: 1, candidate_id: 'cid' },
      journey: { current_step: 'profile' },
    })

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(exchangeCandidatePortalTokenMock).toHaveBeenCalledWith('query-token')
      expect(navigateMock).toHaveBeenCalledWith({ to: '/candidate/journey' })
    })
  })

  it('prefers fresh startapp token over stale session storage token', async () => {
    useParamsMock.mockReturnValue({ token: '' })
    window.sessionStorage.setItem('candidate-portal:access-token', 'stale-token')
    window.history.pushState({}, '', '/candidate/start?startapp=fresh-token')
    exchangeCandidatePortalTokenMock.mockResolvedValue({
      candidate: { id: 1, candidate_id: 'cid' },
      journey: { current_step: 'profile' },
    })

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(exchangeCandidatePortalTokenMock).toHaveBeenCalledWith('fresh-token')
      expect(navigateMock).toHaveBeenCalledWith({ to: '/candidate/journey' })
    })
  })

  it('does not fall back to stale stored token when a fresh link fails', async () => {
    useParamsMock.mockReturnValue({ token: '' })
    window.sessionStorage.setItem('candidate-portal:access-token', 'stale-token')
    window.history.pushState({}, '', '/candidate/start?startapp=fresh-token')
    exchangeCandidatePortalTokenMock.mockRejectedValue(
      Object.assign(new Error('Ссылка устарела'), { status: 401 }),
    )
    fetchCandidatePortalJourneyMock.mockRejectedValue(
      Object.assign(new Error('Ссылка устарела'), { status: 401 }),
    )
    parseCandidatePortalErrorMock.mockImplementation((error: unknown) => ({
      message: error instanceof Error ? error.message : 'Ссылка устарела',
      state: 'needs_new_link',
      status: 401,
    }))

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(fetchCandidatePortalJourneyMock).toHaveBeenCalledWith({ skipStoredPortalToken: true })
      expect(screen.getByText('Продолжим через выбор канала')).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Вернуться к выбору способа входа' })).toHaveAttribute('href', '/candidate/start')
    })
  })

  it('recovers into the stored HH entry chooser when direct cabinet token is stale', async () => {
    useParamsMock.mockReturnValue({ token: '' })
    window.sessionStorage.setItem('candidate-portal:access-token', 'stale-token')
    window.localStorage.setItem('candidate-portal:entry-token', 'hh-entry-token')
    window.history.pushState({}, '', '/candidate/start?startapp=fresh-token')
    exchangeCandidatePortalTokenMock.mockRejectedValue(
      Object.assign(new Error('Ссылка устарела'), { status: 401 }),
    )
    fetchCandidatePortalJourneyMock.mockRejectedValue(
      Object.assign(new Error('Ссылка устарела'), { status: 401 }),
    )
    resolveCandidateEntryGatewayMock.mockResolvedValue({
      candidate: {
        id: 1,
        candidate_id: 'cid',
        fio: 'Иван Петров',
        city: 'Москва',
        vacancy_label: 'Оператор склада',
        company: 'SMART SERVICE',
      },
      journey: {
        session_id: 7,
        current_step: 'screening',
        current_step_label: 'Анкета',
        status_label: 'Тест 1',
        next_action: 'Выберите удобный канал, чтобы пройти анкету.',
      },
      company_preview: {
        summary: 'Можно продолжить в MAX или Telegram.',
        highlights: ['Тест 1', 'Слот', 'Чат с рекрутером'],
      },
      suggested_channel: 'max',
      options: {
        web: { channel: 'web', enabled: true, launch_url: 'https://crm.example.test/candidate/start?start=token', type: 'cabinet' },
        max: { channel: 'max', enabled: true, launch_url: 'https://max.ru/id1_bot?startapp=token', type: 'external' },
        telegram: { channel: 'telegram', enabled: true, launch_url: 'https://t.me/test_bot?start=token', type: 'external' },
      },
    })

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(resolveCandidateEntryGatewayMock).toHaveBeenCalledWith('hh-entry-token')
      expect(screen.getByText('Выберите мессенджер')).toBeInTheDocument()
    })
  })

  it('falls back to the neutral landing when local resume is stale', async () => {
    useParamsMock.mockReturnValue({ token: '' })
    window.sessionStorage.setItem('candidate-portal:access-token', 'stale-token')
    exchangeCandidatePortalTokenMock.mockRejectedValue(
      Object.assign(new Error('Сессия устарела'), { status: 401 }),
    )
    fetchCandidatePortalJourneyMock.mockRejectedValue(
      Object.assign(new Error('Сессия устарела'), { status: 401 }),
    )

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(screen.getByText('Начните путь в мессенджере')).toBeInTheDocument()
      expect(screen.queryByText('Продолжить на этом устройстве')).not.toBeInTheDocument()
    })
  })

  it('can reopen the stored HH chooser from the neutral landing on the same device', async () => {
    useParamsMock.mockReturnValue({ token: '' })
    window.localStorage.setItem('candidate-portal:entry-token', 'hh-entry-token')
    resolveCandidateEntryGatewayMock.mockResolvedValue({
      candidate: {
        id: 1,
        candidate_id: 'cid',
        fio: 'Иван Петров',
        city: 'Москва',
        vacancy_label: 'Оператор склада',
        company: 'SMART SERVICE',
      },
      journey: {
        session_id: 7,
        current_step: 'screening',
        current_step_label: 'Анкета',
        status_label: 'Тест 1',
        next_action: 'Выберите удобный канал, чтобы продолжить.',
      },
      company_preview: {
        summary: 'Можно продолжить в MAX или Telegram.',
        highlights: ['Тест 1', 'Слот', 'Чат с рекрутером'],
      },
      suggested_channel: 'max',
      options: {
        web: { channel: 'web', enabled: true, launch_url: 'https://crm.example.test/candidate/start?start=token', type: 'cabinet' },
        max: { channel: 'max', enabled: true, launch_url: 'https://max.ru/id1_bot?startapp=token', type: 'external' },
        telegram: { channel: 'telegram', enabled: true, launch_url: 'https://t.me/test_bot?start=token', type: 'external' },
      },
    })

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(screen.getByText('Начните путь в мессенджере')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Продолжить на этом устройстве' }))

    await waitFor(() => {
      expect(resolveCandidateEntryGatewayMock).toHaveBeenCalledWith('hh-entry-token')
      expect(screen.getByText('Выберите мессенджер')).toBeInTheDocument()
    })
  })

  it('renders HH entry chooser from entry token', async () => {
    useParamsMock.mockReturnValue({ token: '' })
    window.history.pushState({}, '', '/candidate/start?entry=hh-entry-token')
    resolveCandidateEntryGatewayMock.mockResolvedValue({
      candidate: {
        id: 1,
        candidate_id: 'cid',
        fio: 'Иван Петров',
        city: 'Москва',
        vacancy_label: 'Оператор склада',
        company: 'SMART SERVICE',
      },
      journey: {
        session_id: 7,
        current_step: 'screening',
        current_step_label: 'Анкета',
        status_label: 'Тест 1',
        next_action: 'Выберите удобный канал, чтобы пройти анкету.',
      },
      company_preview: {
        summary: 'Можно продолжить в MAX или Telegram.',
        highlights: ['Тест 1', 'Слот', 'Чат с рекрутером'],
      },
      suggested_channel: 'max',
      options: {
        web: { channel: 'web', enabled: true, launch_url: 'https://crm.example.test/candidate/start?start=token', type: 'cabinet' },
        max: { channel: 'max', enabled: true, launch_url: 'https://max.ru/id1_bot?startapp=token', type: 'external' },
        telegram: { channel: 'telegram', enabled: false, reason_if_blocked: 'telegram_entry_blocked', type: 'external' },
      },
    })

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(resolveCandidateEntryGatewayMock).toHaveBeenCalledWith('hh-entry-token')
      expect(screen.getByText('Выберите мессенджер')).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Открыть кабинет' })).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Открыть MAX' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Открыть Telegram' })).toBeInTheDocument()
      expect(screen.getByText('telegram_entry_blocked')).toBeInTheDocument()
    })
  })

  it('shows blocked browser fallback state without inventing a new recovery path', async () => {
    useParamsMock.mockReturnValue({ token: '' })
    window.history.pushState({}, '', '/candidate/start?entry=hh-entry-token')
    resolveCandidateEntryGatewayMock.mockResolvedValue({
      candidate: {
        id: 1,
        candidate_id: 'cid',
        fio: 'Иван Петров',
        city: 'Москва',
        vacancy_label: 'Оператор склада',
        company: 'SMART SERVICE',
      },
      journey: {
        session_id: 7,
        current_step: 'status',
        current_step_label: 'Статус',
        status_label: 'Ожидает подтверждение',
        next_action: 'Продолжите текущий этап в доступном канале.',
      },
      company_preview: {
        summary: 'Продолжите текущий этап.',
        highlights: ['Статус', 'История'],
      },
      suggested_channel: 'max',
      fallback_policy: 'messenger_first',
      options: {
        web: {
          channel: 'web',
          enabled: false,
          launch_url: null,
          reason_if_blocked: 'browser_portal_temporarily_blocked',
          type: 'cabinet',
        },
        max: { channel: 'max', enabled: true, launch_url: 'https://max.ru/id1_bot?startapp=token', type: 'external' },
        telegram: { channel: 'telegram', enabled: false, reason_if_blocked: 'telegram_entry_blocked', type: 'external' },
      },
    })

    render(<CandidateStartPage />)

    await waitFor(() => {
      expect(screen.getByText('browser_portal_temporarily_blocked')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Открыть в браузере' })).toBeDisabled()
    })
  })
})
