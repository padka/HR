import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ErrorBoundary } from './ErrorBoundary'

function Bomb(): JSX.Element {
  throw new Error('boom')
}

describe('ErrorBoundary', () => {
  it('renders fallback UI when child throws', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    const onWindowError = (event: ErrorEvent) => {
      // React will surface render errors to the global handler in jsdom.
      // Prevent jsdom from printing "Uncaught [Error: boom]" noise for this test.
      event.preventDefault()
    }
    window.addEventListener('error', onWindowError)

    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>
    )

    expect(screen.getByText('Что-то пошло не так')).toBeInTheDocument()
    expect(screen.getByText('boom')).toBeInTheDocument()

    window.removeEventListener('error', onWindowError)
    consoleError.mockRestore()
  })
})
