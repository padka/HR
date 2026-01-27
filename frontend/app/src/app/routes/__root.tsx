import { Link, Outlet, useRouterState } from '@tanstack/react-router'
import { useProfile } from '@/app/hooks/useProfile'

const ICONS = {
  dashboard: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5 9.5V21h14V9.5" />
      <path d="M9.5 21v-6h5v6" />
    </svg>
  ),
  slots: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 3v3M17 3v3" />
      <rect x="4" y="5" width="16" height="16" rx="3" />
      <path d="M4 10h16" />
      <path d="M8 14h3M13 14h3M8 17h3" />
    </svg>
  ),
  candidates: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="8" r="3.5" />
      <path d="M4.5 20c1.8-3.8 5-5.5 7.5-5.5S17.2 16.2 19 20" />
    </svg>
  ),
  recruiters: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="8" cy="9" r="3" />
      <circle cx="16.5" cy="8" r="2.5" />
      <path d="M3.5 20c1.3-3.4 3.9-5 6.5-5s5.2 1.6 6.5 5" />
      <path d="M13.5 20c.7-2 2.1-3.1 4-3.1 1 0 1.9.3 2.6.9" />
    </svg>
  ),
  cities: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4" y="5" width="7" height="14" rx="2" />
      <rect x="13" y="8" width="7" height="11" rx="2" />
      <path d="M7 9h1M7 12h1M7 15h1M16 11h1M16 14h1M16 17h1" />
    </svg>
  ),
  templates: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 3h7l4 4v14H7z" />
      <path d="M14 3v5h5" />
      <path d="M9 12h6M9 15h6" />
    </svg>
  ),
  notifications: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 4c-3 0-5 2.2-5 5v3.2l-1.5 2.3h13L17 12.2V9c0-2.8-2-5-5-5z" />
      <path d="M9.5 18a2.5 2.5 0 0 0 5 0" />
    </svg>
  ),
  messenger: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 5h16v10H8l-4 4V5z" />
      <path d="M8 9h8M8 12h5" />
    </svg>
  ),
  questions: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 5h16v11H7l-3 3V5z" />
      <path d="M9.5 9.5a2.5 2.5 0 1 1 3.7 2.2c-.9.5-1.2.9-1.2 1.8" />
      <circle cx="12" cy="15.8" r="0.9" />
    </svg>
  ),
  system: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 2.8v2.4M12 18.8v2.4M4.8 12H2.4M21.6 12h-2.4M5.6 5.6l1.7 1.7M16.7 16.7l1.7 1.7M18.4 5.6l-1.7 1.7M7.3 16.7l-1.7 1.7" />
    </svg>
  ),
  profile: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="8" r="3.5" />
      <path d="M6 20c1.6-3.6 4.2-5.4 6-5.4s4.4 1.8 6 5.4" />
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
        <header className="app-header glass">
          <div className="app-header__left">
            <div className="app-brand">
              <span className="app-brand__mark">RS</span>
            </div>
            {profileQuery.isLoading && (
              <span className="app-header__status">Загрузка профиля…</span>
            )}
          </div>
          <nav className="app-nav" aria-label="Основная навигация">
            {navItems.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="app-nav__item"
                activeProps={{ className: 'app-nav__item is-active' }}
                data-tone={item.tone}
                aria-label={item.label}
                title={item.label}
              >
                <span className="app-nav__icon">{item.icon}</span>
              </Link>
            ))}
          </nav>
          <div className="app-header__right">
            <Link
              to="/app/profile"
              className="app-profile"
              aria-label="Профиль"
              title="Профиль"
            >
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
