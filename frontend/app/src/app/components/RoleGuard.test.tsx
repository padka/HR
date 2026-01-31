import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { RoleGuard } from './RoleGuard'
import type { ReactNode } from 'react'

const useProfileMock = vi.fn()
const navigateMock = vi.fn()

vi.mock('@/app/hooks/useProfile', () => ({
  useProfile: (...args: unknown[]) => useProfileMock(...args),
}))

vi.mock('@tanstack/react-router', () => ({
  Link: ({ to, children, ...rest }: { to: string; children: ReactNode }) => (
    <a href={to} {...rest}>{children}</a>
  ),
  useNavigate: () => navigateMock,
}))

describe('RoleGuard', () => {
  beforeEach(() => {
    useProfileMock.mockReset()
    navigateMock.mockReset()
  })

  it('shows loading state while profile loads', () => {
    useProfileMock.mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined,
    })

    render(
      <RoleGuard allow={['admin']}>
        <div>content</div>
      </RoleGuard>
    )

    expect(screen.getByText('Загрузка…')).toBeInTheDocument()
  })

  it('shows login prompt on 401 errors', () => {
    useProfileMock.mockReturnValue({
      isLoading: false,
      isError: true,
      error: { status: 401, message: 'unauthorized' },
      refetch: vi.fn(),
    })

    render(
      <RoleGuard allow={['admin']}>
        <div>content</div>
      </RoleGuard>
    )

    expect(screen.getByText('Нужен вход')).toBeInTheDocument()
    expect(screen.getByText('Открыть вход')).toBeInTheDocument()
  })

  it('renders children when role is allowed', () => {
    useProfileMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { principal: { type: 'admin', id: 1 } },
    })

    render(
      <RoleGuard allow={['admin']}>
        <div>content</div>
      </RoleGuard>
    )

    expect(screen.getByText('content')).toBeInTheDocument()
  })

  it('redirects when role is not allowed', async () => {
    useProfileMock.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { principal: { type: 'recruiter', id: 2 } },
    })

    render(
      <RoleGuard allow={['admin']}>
        <div>content</div>
      </RoleGuard>
    )

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith({ to: '/app/dashboard', replace: true })
    })

    expect(screen.getByText('Раздел недоступен для текущей роли.')).toBeInTheDocument()
  })
})
