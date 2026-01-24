import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'

type Recruiter = { id: number; name: string; tz?: string | null }
type TimezoneOption = { value: string; label: string; region?: string; offset?: string }

// City name to timezone mapping for auto-suggestion
const CITY_TZ_MAP: Record<string, string> = {
  'москва': 'Europe/Moscow',
  'санкт-петербург': 'Europe/Moscow',
  'питер': 'Europe/Moscow',
  'спб': 'Europe/Moscow',
  'калининград': 'Europe/Kaliningrad',
  'самара': 'Europe/Samara',
  'екатеринбург': 'Asia/Yekaterinburg',
  'новосибирск': 'Asia/Novosibirsk',
  'красноярск': 'Asia/Krasnoyarsk',
  'иркутск': 'Asia/Irkutsk',
  'владивосток': 'Asia/Vladivostok',
  'сочи': 'Europe/Moscow',
  'краснодар': 'Europe/Moscow',
  'ростов-на-дону': 'Europe/Moscow',
  'нижний новгород': 'Europe/Moscow',
  'минск': 'Europe/Minsk',
  'алматы': 'Asia/Almaty',
  'алма-ата': 'Asia/Almaty',
}

function isValidTimezone(tz: string): boolean {
  try {
    new Intl.DateTimeFormat('ru-RU', { timeZone: tz }).format()
    return true
  } catch {
    return false
  }
}

function formatTimeInTz(tz: string): string {
  try {
    return new Intl.DateTimeFormat('ru-RU', {
      timeZone: tz,
      hour: '2-digit',
      minute: '2-digit',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    }).format(new Date())
  } catch {
    return ''
  }
}

