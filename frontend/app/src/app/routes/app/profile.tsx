import { useEffect, useMemo, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'
import { ApiErrorBanner } from '@/app/components/ApiErrorBanner'
import { useProfile, type ProfileResponse } from '@/app/hooks/useProfile'

type AvatarUploadResponse = { ok: boolean; url?: string }
type AvatarDeleteResponse = { ok: boolean; removed?: boolean }

type TimezoneOption = {
  value: string
  label: string
  region: string
  offset: string
}

type KpiTrend = {
  direction?: 'up' | 'down' | 'flat'
  display?: string
  label?: string
  percent?: number | null
}

type KpiDetailRow = {
  candidate?: string
  recruiter?: string
  event_label?: string
  city?: string
}

type KpiMetric = {
  key: string
  label: string
  tone: string
  icon?: string
  value: number
  previous: number
  trend?: KpiTrend
  details?: KpiDetailRow[]
}

type KpiResponse = {
  timezone: string
  current: {
    label: string
    metrics: KpiMetric[]
  }
}

type ProfileSettingsPayload = {
  name: string
  tz: string
  telemost_url?: string | null
}

type ProfileSettingsResponse = {
  ok: boolean
  recruiter: {
    id: number
    name: string
    tz: string
    telemost_url?: string | null
    cities: { id: number; name: string }[]
  }
}

type ChangePasswordPayload = {
  current_password: string
  new_password: string
}

function CameraIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 19a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h2l2-2h4l2 2h2a2 2 0 0 1 2 2v10z" />
      <circle cx="12" cy="14" r="3" />
    </svg>
  )
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 6h18" />
      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6" />
      <path d="M14 11v6" />
    </svg>
  )
}

function formatMinutes(value?: number | null): string {
  if (typeof value !== 'number' || value <= 0) return '—'
  if (value < 60) return `${value} мин`
  const h = Math.floor(value / 60)
  const m = value % 60
  return m ? `${h} ч ${m} мин` : `${h} ч`
}

function formatHours(value?: number | null): string {
  if (typeof value !== 'number' || value <= 0) return '—'
  return `${value.toFixed(1)} ч`
}

function trendClass(direction?: string): string {
  if (direction === 'up') return 'is-up'
  if (direction === 'down') return 'is-down'
  return 'is-flat'
}

function mergeProfileRecruiter(
  previous: ProfileResponse | undefined,
  recruiter: ProfileSettingsResponse['recruiter'],
): ProfileResponse | undefined {
  if (!previous) return previous
  if (!previous.recruiter) return previous
  return {
    ...previous,
    recruiter: {
      ...previous.recruiter,
      name: recruiter.name,
      tz: recruiter.tz,
      telemost_url: recruiter.telemost_url || null,
      cities: recruiter.cities,
    },
  }
}

function formatDateShort(value: string): string {
  const [year, month, day] = value.split('-')
  if (!year || !month || !day) return value
  return `${day}.${month}.${year}`
}

