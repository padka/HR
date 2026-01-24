import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'

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

export function RecruiterEditPage() {
  const params = useParams({ from: 'recruiterEdit' })
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

  useEffect(() => {
    if (!detailQuery.data) return
    setForm({
      name: detailQuery.data.name || '',
      tz: detailQuery.data.tz || 'Europe/Moscow',
      tg_chat_id: detailQuery.data.tg_chat_id ? String(detailQuery.data.tg_chat_id) : '',
      telemost_url: detailQuery.data.telemost_url || '',
      active: Boolean(detailQuery.data.active),
      city_ids: detailQuery.data.city_ids || [],
    })
  }, [detailQuery.data])

  const mutation = useMutation({
    mutationFn: async () => {
      setFormError(null)
      setFieldError({})
      if (!form.name.trim()) {
        setFieldError({ name: 'Укажите имя' })
        throw new Error('invalid_form')
      }
      if (!form.tz.trim()) {
        setFieldError({ tz: 'Укажите часовой пояс' })
        throw new Error('invalid_form')
      }
      if (form.tg_chat_id && Number.isNaN(Number(form.tg_chat_id))) {
        setFieldError({ tg_chat_id: 'TG chat ID должен быть числом' })
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

  return (
    <RoleGuard allow={['admin']}>
      <div className="page">
        <div className="glass panel" style={{ display: 'grid', gap: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <Link to="/app/recruiters" className="glass action-link">← К списку рекрутёров</Link>
          </div>

          {detailQuery.isLoading && <p className="subtitle">Загрузка…</p>}
          {detailQuery.isError && <p style={{ color: '#f07373' }}>Ошибка: {(detailQuery.error as Error).message}</p>}

          {!detailQuery.isLoading && (
            <>
              {/* Summary card */}
              <div className="glass" style={{ padding: 16, display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
                <div
                  style={{
                    width: 56,
                    height: 56,
                    borderRadius: '50%',
                    background: 'var(--accent)',
                    color: 'white',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 20,
                    fontWeight: 600,
                    flexShrink: 0
                  }}
                >
                  {initials}
                </div>
                <div style={{ flex: 1, minWidth: 200 }}>
                  <p className="subtitle" style={{ marginBottom: 2 }}>Редактирование рекрутёра</p>
                  <h2 style={{ margin: 0, fontSize: 20 }}>{form.name || 'Без имени'}</h2>
                  <div style={{ display: 'flex', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
                    <span className="glass" style={{ padding: '2px 8px', borderRadius: 6, fontSize: 12 }}>ID #{recruiterId}</span>
                    <span className="glass" style={{ padding: '2px 8px', borderRadius: 6, fontSize: 12 }}>{form.tz}</span>
                    <span className="glass" style={{ padding: '2px 8px', borderRadius: 6, fontSize: 12, opacity: form.telemost_url ? 1 : 0.5 }}>
                      {form.telemost_url || 'Телемост не указан'}
                    </span>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <div className="glass" style={{ padding: '8px 12px', borderRadius: 8, textAlign: 'center' }}>
                    <span className="subtitle" style={{ fontSize: 11 }}>Города</span>
                    <div style={{ fontWeight: 600 }}>{selectedCount}</div>
                  </div>
                  <div className="glass" style={{ padding: '8px 12px', borderRadius: 8, textAlign: 'center' }}>
                    <span className="subtitle" style={{ fontSize: 11 }}>Telegram</span>
                    <div style={{ fontWeight: 600 }}>{form.tg_chat_id ? 'Подключен' : 'Не указан'}</div>
                  </div>
                  <div
                    className="glass"
                    style={{
                      padding: '8px 12px',
                      borderRadius: 8,
                      textAlign: 'center',
                      background: form.active ? 'rgba(100, 200, 100, 0.1)' : 'rgba(150, 150, 150, 0.1)'
                    }}
                  >
                    <span className="subtitle" style={{ fontSize: 11 }}>Статус</span>
                    <div style={{ fontWeight: 600, color: form.active ? 'rgb(100, 200, 100)' : 'inherit' }}>
                      {form.active ? 'Активен' : 'Отключен'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Basic info section */}
              <div className="glass" style={{ padding: 16 }}>
                <h3 style={{ marginBottom: 4 }}>Основные данные</h3>
                <p className="subtitle" style={{ marginBottom: 12 }}>Имя и рабочий регион для расчёта локального времени</p>
                <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
                  <label style={{ display: 'grid', gap: 6 }}>
                    <span>Имя <span style={{ color: 'var(--accent)' }}>*</span></span>
                    <input
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                      placeholder="Например: Анна Соколова"
                      required
                    />
                    {fieldError.name && <span style={{ color: '#f07373', fontSize: 12 }}>{fieldError.name}</span>}
                  </label>

                  <label style={{ display: 'grid', gap: 6 }}>
                    <span>Регион <span style={{ color: 'var(--accent)' }}>*</span></span>
                    <select value={form.tz} onChange={(e) => setForm({ ...form, tz: e.target.value })} required>
                      {tzOptions.map((tz) => (
                        <option key={tz.value} value={tz.value}>{tz.label}</option>
                      ))}
                    </select>
                    <span className="subtitle" style={{ fontSize: 11 }}>Используется как базовая таймзона рекрутёра</span>
                    {fieldError.tz && <span style={{ color: '#f07373', fontSize: 12 }}>{fieldError.tz}</span>}
                  </label>
                </div>

                <div style={{ marginTop: 12 }}>
                  <label style={{ display: 'flex', gap: 8, alignItems: 'center', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={form.active}
                      onChange={(e) => setForm({ ...form, active: e.target.checked })}
                    />
                    <span>Активен</span>
                  </label>
                  <span className="subtitle" style={{ fontSize: 11 }}>Неактивные рекрутёры скрываются из расписаний и не получают новые назначения</span>
                </div>
              </div>

              {/* Contacts section */}
              <div className="glass" style={{ padding: 16 }}>
                <h3 style={{ marginBottom: 4 }}>Контакты</h3>
                <p className="subtitle" style={{ marginBottom: 12 }}>Укажите ссылку на Телемост и chat_id для интеграции с ботом</p>
                <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
                  <label style={{ display: 'grid', gap: 6 }}>
                    <span>Ссылка на Телемост</span>
                    <input
                      type="url"
                      value={form.telemost_url}
                      onChange={(e) => setForm({ ...form, telemost_url: e.target.value })}
                      placeholder="https://telemost.yandex.ru/j/XXXXX"
                    />
                    {fieldError.telemost_url && <span style={{ color: '#f07373', fontSize: 12 }}>{fieldError.telemost_url}</span>}
                  </label>

                  <label style={{ display: 'grid', gap: 6 }}>
                    <span>Telegram chat_id</span>
                    <input
                      type="text"
                      inputMode="numeric"
                      value={form.tg_chat_id}
                      onChange={(e) => setForm({ ...form, tg_chat_id: e.target.value })}
                      placeholder="Например: 7588303412"
                    />
                    <span className="subtitle" style={{ fontSize: 11 }}>Только цифры; можно оставить пустым</span>
                    {fieldError.tg_chat_id && <span style={{ color: '#f07373', fontSize: 12 }}>{fieldError.tg_chat_id}</span>}
                  </label>
                </div>
              </div>

              {/* Cities section */}
              <div className="glass" style={{ padding: 16 }}>
                <h3 style={{ marginBottom: 4 }}>Ответственные города</h3>
                <p className="subtitle" style={{ marginBottom: 12 }}>Выберите один или несколько городов. Они появятся в карточке рекрутёра и в фильтрах расписания.</p>

                <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
                  <input
                    type="search"
                    placeholder="Поиск города"
                    value={citySearch}
                    onChange={(e) => setCitySearch(e.target.value)}
                    style={{ flex: 1, minWidth: 180 }}
                  />
                  <span
                    style={{
                      background: selectedCount > 0 ? 'var(--accent)' : 'rgba(150, 150, 150, 0.3)',
                      color: 'white',
                      padding: '6px 12px',
                      borderRadius: 16,
                      fontSize: 14,
                      fontWeight: 600,
                      minWidth: 90,
                      textAlign: 'center'
                    }}
                  >
                    {counterText}
                  </span>
                </div>

                {/* Selected cities preview pills */}
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
                  {selectedCities.length === 0 && (
                    <span className="subtitle">Города пока не выбраны</span>
                  )}
                  {selectedCities.slice(0, 4).map(city => (
                    <span
                      key={city.id}
                      style={{
                        background: 'rgba(105, 183, 255, 0.15)',
                        border: '1px solid rgba(105, 183, 255, 0.3)',
                        padding: '4px 10px',
                        borderRadius: 16,
                        fontSize: 13
                      }}
                    >
                      {city.name}
                    </span>
                  ))}
                  {selectedCities.length > 4 && (
                    <span
                      style={{
                        background: 'rgba(150, 150, 150, 0.15)',
                        border: '1px solid rgba(150, 150, 150, 0.3)',
                        padding: '4px 10px',
                        borderRadius: 16,
                        fontSize: 13
                      }}
                    >
                      +{selectedCities.length - 4}
                    </span>
                  )}
                </div>

                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                    gap: 8,
                    maxHeight: 300,
                    overflowY: 'auto',
                    padding: 4
                  }}
                >
                  {filteredCities.map(city => {
                    const selected = form.city_ids.includes(city.id)
                    return (
                      <label
                        key={city.id}
                        style={{
                          display: 'grid',
                          gap: 2,
                          padding: '10px 12px',
                          borderRadius: 8,
                          cursor: 'pointer',
                          background: selected ? 'rgba(105, 183, 255, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                          border: selected ? '2px solid var(--accent)' : '2px solid transparent',
                          position: 'relative',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => toggleCity(city.id)}
                          style={{ position: 'absolute', opacity: 0, pointerEvents: 'none' }}
                        />
                        {selected && (
                          <span
                            style={{
                              position: 'absolute',
                              top: 6,
                              right: 6,
                              width: 18,
                              height: 18,
                              borderRadius: 4,
                              background: 'var(--accent)',
                              color: 'white',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontSize: 12,
                              fontWeight: 'bold'
                            }}
                          >
                            ✓
                          </span>
                        )}
                        <span style={{ fontWeight: 500 }}>{city.name}</span>
                        <span className="subtitle" style={{ fontSize: 11 }}>{city.tz || '—'}</span>
                      </label>
                    )
                  })}
                </div>

                {filteredCities.length === 0 && (
                  <p className="subtitle" style={{ marginTop: 8 }}>Совпадений не найдено</p>
                )}

                <p className="subtitle" style={{ marginTop: 12, fontSize: 12 }}>
                  💡 Совет: используйте поиск или кликайте по карточкам, чтобы быстро закрепить несколько городов
                </p>
              </div>

              <div className="action-row">
                <button className="ui-btn ui-btn--primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
                  {mutation.isPending ? 'Сохраняем…' : 'Сохранить'}
                </button>
                <Link to="/app/recruiters" className="ui-btn ui-btn--ghost">Отмена</Link>
                <button
                  className="ui-btn ui-btn--danger"
                  onClick={() => window.confirm('Удалить рекрутёра? Это действие нельзя отменить.') && deleteMutation.mutate()}
                  disabled={deleteMutation.isPending}
                  style={{ marginLeft: 'auto' }}
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
