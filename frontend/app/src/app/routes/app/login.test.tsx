import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LoginPage } from './login'

const fetchMock = vi.fn()

describe('LoginPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('associates labels with their inputs', () => {
    render(<LoginPage />)

    expect(screen.getByLabelText('Логин')).toHaveAttribute('id', 'login-username')
    expect(screen.getByLabelText('Пароль')).toHaveAttribute('id', 'login-password')
  })

  it('shows summary and inline errors when required fields are empty', async () => {
    render(<LoginPage />)

    fireEvent.click(screen.getByRole('button', { name: 'Войти' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Проверьте обязательные поля и попробуйте снова.')
    expect(screen.getByText('Введите логин.')).toBeInTheDocument()
    expect(screen.getByText('Введите пароль.')).toBeInTheDocument()
  })

  it('shows a deterministic pending state while the request is in flight', async () => {
    let resolveFetch: ((value: Response) => void) | null = null
    fetchMock.mockImplementation(
      () =>
        new Promise<Response>((resolve) => {
          resolveFetch = resolve
        }),
    )

    render(<LoginPage />)

    fireEvent.change(screen.getByLabelText('Логин'), { target: { value: 'admin' } })
    fireEvent.change(screen.getByLabelText('Пароль'), { target: { value: 'secret' } })
    fireEvent.click(screen.getByRole('button', { name: 'Войти' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Вход...' })).toBeDisabled()
    })

    await act(async () => {
      resolveFetch?.(new Response(null, { status: 401 }))
      await Promise.resolve()
    })
  })

  it('shows credential error copy for unauthorized responses', async () => {
    fetchMock.mockResolvedValue(
      new Response(null, { status: 401 }),
    )

    render(<LoginPage />)

    fireEvent.change(screen.getByLabelText('Логин'), { target: { value: 'admin' } })
    fireEvent.change(screen.getByLabelText('Пароль'), { target: { value: 'secret' } })
    fireEvent.click(screen.getByRole('button', { name: 'Войти' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Неверные учётные данные.')
  })

  it('shows server error copy for non-auth backend failures', async () => {
    fetchMock.mockResolvedValue(
      new Response(null, { status: 503 }),
    )

    render(<LoginPage />)

    fireEvent.change(screen.getByLabelText('Логин'), { target: { value: 'admin' } })
    fireEvent.change(screen.getByLabelText('Пароль'), { target: { value: 'secret' } })
    fireEvent.click(screen.getByRole('button', { name: 'Войти' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось выполнить вход. Попробуйте ещё раз.')
  })
})
