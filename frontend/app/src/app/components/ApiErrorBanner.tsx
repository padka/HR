import type { ReactNode } from 'react'

type ApiErrorBannerProps = {
  error: unknown
  title?: string
  retryLabel?: string
  onRetry?: () => void
  children?: ReactNode
  className?: string
}

function extractErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message
  }
  if (typeof error === 'string' && error.trim()) {
    return error
  }
  return 'Не удалось выполнить запрос. Попробуйте ещё раз.'
}

export function ApiErrorBanner({
  error,
  title = 'Ошибка API',
  retryLabel = 'Повторить',
  onRetry,
  children,
  className,
}: ApiErrorBannerProps) {
  const message = extractErrorMessage(error)
  return (
    <div
      className={className || 'glass panel text-danger'}
      role="alert"
      style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
    >
      <strong>{title}</strong>
      <span>{message}</span>
      {children}
      {onRetry && (
        <div>
          <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={onRetry}>
            {retryLabel}
          </button>
        </div>
      )}
    </div>
  )
}

export default ApiErrorBanner
