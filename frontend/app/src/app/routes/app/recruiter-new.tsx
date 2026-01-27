import { useMemo, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'
import { getTzPreview, validateRecruiterForm } from './recruiter-form'

type City = { id: number; name: string; tz?: string | null }
type TimezoneOption = { value: string; label: string; region?: string; offset?: string }

export function RecruiterNewPage() {
  const navigate = useNavigate()
  const { data: cities } = useQuery<City[]>({
    queryKey: ['cities'],
    queryFn: () => apiFetch('/cities'),
  })
  const { data: timezones } = useQuery<TimezoneOption[]>({
    queryKey: ['timezones'],
    queryFn: () => apiFetch('/timezones'),
  })

  const initialForm = useRef({
    name: '',
    tz: 'Europe/Moscow',
    tg_chat_id: '',
    telemost_url: '',
    active: true,
    city_ids: [] as number[],
  })

  const [form, setForm] = useState(initialForm.current)
  const [citySearch, setCitySearch] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<{
    name?: string
    tz?: string
    tg_chat_id?: string
    telemost_url?: string
  }>({})

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
      return apiFetch('/recruiters', { method: 'POST', body: JSON.stringify(payload) })
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

  const cityList = useMemo(() => cities || [], [cities])
  const filteredCities = useMemo(() => {
    const term = citySearch.toLowerCase().trim()
    if (!term) return cityList
    return cityList.filter((c) =>
      c.name.toLowerCase().includes(term) ||
      (c.tz && c.tz.toLowerCase().includes(term))
    )
  }, [cityList, citySearch])

  const toggleCity = (id: number) => {
    setForm((prev) => ({
      ...prev,
      city_ids: prev.city_ids.includes(id)
        ? prev.city_ids.filter((x) => x !== id)
        : [...prev.city_ids, id],
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
  const counterText =
    selectedCount === 0 ? '0 выбрано' : selectedCount === 1 ? '1 выбран' : `${selectedCount} выбрано`

  const initials = useMemo(() => {
    const parts = (form.name || '').trim().split(/\s+/)
    if (!parts[0]) return 'R'
    const first = parts[0][0] || ''
    const second = parts[1]?.[0] || ''
    return (first + second).toUpperCase() || 'R'
  }, [form.name])

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

  const selectedCities = useMemo(() => {
    return cityList.filter((city) => form.city_ids.includes(city.id))
  }, [cityList, form.city_ids])
  const tzPreview = useMemo(() => getTzPreview(form.tz), [form.tz])

  return (
    <RoleGuard allow={['admin']}>
      <div className="page recruiter-edit">
        <div className="glass panel recruiter-edit__panel">
          <div className="recruiter-edit__header">
            <div>
              <Link to="/app/recruiters" className="glass action-link">← К списку рекрутёров</Link>
              <h1 className="title">Новый рекрутёр</h1>
              <p className="subtitle">Создайте профиль и подключите его к городам и слотам.</p>
            </div>
            <div className="recruiter-edit__header-actions">
              {isDirty && <span className="badge badge--soft">Есть несохранённые изменения</span>}
              <button className="ui-btn ui-btn--primary" onClick={() => mutation.mutate()} disabled={isSaving}>
                {isSaving ? 'Сохраняем…' : 'Создать'}
              </button>
            </div>
          </div>

          <div className="glass recruiter-edit__hero">
            <div className="recruiter-edit__hero-main">
              <div className="recruiter-avatar is-away" aria-hidden="true">
                {initials}
              </div>
              <div>
                <p className="subtitle">Новый рекрутёр</p>
                <h2 className="recruiter-edit__name">{form.name || 'Без имени'}</h2>
                <div className="recruiter-edit__meta">
                  <span className="chip">{form.tz}</span>
                  <span className="chip">Черновик</span>
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
                <span>Статус</span>
                <strong>{form.active ? 'Активен' : 'Отключен'}</strong>
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
                      Определяет локальное время при создании слотов.
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
                    <p className="subtitle">Выберите города, где рекрутёр работает с кандидатами.</p>
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
                  {filteredCities.map(city => {
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
                <p className="subtitle">Проверьте данные перед сохранением.</p>
                <div className="recruiter-edit__list">
                  <div>Города: {selectedCount}</div>
                  <div>Телемост: {form.telemost_url ? 'подключен' : 'нет ссылки'}</div>
                  <div>Telegram: {form.tg_chat_id ? 'подключен' : 'нет chat_id'}</div>
                  <div>Статус: {form.active ? 'активен' : 'отключен'}</div>
                </div>
              </div>
            </aside>
          </div>

          <div className="action-row recruiter-edit__actions">
            <button className="ui-btn ui-btn--primary" onClick={() => mutation.mutate()} disabled={isSaving}>
              {isSaving ? 'Сохраняем…' : 'Создать'}
            </button>
            <button
              className="ui-btn ui-btn--ghost"
              onClick={() => setForm(initialForm.current)}
              disabled={!isDirty || isSaving}
              type="button"
            >
              Сбросить
            </button>
            <Link to="/app/recruiters" className="ui-btn ui-btn--ghost">Отмена</Link>
          </div>
          {formError && <p style={{ color: '#f07373' }}>Ошибка: {formError}</p>}
        </div>
      </div>
    </RoleGuard>
  )
}
