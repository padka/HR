import { Link, Outlet, useRouterState } from '@tanstack/react-router'
import { useProfile } from '@/app/hooks/useProfile'

const ICONS = {
  dashboard: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
    </svg>
  ),
  slots: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M16 2v4M8 2v4M3 10h18" />
    </svg>
  ),
  candidates: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="8.5" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  recruiters: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  ),
  cities: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  ),
  messenger: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  ),
  profile: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />
      <path d="M7 20.662V19a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v1.662" />
    </svg>
  ),
}

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
          { to: '/app/dashboard', label: 'Дашборд', icon: ICONS.dashboard, tone: 'blue' },
          { to: '/app/slots', label: 'Слоты', icon: ICONS.slots, tone: 'violet' },
          { to: '/app/candidates', label: 'Кандидаты', icon: ICONS.candidates, tone: 'sky' },
          { to: '/app/messenger', label: 'Чаты', icon: ICONS.messenger, tone: 'aqua' },
        ]
      : principalType === 'admin'
        ? [
            { to: '/app/dashboard', label: 'Дашборд', icon: ICONS.dashboard, tone: 'blue' },
            { to: '/app/recruiters', label: 'Рекрутёры', icon: ICONS.recruiters, tone: 'indigo' },
            { to: '/app/cities', label: 'Города', icon: ICONS.cities, tone: 'sunset' },
            { to: '/app/messenger', label: 'Чаты', icon: ICONS.messenger, tone: 'aqua' },
          ]
        : []

  return (
    <div className="app-shell">
      <div className="background-scene">
        <div className="bubbles-layer layer-1">
          <span className="bubble"></span>
          <span className="bubble"></span>
          <span className="bubble"></span>
        </div>
        <div className="bubbles-layer layer-2">
          <span className="bubble"></span>
          <span className="bubble"></span>
          <span className="bubble"></span>
          <span className="bubble"></span>
        </div>
        <div className="bubbles-layer layer-3">
          <span className="bubble"></span>
          <span className="bubble"></span>
        </div>
      </div>
      {!hideNav && (
        <header className="app-header">
          <div className="app-header-left" />
          
          <nav className="vision-nav-pill" aria-label="Основная навигация">
            {navItems.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="vision-nav__item"
                activeProps={{ className: 'vision-nav__item is-active' }}
                data-tone={item.tone}
                title={item.label}
              >
                <span className="vision-nav__icon">{item.icon}</span>
                <span className="vision-nav__label">{item.label}</span>
              </Link>
            ))}
          </nav>

          <div className="app-header-right">
            <Link to="/app/profile" className="app-profile-pill glass" title="Профиль">
              <span className="app-profile__icon">{ICONS.profile}</span>
            </Link>
          </div>
        </header>
      )}
      <main>
        <Outlet />
      </main>
    </div>
  )
}
