import { Link, Outlet, useRouterState } from '@tanstack/react-router'
import { useProfile } from '@/app/hooks/useProfile'

export function RootLayout() {
  const { location } = useRouterState()
  const hideNav = location.pathname.startsWith('/app/login')
  const profileQuery = useProfile(!hideNav)
  const principalType = profileQuery.data?.principal.type
  const authError = profileQuery.error as (Error & { status?: number }) | undefined
  const isUnauthed = authError?.status === 401

  if (isUnauthed && !hideNav) {
    return (
      <div style={{ minHeight: '100vh', padding: '24px', display: 'grid', gap: '16px' }}>
        <main>
          <div className="glass" style={{ padding: 24 }}>
            <h1 style={{ marginTop: 0 }}>Требуется вход</h1>
            <p style={{ color: 'var(--muted)' }}>
              Сессия не активна. Перейдите на страницу авторизации, чтобы продолжить работу.
            </p>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <Link to="/app/login" style={{ textDecoration: 'underline', color: 'var(--fg)' }}>
                Открыть вход
              </Link>
              <a href="/auth/login?redirect_to=/app" style={{ textDecoration: 'underline', color: 'var(--fg)' }}>
                Вход (прямой линк)
              </a>
            </div>
          </div>
        </main>
      </div>
    )
  }

  const navItems =
    principalType === 'recruiter'
      ? [
          { to: '/app/dashboard', label: 'Дашборд' },
          { to: '/app/slots', label: 'Слоты' },
          { to: '/app/slots/create', label: 'Создать слот' },
          { to: '/app/candidates', label: 'Кандидаты' },
          { to: '/app/cities', label: 'Города' },
          { to: '/app/profile', label: 'Профиль' },
        ]
      : principalType === 'admin'
        ? [
            { to: '/app/dashboard', label: 'Дашборд' },
            { to: '/app/candidates', label: 'Кандидаты' },
            { to: '/app/recruiters', label: 'Рекрутёры' },
            { to: '/app/cities', label: 'Города' },
            { to: '/app/templates', label: 'Шаблоны' },
            { to: '/app/message-templates', label: 'Уведомления' },
            { to: '/app/questions', label: 'Вопросы' },
            { to: '/app/system', label: 'Система' },
            { to: '/app/profile', label: 'Профиль' },
          ]
        : []

  return (
    <div style={{ minHeight: '100vh', padding: '24px', display: 'grid', gap: '16px' }}>
      {!hideNav && (
        <header className="glass" style={{ padding: '12px 16px', display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 700 }}>RecruitSmart · React SPA (WIP)</span>
          {profileQuery.isLoading && (
            <span style={{ color: 'var(--muted)', fontSize: 12 }}>Загрузка профиля…</span>
          )}
          <nav style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            {navItems.map((item) => (
              <Link key={item.to} to={item.to} activeProps={{ style: { fontWeight: 700 } }}>
                {item.label}
              </Link>
            ))}
          </nav>
        </header>
      )}
      <main>
        <Outlet />
      </main>
    </div>
  )
}
