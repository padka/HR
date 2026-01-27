import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'
import { getTzPreview, validateRecruiterForm } from './recruiter-form'

type City = { id: number; name: string; tz?: string | null }
type TimezoneOption = { value: string; label: string; region?: string; offset?: string }
type RecruiterDetail = {
  id: number
  name: string
  tz?: string | null
  tg_chat_id?: number | null
  telemost_url?: string | null
  active?: boolean | null
  city_ids?: number[]
}
type RecruiterSummary = {
  id: number
  name: string
  tz?: string | null
  tg_chat_id?: string | null
  telemost_url?: string | null
  active?: boolean | null
  last_seen_at?: string | null
  is_online?: boolean | null
  city_ids?: number[]
  stats?: { total: number; free: number; pending: number; booked: number }
  next_free_local?: string | null
  next_is_future?: boolean
}

export function RecruiterEditPage() {
  const params = useParams({ from: '/app/recruiters/$recruiterId/edit' })
  const recruiterId = Number(params.recruiterId)
  const navigate = useNavigate()

  const { data: cities } = useQuery<City[]>({
    queryKey: ['cities'],
    queryFn: () => apiFetch('/cities'),
  })
  const { data: timezones } = useQuery<TimezoneOption[]>({
    queryKey: ['timezones'],
    queryFn: () => apiFetch('/timezones'),
  })

  const detailQuery = useQuery<RecruiterDetail>({
    queryKey: ['recruiter-detail', recruiterId],
    queryFn: () => apiFetch(`/recruiters/${recruiterId}`),
  })
  const recruitersQuery = useQuery<RecruiterSummary[]>({
    queryKey: ['recruiters'],
    queryFn: () => apiFetch('/recruiters'),
  })

  const [form, setForm] = useState({
    name: '',
    tz: 'Europe/Moscow',
    tg_chat_id: '',
    telemost_url: '',
    active: true,
    city_ids: [] as number[],
  })
  const [citySearch, setCitySearch] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<{ name?: string; tz?: string; tg_chat_id?: string; telemost_url?: string }>({})
  const initialForm = useRef(form)

  useEffect(() => {
    if (!detailQuery.data) return
    const nextForm = {
      name: detailQuery.data.name || '',
      tz: detailQuery.data.tz || 'Europe/Moscow',
      tg_chat_id: detailQuery.data.tg_chat_id ? String(detailQuery.data.tg_chat_id) : '',
      telemost_url: detailQuery.data.telemost_url || '',
      active: Boolean(detailQuery.data.active),
      city_ids: detailQuery.data.city_ids || [],
    }
    initialForm.current = nextForm
    setForm(nextForm)
  }, [detailQuery.data])

  const mutation = useMutation({
    mutationFn: async () => {
      setFormError(null)
      setFieldError({})
      const validation = validateRecruiterForm(form)
      if (!validation.valid) {
        setFieldError(validation.errors)
        throw new Error('invalid_form')
      }
      const payload = {
        name: form.name,
        tz: form.tz,
        tg_chat_id: form.tg_chat_id ? Number(form.tg_chat_id) : null,
        telemost_url: form.telemost_url || null,
        active: form.active,
        city_ids: form.city_ids,
      }
      return apiFetch(`/recruiters/${recruiterId}`, { method: 'PUT', body: JSON.stringify(payload) })
    },
    onSuccess: () => navigate({ to: '/app/recruiters' }),
    onError: (err) => {
      if (err instanceof Error && err.message === 'invalid_form') return
      let message = err instanceof Error ? err.message : 'Ошибка'
      try {
        const parsed = JSON.parse(message)
        if (parsed?.error?.message) {
          message = parsed.error.message
          if (parsed.error.field) {
            setFieldError({ [parsed.error.field]: message })
          }
        } else if (parsed?.error) {
          message = parsed.error
        }
      } catch {
        // ignore parsing errors
      }
      setFormError(message)
    },
  })
  const isSaving = mutation.isPending

  const deleteMutation = useMutation({
    mutationFn: async () => {
      return apiFetch(`/recruiters/${recruiterId}`, { method: 'DELETE' })
    },
    onSuccess: () => navigate({ to: '/app/recruiters' }),
  })

  const cityList = useMemo(() => cities || [], [cities])

  const filteredCities = useMemo(() => {
    const term = citySearch.toLowerCase().trim()
    if (!term) return cityList
    return cityList.filter(c =>
      c.name.toLowerCase().includes(term) ||
      (c.tz && c.tz.toLowerCase().includes(term))
    )
  }, [cityList, citySearch])

  const toggleCity = (id: number) => {
    setForm(prev => ({
      ...prev,
      city_ids: prev.city_ids.includes(id)
        ? prev.city_ids.filter(x => x !== id)
        : [...prev.city_ids, id]
    }))
  }

  const tzOptions = useMemo(() => {
    const opts = timezones || []
    if (form.tz && !opts.find((o) => o.value === form.tz)) {
      return [...opts, { value: form.tz, label: form.tz }]
    }
    return opts
  }, [timezones, form.tz])

  const selectedCount = form.city_ids.length
  const counterText = selectedCount === 0 ? 'Нет выбранных' : selectedCount === 1 ? '1 выбран' : `${selectedCount} выбрано`

  // Get initials for avatar
  const initials = useMemo(() => {
    const parts = (form.name || '').trim().split(/\s+/)
    if (!parts[0]) return 'R'
    const first = parts[0][0] || ''
    const second = parts[1]?.[0] || ''
    return (first + second).toUpperCase() || 'R'
  }, [form.name])

  // Get selected cities for pills preview
  const selectedCities = useMemo(() => {
    return cityList.filter(c => form.city_ids.includes(c.id))
  }, [cityList, form.city_ids])
  const tzPreview = useMemo(() => getTzPreview(form.tz), [form.tz])

  const summary = useMemo(() => {
    return recruitersQuery.data?.find((rec) => rec.id === recruiterId)
  }, [recruitersQuery.data, recruiterId])
  const stats = summary?.stats || { total: 0, free: 0, pending: 0, booked: 0 }
  const loadPercent = stats.total ? Math.round((stats.booked / stats.total) * 100) : 0
  const presenceLabel = summary?.active
    ? summary?.is_online
      ? 'Онлайн'
      : 'Вне сети'
    : 'Отключен'
  const presenceClass = summary?.active
    ? summary?.is_online
      ? 'is-online'
      : 'is-away'
    : 'is-inactive'
  const lastSeen = summary?.last_seen_at
    ? new Date(summary.last_seen_at).toLocaleString('ru-RU')
    : '—'
  const isDirty = useMemo(() => {
    const base = initialForm.current
    return (
      base.name !== form.name ||
      base.tz !== form.tz ||
      base.tg_chat_id !== form.tg_chat_id ||
      base.telemost_url !== form.telemost_url ||
      base.active !== form.active ||
      base.city_ids.join(',') !== form.city_ids.join(',')
    )
  }, [form])

  return (
    <RoleGuard allow={['admin']}>
      <div className="page recruiter-edit">
        <div className="glass panel recruiter-edit__panel">
          <div className="recruiter-edit__header">
            <div>
              <Link to="/app/recruiters" className="glass action-link">← К списку рекрутёров</Link>
              <h1 className="title">Профиль рекрутёра</h1>
              <p className="subtitle">Настройте профиль, связи с городами и доступы.</p>
            </div>
            <div className="recruiter-edit__header-actions">
              {isDirty && <span className="badge badge--soft">Есть несохранённые изменения</span>}
              <button className="ui-btn ui-btn--primary" onClick={() => mutation.mutate()} disabled={isSaving}>
                {isSaving ? 'Сохраняем…' : 'Сохранить'}
              </button>
            </div>
          </div>

          {detailQuery.isLoading && <p className="subtitle">Загрузка…</p>}
          {detailQuery.isError && <p style={{ color: '#f07373' }}>Ошибка: {(detailQuery.error as Error).message}</p>}

          {!detailQuery.isLoading && (
            <>
              <div className="glass recruiter-edit__hero">
                <div className="recruiter-edit__hero-main">
                  <div className={`recruiter-avatar ${presenceClass}`} aria-hidden="true">
                    {initials}
                  </div>
                  <div>
                    <p className="subtitle">Редактирование рекрутёра</p>
                    <h2 className="recruiter-edit__name">{form.name || 'Без имени'}</h2>
                    <div className="recruiter-edit__meta">
                      <span className="chip">ID #{recruiterId}</span>
                      <span className="chip">{form.tz}</span>
                      <span className="chip">{presenceLabel}</span>
                    </div>
                  </div>
                </div>
                <div className="recruiter-edit__hero-stats">
                  <div className="recruiter-edit__stat">
                    <span>Города</span>
                    <strong>{selectedCount}</strong>
                  </div>
                  <div className="recruiter-edit__stat">
                    <span>Telegram</span>
                    <strong>{form.tg_chat_id ? 'Подключен' : '—'}</strong>
                  </div>
                  <div className="recruiter-edit__stat">
                    <span>Занятость</span>
                    <strong>{loadPercent}%</strong>
                  </div>
                  <div className="recruiter-edit__stat">
                    <span>Последний вход</span>
                    <strong>{lastSeen}</strong>
                  </div>
                </div>
              </div>

              <div className="recruiter-edit__grid">
                <div className="recruiter-edit__main">
                  <div className="glass recruiter-edit__section">
                    <div className="recruiter-edit__section-header">
                      <div>
                        <h3>Основные данные</h3>
                        <p className="subtitle">Имя и рабочий регион для расчёта локального времени.</p>
                      </div>
                      <label className="recruiter-edit__toggle">
                    <input
                      type="checkbox"
                      checked={form.active}
                      disabled={isSaving}
                      onChange={(e) => setForm({ ...form, active: e.target.checked })}
                    />
                    <span>{form.active ? 'Активен' : 'Отключен'}</span>
                      </label>
                    </div>
                    <div className="recruiter-edit__fields">
                      <label className="recruiter-edit__field">
                        <span>Имя <span className="required">*</span></span>
                        <input
                          value={form.name}
                          disabled={isSaving}
                          onChange={(e) => setForm({ ...form, name: e.target.value })}
                          placeholder="Например: Анна Соколова"
                          required
                        />
                        {fieldError.name && <span className="field-error">{fieldError.name}</span>}
                      </label>
                  <label className="recruiter-edit__field">
                    <span>Регион <span className="required">*</span></span>
                    <select value={form.tz} onChange={(e) => setForm({ ...form, tz: e.target.value })} required disabled={isSaving}>
                      {tzOptions.map((tz) => (
                        <option key={tz.value} value={tz.value}>{tz.label}</option>
                      ))}
                    </select>
                    <span className="subtitle">
                      Используется как базовая таймзона рекрутёра.
                      {tzPreview && ` Сейчас: ${tzPreview}`}
                    </span>
                    {fieldError.tz && <span className="field-error">{fieldError.tz}</span>}
                  </label>
                    </div>
                  </div>

                  <div className="glass recruiter-edit__section">
                    <div className="recruiter-edit__section-header">
                      <div>
                        <h3>Контакты</h3>
                        <p className="subtitle">Телемост и chat_id для интеграции с ботом.</p>
                      </div>
                    </div>
                    <div className="recruiter-edit__fields">
                      <label className="recruiter-edit__field">
                        <span>Ссылка на Телемост</span>
                        <input
                          type="url"
                          value={form.telemost_url}
                          disabled={isSaving}
                          onChange={(e) => setForm({ ...form, telemost_url: e.target.value })}
                          placeholder="https://telemost.yandex.ru/j/XXXXX"
                        />
                        {fieldError.telemost_url && <span className="field-error">{fieldError.telemost_url}</span>}
                      </label>
                      <label className="recruiter-edit__field">
                        <span>Telegram chat_id</span>
                        <input
                          type="text"
                          inputMode="numeric"
                          value={form.tg_chat_id}
                          disabled={isSaving}
                          onChange={(e) => setForm({ ...form, tg_chat_id: e.target.value })}
                          placeholder="Например: 7588303412"
                        />
                        <span className="subtitle">Только цифры; можно оставить пустым.</span>
                        {fieldError.tg_chat_id && <span className="field-error">{fieldError.tg_chat_id}</span>}
                      </label>
                    </div>
                  </div>

                  <div className="glass recruiter-edit__section">
                    <div className="recruiter-edit__section-header">
                      <div>
                        <h3>Ответственные города</h3>
                        <p className="subtitle">Укажите города, где рекрутёр ведёт кандидатов.</p>
                      </div>
                      <span className="recruiter-edit__counter">{counterText}</span>
                    </div>

                    <div className="recruiter-edit__search">
                    <input
                      type="search"
                      placeholder="Поиск города"
                      value={citySearch}
                      disabled={isSaving}
                      onChange={(e) => setCitySearch(e.target.value)}
                    />
                    <button
                      className="ui-btn ui-btn--ghost"
                      onClick={() => setForm((prev) => ({ ...prev, city_ids: [] }))}
                      disabled={isSaving}
                      type="button"
                    >
                        Очистить
                      </button>
                    </div>

                    <div className="recruiter-edit__chips">
                      {selectedCities.length === 0 && (
                        <span className="subtitle">Города пока не выбраны</span>
                      )}
                      {selectedCities.slice(0, 6).map((city) => (
                        <span key={city.id} className="chip chip--soft">{city.name}</span>
                      ))}
                      {selectedCities.length > 6 && (
                        <span className="chip chip--soft">+{selectedCities.length - 6}</span>
                      )}
                    </div>

                    <div className="recruiter-edit__cities">
                      {filteredCities.map((city) => {
                        const selected = form.city_ids.includes(city.id)
                        return (
                          <label key={city.id} className={`recruiter-edit__city ${selected ? 'is-selected' : ''}`}>
                        <input
                          type="checkbox"
                          checked={selected}
                          disabled={isSaving}
                          onChange={() => toggleCity(city.id)}
                        />
                            <span>{city.name}</span>
                            <small>{city.tz || '—'}</small>
                          </label>
                        )
                      })}
                    </div>

                    {filteredCities.length === 0 && (
                      <p className="subtitle" style={{ marginTop: 8 }}>Совпадений не найдено</p>
                    )}
                  </div>
                </div>

                <aside className="recruiter-edit__aside">
                  <div className="glass recruiter-edit__section recruiter-edit__aside-card">
                    <h3>Сводка</h3>
                    <div className="recruiter-edit__stats">
                      <div>
                        <span>Свободно</span>
                        <strong>{stats.free}</strong>
                      </div>
                      <div>
                        <span>Ожидают</span>
                        <strong>{stats.pending}</strong>
                      </div>
                      <div>
                        <span>Занято</span>
                        <strong>{stats.booked}</strong>
                      </div>
                      <div>
                        <span>Всего</span>
                        <strong>{stats.total}</strong>
                      </div>
                    </div>
                    <div className="recruiter-edit__load">
                      <div>
                        <span>Занятость</span>
                        <strong>{loadPercent}%</strong>
                      </div>
                      <div className="recruiter-edit__load-bar">
                        <span style={{ width: `${Math.min(loadPercent, 100)}%` }} />
                      </div>
                    </div>
                    <div className="recruiter-edit__next">
                      <span>Ближайший слот</span>
                      <strong>{summary?.next_free_local || 'Нет свободных'}</strong>
                    </div>
                  </div>
                  <div className="glass recruiter-edit__section recruiter-edit__aside-card">
                    <h3>Сервис</h3>
                    <p className="subtitle">Проверьте доступность ключевых каналов связи.</p>
                    <ul className="recruiter-edit__list">
                      <li>Телемост: {form.telemost_url ? 'подключен' : 'нет ссылки'}</li>
                      <li>Telegram: {form.tg_chat_id ? 'подключен' : 'нет chat_id'}</li>
                      <li>Аккаунт: {form.active ? 'активен' : 'выключен'}</li>
                    </ul>
                  </div>
                </aside>
              </div>

              <div className="action-row recruiter-edit__actions">
            <button className="ui-btn ui-btn--primary" onClick={() => mutation.mutate()} disabled={isSaving}>
              {isSaving ? 'Сохраняем…' : 'Сохранить'}
            </button>
                <button
                  className="ui-btn ui-btn--ghost"
                  onClick={() => setForm(initialForm.current)}
                  disabled={!isDirty}
                  type="button"
                >
                  Сбросить
                </button>
                <Link to="/app/recruiters" className="ui-btn ui-btn--ghost">Отмена</Link>
                <button
                  className="ui-btn ui-btn--danger"
                  onClick={() => window.confirm('Удалить рекрутёра? Это действие нельзя отменить.') && deleteMutation.mutate()}
                  disabled={deleteMutation.isPending}
                >
                  {deleteMutation.isPending ? 'Удаляем…' : 'Удалить'}
                </button>
              </div>
              {formError && <p style={{ color: '#f07373' }}>Ошибка: {formError}</p>}
              {deleteMutation.isError && <p style={{ color: '#f07373' }}>Ошибка: {(deleteMutation.error as Error).message}</p>}
            </>
          )}
        </div>
      </div>
    </RoleGuard>
  )
}
