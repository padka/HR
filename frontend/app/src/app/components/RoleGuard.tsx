import { ReactNode, useEffect } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { useProfile } from '@/app/hooks/useProfile'
import { AuthCheckState, AuthRequiredState, EmptyState, ErrorState } from './AppStates'

type RoleGuardProps = {
  allow: Array<'admin' | 'recruiter'>
  children: ReactNode
}

export function RoleGuard({ allow, children }: RoleGuardProps) {
  const { data, isLoading, isError, error, refetch } = useProfile()
  const navigate = useNavigate()
  const role = data?.principal.type
  const shouldRedirect = Boolean(role && !allow.includes(role))

  useEffect(() => {
    if (shouldRedirect) {
      navigate({ to: '/app/dashboard', replace: true })
    }
  }, [shouldRedirect, navigate])

  if (isLoading) {
    return (
      <AuthCheckState
        compact
        title="Проверяем доступ"
        description="Проверяем, доступен ли этот раздел для вашей роли."
      />
    )
  }

  if (isError) {
    const err = error as Error & { status?: number }
    if (err.status === 401) {
      return (
        <AuthRequiredState
          compact
          title="Нужен вход"
          description="Сессия не активна. Авторизуйтесь, чтобы продолжить."
          actions={(
            <>
              <Link to="/app/login" className="ui-btn ui-btn--primary">Открыть вход</Link>
              <a href="/auth/login?redirect_to=/app" className="ui-btn ui-btn--ghost">Вход (прямой линк)</a>
            </>
          )}
        />
      )
    }

    return (
      <ErrorState
        compact
        title="Не удалось проверить доступ"
        description={`Не удалось проверить доступ: ${err.message}`}
        actions={(
          <button type="button" className="ui-btn ui-btn--primary" onClick={() => refetch()}>
            Повторить
          </button>
        )}
      />
    )
  }

  if (shouldRedirect) {
    return (
      <EmptyState
        compact
        title="Раздел недоступен"
        description="Раздел недоступен для текущей роли. Перенаправляем на рабочий экран."
        actions={(
          <Link to="/app/dashboard" className="ui-btn ui-btn--ghost">Вернуться на дашборд</Link>
        )}
      />
    )
  }

  return <>{children}</>
}
