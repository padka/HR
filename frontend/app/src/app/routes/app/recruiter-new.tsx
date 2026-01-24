import { useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'

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
  const counterText = selectedCount === 0 ? '0 выбрано' : selectedCount === 1 ? '1 выбран' : `${selectedCount} выбрано`

  return (
    <RoleGuard allow={['admin']}>
      <div className="page">
        <div className="glass panel" style={{ display: 'grid', gap: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <div>
              <h1 className="title">Новый рекрутёр</h1>
              <p className="subtitle">Создайте запись, чтобы бот мог назначать встречи.</p>
            </div>
            <Link to="/app/recruiters" className="glass action-link">← Назад</Link>
          </div>

          {/* Basic info section */}
          <div className="glass" style={{ padding: 16 }}>
            <h3 style={{ marginBottom: 12 }}>Основные данные</h3>
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
                <span className="subtitle" style={{ fontSize: 11 }}>Определяет локальное время при создании слотов</span>
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
              <span className="subtitle" style={{ fontSize: 11 }}>Неактивные рекрутёры скрываются из расписаний</span>
            </div>
          </div>

          {/* Contacts section */}
          <div className="glass" style={{ padding: 16 }}>
            <h3 style={{ marginBottom: 12 }}>Контакты</h3>
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
            <p className="subtitle" style={{ marginBottom: 12 }}>Выберите один или несколько городов</p>

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
                  background: 'var(--accent)',
                  color: 'white',
                  padding: '6px 12px',
                  borderRadius: 16,
                  fontSize: 14,
                  fontWeight: 600,
                  minWidth: 70,
                  textAlign: 'center'
                }}
              >
                {counterText}
              </span>
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
              💡 Совет: используйте поиск или кликайте по карточкам для выбора
            </p>
          </div>

          <div className="action-row">
            <button className="ui-btn ui-btn--primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
              {mutation.isPending ? 'Сохраняем…' : 'Создать'}
            </button>
            <Link to="/app/recruiters" className="ui-btn ui-btn--ghost">Отмена</Link>
          </div>
          {formError && <p style={{ color: '#f07373' }}>Ошибка: {formError}</p>}
        </div>
      </div>
    </RoleGuard>
  )
}
