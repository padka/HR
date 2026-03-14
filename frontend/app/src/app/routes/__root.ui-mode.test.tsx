import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/api/client'
import { RootLayout } from './__root'

const useRouterStateMock = vi.fn()
const useProfileMock = vi.fn()
const useIsMobileMock = vi.fn()
const apiFetchMock = vi.mocked(apiFetch)

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, activeProps: _activeProps, ...rest }: { children: ReactNode; activeProps?: unknown }) => (
    <a {...rest}>{children}</a>
  ),
  Outlet: () => <div data-testid="root-layout-outlet" />,
  useRouterState: () => useRouterStateMock(),
}))

vi.mock('@/app/hooks/useProfile', () => ({
  useProfile: () => useProfileMock(),
}))

vi.mock('@/app/hooks/useIsMobile', () => ({
  useIsMobile: () => useIsMobileMock(),
}))

vi.mock('@/api/client', () => ({
  apiFetch: vi.fn(),
  queryClient: {
    setQueryData: vi.fn(),
  },
}))

describe('RootLayout liquid glass mode', () => {
  beforeEach(() => {
    localStorage.clear()
    delete document.documentElement.dataset.ui
    delete document.documentElement.dataset.motion
    document.title = 'RecruitSmart'

    useRouterStateMock.mockReturnValue({ location: { pathname: '/app/login' } })
    useProfileMock.mockReturnValue({
      data: undefined,
      error: undefined,
    })
    useIsMobileMock.mockReturnValue(false)
    apiFetchMock.mockReset()

    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
  })

  afterEach(() => {
    delete document.documentElement.dataset.ui
    delete document.documentElement.dataset.motion
    vi.restoreAllMocks()
  })

  it('enables liquid glass root mode when localStorage override is 1', async () => {
    localStorage.setItem('ui:liquidGlassV2', '1')
    render(<RootLayout />)

    await waitFor(() => {
      expect(document.documentElement.dataset.ui).toBe('liquid-glass-v2')
      expect(document.documentElement.dataset.motion).toBe('full')
    })
  })

  it('enables liquid glass root mode by default when no override is set', async () => {
    render(<RootLayout />)

    await waitFor(() => {
      expect(document.documentElement.dataset.ui).toBe('liquid-glass-v2')
      expect(document.documentElement.dataset.motion).toBe('full')
    })
  })

  it('disables liquid glass root mode when localStorage override is 0', async () => {
    localStorage.setItem('ui:liquidGlassV2', '0')
    render(<RootLayout />)

    await waitFor(() => {
      expect(document.documentElement.dataset.ui).toBeUndefined()
      expect(document.documentElement.dataset.motion).toBe('full')
    })
  })

  it('sets reduced motion mode from media preference', async () => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query.includes('prefers-reduced-motion'),
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })

    localStorage.setItem('ui:liquidGlassV2', '1')
    render(<RootLayout />)

    await waitFor(() => {
      expect(document.documentElement.dataset.ui).toBe('liquid-glass-v2')
      expect(document.documentElement.dataset.motion).toBe('reduced')
    })
  })

  it('keeps the mobile more sheet out of the DOM until opened', async () => {
    useRouterStateMock.mockReturnValue({ location: { pathname: '/app/slots' } })
    useProfileMock.mockReturnValue({
      data: {
        principal: { type: 'admin', id: 1, name: 'Admin' },
      },
      error: undefined,
    })
    useIsMobileMock.mockReturnValue(true)

    render(<RootLayout />)

    expect(screen.queryByRole('dialog', { name: 'Ещё разделы' })).not.toBeInTheDocument()
    expect(document.querySelector('.background-scene')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Ещё' }))

    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: 'Ещё разделы' })).toBeVisible()
    })
  })

  it('shows a visible chat badge and title counter for unread candidate messages', async () => {
    useRouterStateMock.mockReturnValue({ location: { pathname: '/app/dashboard' } })
    useProfileMock.mockReturnValue({
      data: {
        principal: { type: 'admin', id: 1, name: 'Admin' },
      },
      error: undefined,
    })
    useIsMobileMock.mockReturnValue(false)

    apiFetchMock.mockImplementation((input: string | Request | URL) => {
      const url = String(input)
      if (url === '/candidate-chat/threads') {
        return Promise.resolve({
          threads: [
            {
              id: 17,
              candidate_id: 501,
              title: 'Иван Петров',
              created_at: '2026-03-08T15:30:00Z',
              last_message_at: '2026-03-08T15:31:00Z',
              last_message: {
                text: 'Подскажите, можно перенести собеседование?',
                direction: 'inbound',
                created_at: '2026-03-08T15:31:00Z',
              },
              unread_count: 3,
            },
          ],
          latest_event_at: '2026-03-08T15:31:00Z',
        })
      }
      if (url.startsWith('/candidate-chat/threads/updates?')) {
        return new Promise(() => {})
      }
      return Promise.resolve({ threads: [], latest_event_at: null })
    })

    render(<RootLayout />)

    await waitFor(() => {
      expect(document.title).toBe('(3) Дашборд • RecruitSmart')
      expect(document.querySelector('.vision-nav__badge')?.textContent).toBe('3')
    })
  })

  it('renders an alert-style chat toast for a fresh inbound message', async () => {
    useRouterStateMock.mockReturnValue({ location: { pathname: '/app/dashboard' } })
    useProfileMock.mockReturnValue({
      data: {
        principal: { type: 'admin', id: 1, name: 'Admin' },
      },
      error: undefined,
    })
    useIsMobileMock.mockReturnValue(false)

    let updateSent = false
    apiFetchMock.mockImplementation((input: string | Request | URL) => {
      const url = String(input)
      if (url === '/candidate-chat/threads') {
        return Promise.resolve({
          threads: [
            {
              id: 17,
              candidate_id: 501,
              title: 'Иван Петров',
              created_at: '2026-03-08T15:30:00Z',
              last_message_at: '2026-03-08T15:30:00Z',
              last_message: {
                text: 'Добрый день',
                direction: 'outbound',
                created_at: '2026-03-08T15:30:00Z',
              },
              unread_count: 0,
            },
          ],
          latest_event_at: '2026-03-08T15:30:00Z',
        })
      }
      if (url.startsWith('/candidate-chat/threads/updates?')) {
        if (!updateSent) {
          updateSent = true
          return Promise.resolve({
            updated: true,
            latest_event_at: '2026-03-08T15:34:00Z',
            threads: [
              {
                id: 17,
                candidate_id: 501,
                title: 'Иван Петров',
                created_at: '2026-03-08T15:30:00Z',
                last_message_at: '2026-03-08T15:34:00Z',
                last_message: {
                  text: 'Можете перенести встречу на вечер?',
                  direction: 'inbound',
                  created_at: '2026-03-08T15:34:00Z',
                },
                unread_count: 1,
              },
            ],
          })
        }
        return new Promise(() => {})
      }
      return Promise.resolve({ threads: [], latest_event_at: null })
    })

    render(<RootLayout />)

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
      expect(screen.getByText('Новое сообщение')).toBeInTheDocument()
      expect(screen.getByText('Откройте вкладку «Чаты», чтобы ответить кандидату')).toBeInTheDocument()
      expect(document.querySelector('.chat-toast__count')?.textContent).toBe('1')
    })
  })
})