export function CityNewPage() {
  const navigate = useNavigate()
  const { data: recruiters } = useQuery<Recruiter[]>({
    queryKey: ['recruiters'],
    queryFn: () => apiFetch('/recruiters'),
  })
  const { data: timezones } = useQuery<TimezoneOption[]>({
    queryKey: ['timezones'],
    queryFn: () => apiFetch('/timezones'),
  })

  const [form, setForm] = useState({
    name: '',
    tz: 'Europe/Moscow',
    active: true,
    plan_week: '',
    plan_month: '',
    criteria: '',
    experts: '',
    recruiter_ids: [] as number[],
  })
  const [tzTouched, setTzTouched] = useState(false)
  const [recruiterSearch, setRecruiterSearch] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<{ name?: string; tz?: string; plan_week?: string; plan_month?: string }>({})

  // Auto-suggest timezone based on city name
  useEffect(() => {
    if (tzTouched) return
    const key = form.name.toLowerCase().trim()
    const guess = CITY_TZ_MAP[key]
    if (guess) {
      setForm(prev => ({ ...prev, tz: guess }))
    }
  }, [form.name, tzTouched])

  const mutation = useMutation({
    mutationFn: async () => {
      setFormError(null)
      setFieldError({})
      if (!form.name.trim()) {
        setFieldError({ name: 'Укажите название города' })
        throw new Error('invalid_form')
      }
      if (!form.tz.trim()) {
        setFieldError({ tz: 'Укажите часовой пояс' })
        throw new Error('invalid_form')
      }
      if (!isValidTimezone(form.tz)) {
        setFieldError({ tz: 'Некорректная IANA TZ (например, Europe/Moscow)' })
        throw new Error('invalid_form')
      }
      if (form.plan_week && Number.isNaN(Number(form.plan_week))) {
        setFieldError({ plan_week: 'План/нед должен быть числом' })
        throw new Error('invalid_form')
      }
      if (form.plan_month && Number.isNaN(Number(form.plan_month))) {
        setFieldError({ plan_month: 'План/мес должен быть числом' })
        throw new Error('invalid_form')
      }
      const payload = {
        name: form.name,
        tz: form.tz,
        active: form.active,
        plan_week: form.plan_week ? Number(form.plan_week) : null,
        plan_month: form.plan_month ? Number(form.plan_month) : null,
        criteria: form.criteria || null,
        experts: form.experts || null,
        recruiter_ids: form.recruiter_ids,
      }
      return apiFetch('/cities', { method: 'POST', body: JSON.stringify(payload) })
    },
    onSuccess: () => navigate({ to: '/app/cities' }),
    onError: (err) => {
      if (err instanceof Error && err.message === 'invalid_form') return
      let message = err instanceof Error ? err.message : 'Ошибка'
      try {
        const parsed = JSON.parse(message)
        if (parsed?.error) {
          message = parsed.error
        }
      } catch {
        // ignore parsing errors
      }
      setFormError(message)
    },
  })

  const recruiterList = useMemo(() => recruiters || [], [recruiters])

  const filteredRecruiters = useMemo(() => {
    const term = recruiterSearch.toLowerCase().trim()
    if (!term) return recruiterList
    return recruiterList.filter(r =>
      r.name.toLowerCase().includes(term) ||
      (r.tz && r.tz.toLowerCase().includes(term))
    )
  }, [recruiterList, recruiterSearch])

  const toggleRecruiter = (id: number) => {
    setForm(prev => ({
      ...prev,
      recruiter_ids: prev.recruiter_ids.includes(id)
        ? prev.recruiter_ids.filter(x => x !== id)
        : [...prev.recruiter_ids, id]
    }))
  }

  const tzOptions = useMemo(() => {
    const opts = timezones || []
    if (form.tz && !opts.find((o) => o.value === form.tz)) {
      return [...opts, { value: form.tz, label: form.tz }]
    }
    return opts
  }, [timezones, form.tz])

  const tzValid = isValidTimezone(form.tz)
  const tzNow = tzValid ? formatTimeInTz(form.tz) : ''
  const selectedRecruiterCount = form.recruiter_ids.length

  return (
    <RoleGuard allow={['admin']}>
      <div className="page">
        <div className="glass panel" style={{ display: 'grid', gap: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <div>
              <h1 className="title">Новый город</h1>
              <p className="subtitle">Кириллица поддерживается, таймзона подставится автоматически.</p>
            </div>
            <Link to="/app/cities" className="glass action-link">← К списку городов</Link>
          </div>

          {/* Basic parameters */}
          <div className="glass" style={{ padding: 16 }}>
            <h3 style={{ marginBottom: 12 }}>Параметры</h3>
            <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
              <label style={{ display: 'grid', gap: 6 }}>
                <span>Название <span style={{ color: 'var(--accent)' }}>*</span></span>
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Например: Новосибирск"
                  autoFocus
                  required
                />
                {fieldError.name && <span style={{ color: '#f07373', fontSize: 12 }}>{fieldError.name}</span>}
              </label>

              <label style={{ display: 'grid', gap: 6 }}>
                <span>Часовой пояс (IANA) <span style={{ color: 'var(--accent)' }}>*</span></span>
                <select
                  value={form.tz}
                  onChange={(e) => { setForm({ ...form, tz: e.target.value }); setTzTouched(true) }}
                  required
                >
                  {tzOptions.map((tz) => (
                    <option key={tz.value} value={tz.value}>{tz.label}</option>
                  ))}
                </select>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  <span
                    style={{
                      padding: '2px 8px',
                      borderRadius: 6,
                      fontSize: 11,
                      background: tzValid ? 'rgba(100, 200, 100, 0.15)' : 'rgba(240, 115, 115, 0.15)',
                      border: tzValid ? '1px solid rgba(100, 200, 100, 0.3)' : '1px solid rgba(240, 115, 115, 0.3)',
                      color: tzValid ? 'rgb(100, 200, 100)' : '#f07373'
                    }}
                  >
                    {tzValid ? 'TZ OK' : 'Некорректная TZ'}
                  </span>
                  {tzNow && <span className="subtitle" style={{ fontSize: 11 }}>Сейчас там: {tzNow}</span>}
                </div>
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
            </div>
          </div>

          {/* Plan section */}
          <div className="glass" style={{ padding: 16 }}>
            <h3 style={{ marginBottom: 12 }}>План найма</h3>
            <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
              <div>
                <label style={{ display: 'grid', gap: 6 }}>
                  <span>План, неделя</span>
                  <input
                    type="number"
                    min="0"
                    value={form.plan_week}
                    onChange={(e) => setForm({ ...form, plan_week: e.target.value })}
                    placeholder="0"
                  />
                </label>
                <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                  {[5, 10, 20].map(v => (
                    <button
                      key={v}
                      type="button"
                      className="ui-btn ui-btn--ghost"
                      style={{ padding: '4px 10px', fontSize: 12 }}
                      onClick={() => setForm({ ...form, plan_week: String(v) })}
                    >
                      {v}
                    </button>
                  ))}
                </div>
                {fieldError.plan_week && <span style={{ color: '#f07373', fontSize: 12 }}>{fieldError.plan_week}</span>}
              </div>
              <div>
                <label style={{ display: 'grid', gap: 6 }}>
                  <span>План, месяц</span>
                  <input
                    type="number"
                    min="0"
                    value={form.plan_month}
                    onChange={(e) => setForm({ ...form, plan_month: e.target.value })}
                    placeholder="0"
                  />
                </label>
                <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                  {[30, 60, 100].map(v => (
                    <button
                      key={v}
                      type="button"
                      className="ui-btn ui-btn--ghost"
                      style={{ padding: '4px 10px', fontSize: 12 }}
                      onClick={() => setForm({ ...form, plan_month: String(v) })}
                    >
                      {v}
                    </button>
                  ))}
                </div>
                {fieldError.plan_month && <span style={{ color: '#f07373', fontSize: 12 }}>{fieldError.plan_month}</span>}
              </div>
            </div>
          </div>

          {/* Additional info */}
          <div className="glass" style={{ padding: 16 }}>
            <h3 style={{ marginBottom: 12 }}>Дополнительно</h3>
            <div style={{ display: 'grid', gap: 12 }}>
              <label style={{ display: 'grid', gap: 6 }}>
                <span>Фильтр/Критерии</span>
                <textarea
                  rows={3}
                  value={form.criteria}
                  onChange={(e) => setForm({ ...form, criteria: e.target.value })}
                  placeholder="Критерии отбора для города"
                />
              </label>

              <label style={{ display: 'grid', gap: 6 }}>
                <span>Контакты/Эксперты</span>
                <textarea
                  rows={3}
                  value={form.experts}
                  onChange={(e) => setForm({ ...form, experts: e.target.value })}
                  placeholder="Контактные лица или эксперты для города"
                />
              </label>
            </div>
          </div>

          {/* Recruiters section */}
          <div className="glass" style={{ padding: 16 }}>
            <h3 style={{ marginBottom: 4 }}>Ответственные рекрутёры</h3>
            <p className="subtitle" style={{ marginBottom: 12 }}>Выберите одного или нескольких рекрутёров</p>

            <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
              <input
                type="search"
                placeholder="Поиск рекрутёра"
                value={recruiterSearch}
                onChange={(e) => setRecruiterSearch(e.target.value)}
                style={{ flex: 1, minWidth: 180 }}
              />
              <span
                style={{
                  background: selectedRecruiterCount > 0 ? 'var(--accent)' : 'rgba(150, 150, 150, 0.3)',
                  color: 'white',
                  padding: '6px 12px',
                  borderRadius: 16,
                  fontSize: 14,
                  fontWeight: 600,
                  minWidth: 70,
                  textAlign: 'center'
                }}
              >
                {selectedRecruiterCount === 0 ? '0 выбрано' : selectedRecruiterCount === 1 ? '1 выбран' : `${selectedRecruiterCount} выбрано`}
              </span>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                gap: 8,
                maxHeight: 250,
                overflowY: 'auto',
                padding: 4
              }}
            >
              {filteredRecruiters.map(rec => {
                const selected = form.recruiter_ids.includes(rec.id)
                return (
                  <label
                    key={rec.id}
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
                      onChange={() => toggleRecruiter(rec.id)}
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
                    <span style={{ fontWeight: 500 }}>{rec.name}</span>
                    <span className="subtitle" style={{ fontSize: 11 }}>{rec.tz || '—'}</span>
                  </label>
                )
              })}
            </div>

            {filteredRecruiters.length === 0 && (
              <p className="subtitle" style={{ marginTop: 8 }}>Рекрутёров не найдено</p>
            )}
          </div>

          <div className="action-row">
            <button className="ui-btn ui-btn--primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
              {mutation.isPending ? 'Сохраняем…' : 'Создать'}
            </button>
            <Link to="/app/cities" className="ui-btn ui-btn--ghost">Отмена</Link>
          </div>
          {formError && <p style={{ color: '#f07373' }}>Ошибка: {formError}</p>}
        </div>
      </div>
    </RoleGuard>
  )
}
