import { useEffect, useMemo, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { useMutation } from '@tanstack/react-query'
import { useProfile } from '@/app/hooks/useProfile'
import { apiFetch } from '@/api/client'

type AvatarUploadResponse = { ok: boolean; url?: string }

export function ProfilePage() {
  const { data, isLoading, isError, error, refetch, isFetching } = useProfile()
  const isAdmin = data?.principal.type === 'admin'
  const recruiter = data?.recruiter
  const health = data?.profile?.admin_stats?.health || {}

  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    const stored = localStorage.getItem('theme')
    return stored === 'light' ? 'light' : 'dark'
  })

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('theme', theme)
  }, [theme])

  const avatarUpload = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return apiFetch<AvatarUploadResponse>('/profile/avatar', { method: 'POST', body: form })
    },
    onSuccess: () => {
      refetch()
    },
  })

  const displayName = useMemo(() => {
    if (recruiter?.name) return recruiter.name
    if (data?.principal.type === 'admin') return 'Администратор'
    return 'Пользователь'
  }, [recruiter?.name, data?.principal.type])

  const initials = useMemo(() => {
    const parts = (displayName || '').split(' ').filter(Boolean)
    if (!parts.length) return 'RS'
    return parts.slice(0, 2).map((p) => p[0]?.toUpperCase()).join('')
  }, [displayName])

  if (isLoading) {
    return (
      <div className="glass panel profile-card">
        <h1 className="title">Профиль</h1>
        <p className="subtitle">Загрузка…</p>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="glass panel profile-card">
        <h1 className="title">Профиль</h1>
        <p className="subtitle">Ошибка загрузки: {(error as Error).message}</p>
        <button className="ui-btn ui-btn--ghost" onClick={() => refetch()}>Повторить</button>
      </div>
    )
  }

  return (
    <div className="page profile-page profile-min">
      <section className="glass panel profile-card">
        <div className="profile-card__main">
          <div className="profile-avatar">
            {data?.avatar_url ? (
              <img src={data.avatar_url} alt="Аватар" />
            ) : (
              <span>{initials}</span>
            )}
            <label className="profile-avatar__upload">
              <input
                type="file"
                accept="image/*"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) avatarUpload.mutate(file)
                }}
              />
              <span>{avatarUpload.isPending ? 'Загрузка…' : 'Загрузить'}</span>
            </label>
          </div>

          <div className="profile-info">
            <h1 className="title title--lg">{displayName}</h1>
            <p className="subtitle">
              {data?.principal.type === 'admin' ? 'Администратор' : 'Рекрутер'} · ID {data?.principal.id}
              {isFetching ? ' · обновление…' : ''}
            </p>
            {recruiter?.tz && <div className="text-muted text-sm">TZ: {recruiter.tz}</div>}
            {recruiter?.cities?.length ? (
              <div className="profile-chips">
                {recruiter.cities.map((city) => (
                  <span key={city.id} className="chip chip--accent">{city.name}</span>
                ))}
              </div>
            ) : null}
          </div>
        </div>

        <div className="profile-card__actions">
          <div className="theme-toggle">
            <button
              type="button"
              className={`ui-btn ui-btn--ghost ${theme === 'dark' ? 'is-active' : ''}`}
              onClick={() => setTheme('dark')}
            >
              Тёмная
            </button>
            <button
              type="button"
              className={`ui-btn ui-btn--ghost ${theme === 'light' ? 'is-active' : ''}`}
              onClick={() => setTheme('light')}
            >
              Светлая
            </button>
          </div>
          <form method="post" action="/auth/logout">
            <button type="submit" className="ui-btn ui-btn--primary">Выйти</button>
          </form>
        </div>

        {avatarUpload.isError && (
          <p className="text-danger text-sm">Не удалось загрузить аватар</p>
        )}
      </section>

      {isAdmin && (
        <section className="glass panel profile-admin">
          <div className="profile-admin__block">
            <h2 className="title title--sm">Состояние системы</h2>
            <div className="health-grid">
              <HealthItem label="DB" value={health.db} />
              <HealthItem label="Redis" value={health.redis} />
              <HealthItem label="Cache" value={health.cache} />
              <HealthItem label="Bot" value={health.bot} />
              <HealthItem label="Notifications" value={health.notifications} />
            </div>
          </div>

          <div className="profile-admin__block">
            <h2 className="title title--sm">Быстрые действия</h2>
            <div className="quick-actions">
              <Link to="/app/recruiters" className="glass action-link">Рекрутеры</Link>
              <Link to="/app/cities" className="glass action-link">Города</Link>
              <Link to="/app/templates" className="glass action-link">Шаблоны</Link>
              <Link to="/app/message-templates" className="glass action-link">Сообщения</Link>
              <Link to="/app/questions" className="glass action-link">Вопросы</Link>
              <Link to="/app/messenger" className="glass action-link">Чаты</Link>
            </div>
          </div>
        </section>
      )}
    </div>
  )
}

function HealthItem({ label, value }: { label: string; value: string | boolean | null | undefined }) {
  const normalized = typeof value === 'boolean' ? (value ? 'OK' : 'OFF') : value ?? '—'
  const tone = value === false ? 'danger' : 'success'
  return (
    <div className={`health-item health-item--${tone}`}>
      <span>{label}</span>
      <strong>{String(normalized)}</strong>
    </div>
  )
}
