import { ReactNode, useEffect } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { useProfile } from '@/app/hooks/useProfile'

type RoleGuardProps = {
  allow: Array<'admin' | 'recruiter'>
  children: ReactNode
}

export function RoleGuard({ allow, children }: RoleGuardProps) {
  const { data, isLoading, isError, error, refetch } = useProfile()
  const navigate = useNavigate()

  if (isLoading) {
    return (
      <div className="glass panel empty-state">
        <h2 className="title">Загрузка…</h2>
        <p className="subtitle">Проверяем доступ к разделу.</p>
      </div>
    )
  }

  if (isError) {
    const err = error as Error & { status?: number }
    if (err.status === 401) {
      return (
        <div className="glass panel empty-state">
          <h2 className="title">Нужен вход</h2>
          <p className="subtitle">Сессия не активна. Авторизуйтесь, чтобы продолжить.</p>
          <div className="action-row" style={{ justifyContent: 'center' }}>
            <Link to="/app/login" className="glass action-link">Открыть вход</Link>
            <a href="/auth/login?redirect_to=/app" className="glass action-link">Вход (прямой линк)</a>
          </div>
        </div>
      )
    }

    return (
      <div className="glass panel empty-state">
        <h2 className="title">Ошибка</h2>
        <p className="subtitle">Не удалось проверить доступ: {err.message}</p>
        <button className="ui-btn ui-btn--ghost" onClick={() => refetch()} style={{ marginTop: 12 }}>Повторить</button>
      </div>
    )
  }

  const role = data?.principal.type
  const shouldRedirect = Boolean(role && !allow.includes(role))

  useEffect(() => {
    if (shouldRedirect) {
      navigate({ to: '/app/dashboard', replace: true })
    }
  }, [shouldRedirect, navigate])

  if (shouldRedirect) {
    return (
      <div className="glass panel empty-state">
        <h2 className="title">Перенаправляем…</h2>
        <p className="subtitle">Раздел недоступен для текущей роли.</p>
        <div className="action-row" style={{ justifyContent: 'center' }}>
          <Link to="/app/dashboard" className="glass action-link">Вернуться на дашборд</Link>
        </div>
      </div>
    )
  }

  return <>{children}</>
}