export function ProfilePage() {
  const queryClient = useQueryClient()
  const { data, isLoading, isError, error, refetch, isFetching } = useProfile()
  const isAdmin = data?.principal.type === 'admin'
  const isRecruiter = data?.principal.type === 'recruiter'
  const recruiter = data?.recruiter
  const health = data?.profile?.admin_stats?.health || {}
  const hasAvatar = Boolean(data?.avatar_url)

  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    const stored = localStorage.getItem('theme')
    return stored === 'light' ? 'light' : 'dark'
  })

  const [settings, setSettings] = useState<ProfileSettingsPayload>({
    name: '',
    tz: 'Europe/Moscow',
    telemost_url: '',
  })
  const [passwordForm, setPasswordForm] = useState({
    current: '',
    next: '',
    confirm: '',
  })
  const [passwordError, setPasswordError] = useState<string | null>(null)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('theme', theme)
  }, [theme])

  useEffect(() => {
    if (!recruiter) return
    setSettings({
      name: recruiter.name || '',
      tz: recruiter.tz || 'Europe/Moscow',
      telemost_url: recruiter.telemost_url || '',
    })
  }, [recruiter])

  const timezoneQuery = useQuery({
    queryKey: ['timezones'],
    queryFn: () => apiFetch<TimezoneOption[]>('/timezones'),
    enabled: Boolean(isRecruiter),
    staleTime: 60_000,
  })

  const kpiQuery = useQuery({
    queryKey: ['profile-kpis'],
    queryFn: () => apiFetch<KpiResponse>('/kpis/current'),
    enabled: Boolean(isRecruiter),
    staleTime: 30_000,
  })

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

  const avatarDelete = useMutation({
    mutationFn: async () => {
      return apiFetch<AvatarDeleteResponse>('/profile/avatar', { method: 'DELETE' })
    },
    onSuccess: () => {
      refetch()
    },
  })

  const settingsMutation = useMutation({
    mutationFn: async (payload: ProfileSettingsPayload) => {
      return apiFetch<ProfileSettingsResponse>('/profile/settings', {
        method: 'PATCH',
        body: JSON.stringify(payload),
      })
    },
    onSuccess: (response) => {
      queryClient.setQueryData<ProfileResponse>(['profile'], (previous) =>
        mergeProfileRecruiter(previous, response.recruiter),
      )
      refetch()
    },
  })

  const passwordMutation = useMutation({
    mutationFn: async (payload: ChangePasswordPayload) => {
      return apiFetch<{ ok: boolean }>('/profile/change-password', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
    },
    onSuccess: () => {
      setPasswordForm({ current: '', next: '', confirm: '' })
      setPasswordError(null)
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

  const metrics = useMemo(() => {
    return kpiQuery.data?.current.metrics || []
  }, [kpiQuery.data])
  const maxMetricValue = useMemo(() => {
    return Math.max(1, ...metrics.map((m) => m.value || 0))
  }, [metrics])

  const detailsRows = useMemo(() => {
    const rows: Array<KpiDetailRow & { stage: string }> = []
    for (const metric of metrics) {
      const rowsForMetric = metric.details || []
      for (const row of rowsForMetric.slice(0, 3)) {
        rows.push({ ...row, stage: metric.label })
      }
    }
    return rows.slice(0, 12)
  }, [metrics])

  const plannerRows = useMemo(() => {
    const source = data?.profile?.planner_days || []
    return source.flatMap((day) =>
      day.entries.map((entry) => ({
        date: day.date,
        id: entry.id,
        time: entry.time || '—',
        status: entry.status || '—',
      })),
    )
  }, [data?.profile?.planner_days])

  const recruiterKpi = data?.profile?.kpi

  if (isLoading) {
    return (
      <div className="glass panel profile-card">
        <h1 className="title">Личный кабинет</h1>
        <p className="subtitle">Загрузка…</p>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="glass panel profile-card">
        <h1 className="title">Личный кабинет</h1>
        <ApiErrorBanner
          error={error}
          title="Ошибка загрузки профиля"
          onRetry={() => refetch()}
        />
      </div>
    )
  }

  return (
    <div className="page profile-page profile-cabinet">
      <section className="cabinet-glass cabinet-hero">
        <div className="cabinet-hero__main">
          <div className="profile-avatar">
            {data?.avatar_url ? (
              <img src={data.avatar_url} alt="Аватар" />
            ) : (
              <span className="profile-avatar__initials">{initials}</span>
            )}
            {hasAvatar ? (
              <button
                type="button"
                className="profile-avatar__delete"
                disabled={avatarUpload.isPending || avatarDelete.isPending}
                title="Удалить фото"
                aria-label="Удалить фото профиля"
                onClick={() => {
                  if (!confirm('Удалить фотографию профиля?')) return
                  avatarDelete.mutate()
                }}
              >
                <TrashIcon />
              </button>
            ) : null}
            <label
              className={`profile-avatar__upload ${avatarUpload.isPending ? 'is-pending' : ''}`}
              title={avatarUpload.isPending ? 'Загрузка…' : hasAvatar ? 'Заменить фото' : 'Загрузить фото'}
              aria-label={hasAvatar ? 'Заменить фото профиля' : 'Загрузить фото профиля'}
            >
              <input
                type="file"
                accept="image/*"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  e.target.value = ''
                  if (file) avatarUpload.mutate(file)
                }}
              />
              <CameraIcon />
              {hasAvatar ? null : (
                <span>{avatarUpload.isPending ? 'Загрузка…' : 'Загрузить'}</span>
              )}
            </label>
          </div>

          <div className="cabinet-identity">
            <h1 className="title title--lg">{displayName}</h1>
            <p className="subtitle">
              {data?.principal.type === 'admin' ? 'Администратор' : 'Рекрутер'}
              {' · '}
              ID {data?.principal.id}
              {isFetching ? ' · обновление…' : ''}
            </p>
            {recruiter?.cities?.length ? (
              <div className="profile-chips">
                {recruiter.cities.map((city) => (
                  <span key={city.id} className="chip chip--accent">{city.name}</span>
                ))}
              </div>
            ) : null}
          </div>
        </div>

        <div className="cabinet-hero__stats">
          <article className="cabinet-kpi-card">
            <span className="cabinet-kpi-card__label">Сегодня встреч</span>
            <strong className="cabinet-kpi-card__value">{recruiterKpi?.today ?? 0}</strong>
          </article>
          <article className="cabinet-kpi-card">
            <span className="cabinet-kpi-card__label">Впереди</span>
            <strong className="cabinet-kpi-card__value">{recruiterKpi?.upcoming ?? 0}</strong>
          </article>
          <article className="cabinet-kpi-card">
            <span className="cabinet-kpi-card__label">Ожидают подтверждения</span>
            <strong className="cabinet-kpi-card__value">{recruiterKpi?.pending ?? 0}</strong>
          </article>
          <article className="cabinet-kpi-card">
            <span className="cabinet-kpi-card__label">Конверсия</span>
            <strong className="cabinet-kpi-card__value">{recruiterKpi?.conversion ?? 0}%</strong>
          </article>
          <article className="cabinet-kpi-card">
            <span className="cabinet-kpi-card__label">Ближайший слот</span>
            <strong className="cabinet-kpi-card__value">{formatMinutes(recruiterKpi?.nearest_minutes)}</strong>
          </article>
          <article className="cabinet-kpi-card">
            <span className="cabinet-kpi-card__label">Среднее lead time</span>
            <strong className="cabinet-kpi-card__value">{formatHours(recruiterKpi?.avg_lead_hours)}</strong>
          </article>
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
          <ApiErrorBanner error={avatarUpload.error} title="Не удалось загрузить аватар" />
        )}
        {avatarDelete.isError && (
          <ApiErrorBanner error={avatarDelete.error} title="Не удалось удалить аватар" />
        )}
      </section>

      {isRecruiter && (
        <>
          <div className="cabinet-grid">
            <section className="cabinet-glass cabinet-panel">
              <div className="cabinet-panel__header">
                <h2 className="title title--sm">Настройки профиля рекрутера</h2>
                <p className="subtitle">Изменения применяются сразу для личного кабинета и рабочих форм.</p>
              </div>
              <form
                className="cabinet-form"
                onSubmit={(event) => {
                  event.preventDefault()
                  settingsMutation.mutate(settings)
                }}
              >
                <label className="field">
                  <span>Имя</span>
                  <input
                    value={settings.name}
                    maxLength={100}
                    onChange={(e) => setSettings((prev) => ({ ...prev, name: e.target.value }))}
                    placeholder="Введите имя"
                    required
                  />
                </label>

                <label className="field">
                  <span>Часовой пояс</span>
                  <select
                    value={settings.tz}
                    onChange={(e) => setSettings((prev) => ({ ...prev, tz: e.target.value }))}
                  >
                    {(timezoneQuery.data || []).map((timezone) => (
                      <option key={timezone.value} value={timezone.value}>
                        {timezone.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="field">
                  <span>Ссылка на конференцию</span>
                  <input
                    value={settings.telemost_url || ''}
                    onChange={(e) => setSettings((prev) => ({ ...prev, telemost_url: e.target.value }))}
                    placeholder="https://telemost.yandex.ru/..."
                  />
                </label>

                <label className="field field--readonly">
                  <span>Telegram chat ID</span>
                  <input value={String(recruiter?.tg_chat_id || '—')} disabled />
                </label>

                <div className="cabinet-form__actions">
                  <button type="submit" className="ui-btn ui-btn--primary" disabled={settingsMutation.isPending}>
                    {settingsMutation.isPending ? 'Сохранение…' : 'Сохранить настройки'}
                  </button>
                </div>
              </form>
              {settingsMutation.isError && (
                <ApiErrorBanner error={settingsMutation.error} title="Не удалось сохранить настройки" />
              )}
              {settingsMutation.isSuccess && (
                <p className="cabinet-success">Настройки профиля обновлены.</p>
              )}
            </section>

            <section className="cabinet-glass cabinet-panel">
              <div className="cabinet-panel__header">
                <h2 className="title title--sm">Безопасность аккаунта</h2>
                <p className="subtitle">Для смены пароля нужен текущий пароль от вашей учётной записи.</p>
              </div>
              <form
                className="cabinet-form"
                onSubmit={(event) => {
                  event.preventDefault()
                  if (passwordForm.next !== passwordForm.confirm) {
                    setPasswordError('Новый пароль и подтверждение не совпадают.')
                    return
                  }
                  setPasswordError(null)
                  passwordMutation.mutate({
                    current_password: passwordForm.current,
                    new_password: passwordForm.next,
                  })
                }}
              >
                <label className="field">
                  <span>Текущий пароль</span>
                  <input
                    type="password"
                    value={passwordForm.current}
                    onChange={(e) => setPasswordForm((prev) => ({ ...prev, current: e.target.value }))}
                    required
                  />
                </label>
                <label className="field">
                  <span>Новый пароль</span>
                  <input
                    type="password"
                    value={passwordForm.next}
                    onChange={(e) => setPasswordForm((prev) => ({ ...prev, next: e.target.value }))}
                    required
                    minLength={8}
                  />
                </label>
                <label className="field">
                  <span>Подтверждение</span>
                  <input
                    type="password"
                    value={passwordForm.confirm}
                    onChange={(e) => setPasswordForm((prev) => ({ ...prev, confirm: e.target.value }))}
                    required
                    minLength={8}
                  />
                </label>
                <div className="cabinet-form__actions">
                  <button type="submit" className="ui-btn ui-btn--primary" disabled={passwordMutation.isPending}>
                    {passwordMutation.isPending ? 'Обновление…' : 'Сменить пароль'}
                  </button>
                </div>
              </form>
              {passwordError && <p className="text-danger text-sm">{passwordError}</p>}
              {passwordMutation.isError && (
                <ApiErrorBanner error={passwordMutation.error} title="Не удалось сменить пароль" />
              )}
              {passwordMutation.isSuccess && (
                <p className="cabinet-success">Пароль успешно обновлён.</p>
              )}
            </section>
          </div>

          <section className="cabinet-glass cabinet-panel">
            <div className="cabinet-panel__header">
              <h2 className="title title--sm">Личный дашборд: визуализация</h2>
              <p className="subtitle">
                {kpiQuery.data?.current?.label || 'Текущая неделя'}
                {kpiQuery.data?.timezone ? ` · ${kpiQuery.data.timezone}` : ''}
              </p>
            </div>
            {kpiQuery.isLoading && <p className="subtitle">Загрузка KPI…</p>}
            {kpiQuery.isError && (
              <ApiErrorBanner error={kpiQuery.error} title="Не удалось загрузить персональные KPI" />
            )}
            {!kpiQuery.isLoading && !metrics.length && (
              <p className="subtitle">Нет данных для построения графика.</p>
            )}
            {!!metrics.length && (
              <div className="cabinet-funnel">
                {metrics.map((metric) => {
                  const width = Math.max(4, Math.round((metric.value / maxMetricValue) * 100))
                  return (
                    <div className="cabinet-funnel__row" key={metric.key}>
                      <div className="cabinet-funnel__label">
                        <span>{metric.icon || '•'}</span>
                        <span>{metric.label}</span>
                      </div>
                      <div className="cabinet-funnel__track" aria-hidden="true">
                        <div className={`cabinet-funnel__bar ${trendClass(metric.trend?.direction)}`} style={{ width: `${width}%` }} />
                      </div>
                      <div className="cabinet-funnel__value">{metric.value}</div>
                    </div>
                  )
                })}
              </div>
            )}
          </section>

          <section className="cabinet-glass cabinet-panel">
            <div className="cabinet-panel__header">
              <h2 className="title title--sm">Личный дашборд: табличное представление</h2>
              <p className="subtitle">Текущая vs прошлая неделя по ключевым этапам воронки.</p>
            </div>
            <div className="table-wrap">
              <table className="data-table cabinet-table">
                <thead>
                  <tr>
                    <th>Этап</th>
                    <th>Текущая неделя</th>
                    <th>Прошлая неделя</th>
                    <th>Тренд</th>
                  </tr>
                </thead>
                <tbody>
                  {!metrics.length && (
                    <tr>
                      <td colSpan={4}>Нет данных</td>
                    </tr>
                  )}
                  {metrics.map((metric) => (
                    <tr key={metric.key}>
                      <td>
                        <span className="cabinet-stage">
                          <span>{metric.icon || '•'}</span>
                          <span>{metric.label}</span>
                        </span>
                      </td>
                      <td>{metric.value}</td>
                      <td>{metric.previous}</td>
                      <td>
                        <span className={`cabinet-trend ${trendClass(metric.trend?.direction)}`}>
                          {metric.trend?.display || '—'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="cabinet-glass cabinet-panel">
            <div className="cabinet-panel__header">
              <h2 className="title title--sm">Лента персональных событий</h2>
              <p className="subtitle">Последние события по ключевым этапам (кандидаты, интервью, intro day).</p>
            </div>
            <div className="table-wrap">
              <table className="data-table cabinet-table">
                <thead>
                  <tr>
                    <th>Этап</th>
                    <th>Кандидат</th>
                    <th>Рекрутёр</th>
                    <th>Событие</th>
                    <th>Город</th>
                  </tr>
                </thead>
                <tbody>
                  {!detailsRows.length && (
                    <tr>
                      <td colSpan={5}>Нет событий за выбранный период</td>
                    </tr>
                  )}
                  {detailsRows.map((row, index) => (
                    <tr key={`${row.stage}-${row.candidate || 'candidate'}-${index}`}>
                      <td>{row.stage}</td>
                      <td>{row.candidate || '—'}</td>
                      <td>{row.recruiter || '—'}</td>
                      <td>{row.event_label || '—'}</td>
                      <td>{row.city || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="cabinet-glass cabinet-panel">
            <div className="cabinet-panel__header">
              <h2 className="title title--sm">Планировщик встреч (7 дней)</h2>
              <p className="subtitle">Операционная таблица для ежедневной работы рекрутера.</p>
            </div>
            <div className="table-wrap">
              <table className="data-table cabinet-table">
                <thead>
                  <tr>
                    <th>Дата</th>
                    <th>Время</th>
                    <th>Статус</th>
                    <th>ID слота</th>
                  </tr>
                </thead>
                <tbody>
                  {!plannerRows.length && (
                    <tr>
                      <td colSpan={4}>На ближайшие 7 дней слотов нет</td>
                    </tr>
                  )}
                  {plannerRows.map((row) => (
                    <tr key={`${row.date}-${row.id}`}>
                      <td>{formatDateShort(row.date)}</td>
                      <td>{row.time}</td>
                      <td>{row.status}</td>
                      <td>{row.id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {isAdmin && (
        <section className="cabinet-glass cabinet-panel">
          <div className="cabinet-panel__header">
            <h2 className="title title--sm">Профиль администратора</h2>
            <p className="subtitle">Системные метрики и быстрые переходы.</p>
          </div>
          <div className="health-grid">
            <HealthItem label="DB" value={health.db} />
            <HealthItem label="Redis" value={health.redis} />
            <HealthItem label="Cache" value={health.cache} />
            <HealthItem label="Bot" value={health.bot} />
            <HealthItem label="Notifications" value={health.notifications} />
          </div>
          <div className="quick-actions">
            <Link to="/app/recruiters" className="glass action-link">Рекрутеры</Link>
            <Link to="/app/cities" className="glass action-link">Города</Link>
            <Link to="/app/templates" className="glass action-link">Шаблоны</Link>
            <Link to="/app/message-templates" className="glass action-link">Сообщения</Link>
            <Link to="/app/questions" className="glass action-link">Вопросы</Link>
            <Link to="/app/messenger" className="glass action-link">Чаты</Link>
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
