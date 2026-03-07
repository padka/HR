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
        <div className="ui-error-boundary ui-surface ui-surface--base" data-testid="error-boundary-fallback">
          <h2 className="ui-error-boundary__title">
            Что-то пошло не так
          </h2>
          <p className="ui-error-boundary__text">
            {this.state.error?.message || 'Произошла непредвиденная ошибка'}
          </p>
          <div className="ui-error-boundary__actions">
            <button onClick={this.handleReset} className="ui-btn ui-btn--ghost ui-btn--sm">
              Попробовать снова
            </button>
            <button onClick={() => window.location.reload()} className="ui-btn ui-btn--ghost ui-btn--sm">
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
