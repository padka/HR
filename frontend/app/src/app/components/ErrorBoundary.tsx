import React, { Component, ErrorInfo, ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div style={{
          padding: '24px',
          margin: '24px',
          background: 'rgba(240, 115, 115, 0.1)',
          border: '1px solid rgba(240, 115, 115, 0.3)',
          borderRadius: '14px',
        }}>
          <h2 style={{ margin: '0 0 12px', color: '#f07373', fontSize: '18px' }}>
            Что-то пошло не так
          </h2>
          <p style={{ margin: '0 0 16px', color: 'var(--muted)', fontSize: '14px' }}>
            {this.state.error?.message || 'Произошла непредвиденная ошибка'}
          </p>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button
              onClick={this.handleReset}
              style={{
                padding: '8px 16px',
                background: 'rgba(255, 255, 255, 0.1)',
                border: '1px solid rgba(255, 255, 255, 0.2)',
                borderRadius: '8px',
                color: 'var(--fg)',
                cursor: 'pointer',
              }}
            >
              Попробовать снова
            </button>
            <button
              onClick={() => window.location.reload()}
              style={{
                padding: '8px 16px',
                background: 'transparent',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                borderRadius: '8px',
                color: 'var(--muted)',
                cursor: 'pointer',
              }}
            >
              Перезагрузить страницу
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

// Hook for functional components to trigger error boundary
export function useErrorHandler() {
  const [, setError] = React.useState<Error | null>(null)

  return React.useCallback((error: Error) => {
    setError(() => {
      throw error
    })
  }, [])
}
