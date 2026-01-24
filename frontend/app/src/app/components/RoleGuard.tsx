import { ReactNode } from 'react'
import { Link } from '@tanstack/react-router'
import { useProfile } from '@/app/hooks/useProfile'

type RoleGuardProps = {
  allow: Array<'admin' | 'recruiter'>
  children: ReactNode
}

export function RoleGuard({ allow, children }: RoleGuardProps) {
  const { data, isLoading, isError, error, refetch } = useProfile()

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
  if (role && !allow.includes(role)) {
    return (
      <div className="glass panel empty-state">
        <h2 className="title">Недоступно</h2>
        <p className="subtitle">Этот раздел доступен только для роли: {allow.join(', ')}.</p>
        <div className="action-row" style={{ justifyContent: 'center' }}>
          <Link to="/app/profile" className="glass action-link">Перейти в профиль</Link>
          <Link to="/app" className="glass action-link">На главную</Link>
        </div>
      </div>
    )
  }

  return <>{children}</>
}
