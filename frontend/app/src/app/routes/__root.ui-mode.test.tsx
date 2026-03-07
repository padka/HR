import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { RootLayout } from './__root'

const useRouterStateMock = vi.fn()
const useProfileMock = vi.fn()
const useIsMobileMock = vi.fn()

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, activeProps, ...rest }: { children: ReactNode; activeProps?: unknown }) => (
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

    useRouterStateMock.mockReturnValue({ location: { pathname: '/app/login' } })
    useProfileMock.mockReturnValue({
      data: undefined,
      error: undefined,
    })
    useIsMobileMock.mockReturnValue(false)

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
})
