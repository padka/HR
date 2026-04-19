import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'
import { formatTimeInTz, isValidTimezone } from '@/shared/utils/timezone'

type Recruiter = { id: number; name: string; tz?: string | null }
type TimezoneOption = { value: string; label: string; region?: string; offset?: string }
type CityExpertItem = { id: number | null; name: string; is_active: boolean }

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
    recruiter_ids: [] as number[],
  })
  const [expertsItems, setExpertsItems] = useState<CityExpertItem[]>([])
  const [tzTouched, setTzTouched] = useState(false)
  const [recruiterSearch, setRecruiterSearch] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<{ name?: string; tz?: string; plan_week?: string; plan_month?: string }>({})

  const setExpertPatch = (index: number, patch: Partial<CityExpertItem>) => {
    setExpertsItems((prev) => prev.map((e, i) => (i === index ? { ...e, ...patch } : e)))
  }

  const addExpert = () => {
    setExpertsItems((prev) => [...prev, { id: null, name: '', is_active: true }])
  }

  const removeExpert = (index: number) => {
    setExpertsItems((prev) => prev.filter((_, i) => i !== index))
  }

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

      const normalizeExpertName = (value: string): string => value.trim().replace(/\s+/g, ' ')
      const experts_items = expertsItems
        .map((e) => ({
          id: e.id ?? null,
          name: normalizeExpertName(e.name),
          is_active: e.is_active !== false,
        }))
        .filter((e) => e.name)
      const experts_text = experts_items
        .filter((e) => e.is_active)
        .map((e) => e.name)
        .join('\n')
        .trim() || null

      const payload = {
        name: form.name,
        tz: form.tz,
        active: form.active,
        plan_week: form.plan_week ? Number(form.plan_week) : null,
        plan_month: form.plan_month ? Number(form.plan_month) : null,
        criteria: form.criteria || null,
        experts: experts_text,
        experts_items,
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
        <div className="glass panel ui-form-shell">
          <div className="ui-form-header">
            <div>
              <h1 className="title">Новый город</h1>
              <p className="subtitle">Кириллица поддерживается, таймзона подставится автоматически.</p>
            </div>
            <Link to="/app/cities" className="glass action-link">← К списку городов</Link>
          </div>

          {/* Basic parameters */}
          <div className="glass city-form__section">
            <h3 className="city-form__section-title">Параметры</h3>
            <div className="ui-form-grid ui-form-grid--md">
              <label className="ui-field">
                <span>Название <span className="ui-required">*</span></span>
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Например: Новосибирск"
                  autoFocus
                  required
                />
                {fieldError.name && <span className="ui-field__error">{fieldError.name}</span>}
              </label>

              <label className="ui-field">
                <span>Часовой пояс (IANA) <span className="ui-required">*</span></span>
                <select
                  value={form.tz}
                  onChange={(e) => { setForm({ ...form, tz: e.target.value }); setTzTouched(true) }}
                  required
                  data-testid="city-tz-input"
                >
                  {tzOptions.map((tz) => (
                    <option key={tz.value} value={tz.value}>{tz.label}</option>
                  ))}
                </select>
                <div className="ui-field__status-row city-form__tz-status">
                  <span className={`city-form__tz-pill ${tzValid ? 'is-valid' : 'is-invalid'}`}>
                    {tzValid ? 'TZ OK' : 'Некорректная TZ'}
                  </span>
                  {tzNow && <span className="ui-field__note city-form__tz-now">Сейчас там: {tzNow}</span>}
                </div>
                {fieldError.tz && <span className="ui-field__error">{fieldError.tz}</span>}
              </label>
            </div>

            <div className="city-form__toggle">
              <label className="ui-inline-checkbox">
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
          <div className="glass city-form__section">
            <h3 className="city-form__section-title">План найма</h3>
            <div className="ui-form-grid ui-form-grid--md">
              <div>
                <label className="ui-field">
                  <span>План, неделя</span>
                  <input
                    type="number"
                    min="0"
                    value={form.plan_week}
                    onChange={(e) => setForm({ ...form, plan_week: e.target.value })}
                    placeholder="0"
                  />
                </label>
                <div className="city-form__chips">
                  {[5, 10, 20].map(v => (
                    <button
                      key={v}
                      type="button"
                      className="ui-btn ui-btn--ghost city-form__chip-btn"
                      onClick={() => setForm({ ...form, plan_week: String(v) })}
                    >
                      {v}
                    </button>
                  ))}
                </div>
                {fieldError.plan_week && (
                  <div className="ui-field__support">
                    <span className="ui-field__error">{fieldError.plan_week}</span>
                  </div>
                )}
              </div>
              <div>
                <label className="ui-field">
                  <span>План, месяц</span>
                  <input
                    type="number"
                    min="0"
                    value={form.plan_month}
                    onChange={(e) => setForm({ ...form, plan_month: e.target.value })}
                    placeholder="0"
                  />
                </label>
                <div className="city-form__chips">
                  {[30, 60, 100].map(v => (
                    <button
                      key={v}
                      type="button"
                      className="ui-btn ui-btn--ghost city-form__chip-btn"
                      onClick={() => setForm({ ...form, plan_month: String(v) })}
                    >
                      {v}
                    </button>
                  ))}
                </div>
                {fieldError.plan_month && (
                  <div className="ui-field__support">
                    <span className="ui-field__error">{fieldError.plan_month}</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Additional info */}
          <div className="glass city-form__section">
            <h3 className="city-form__section-title">Дополнительно</h3>
            <div className="ui-form-grid">
              <label className="ui-field">
                <span>Фильтр/Критерии</span>
                <textarea
                  rows={3}
                  value={form.criteria}
                  onChange={(e) => setForm({ ...form, criteria: e.target.value })}
                  placeholder="Критерии отбора для города"
                />
              </label>

              <div className="ui-form-grid">
                <div className="city-form__experts-head">
                  <span>Эксперты</span>
                  <button type="button" className="ui-btn ui-btn--secondary" onClick={addExpert}>
                    + Эксперт
                  </button>
                </div>
                <div className="text-muted text-xs">
                  Список экспертов для города. Используется в отчётных и операционных сценариях.
                </div>
                {expertsItems.length === 0 && <div className="text-muted text-sm">Эксперты не добавлены</div>}
                <div className="city-form__experts-list">
                  {expertsItems.map((exp, idx) => (
                    <div key={exp.id ?? `new-${idx}`} className="glass city-form__expert-item">
                      <div className="city-form__expert-row">
                        <input
                          value={exp.name}
                          onChange={(e) => setExpertPatch(idx, { name: e.target.value })}
                          placeholder="ФИО эксперта"
                          className="city-form__expert-input"
                        />
                        <label className="ui-inline-checkbox">
                          <input
                            type="checkbox"
                            checked={exp.is_active !== false}
                            onChange={(e) => setExpertPatch(idx, { is_active: e.target.checked })}
                          />
                          <span className="text-muted text-xs">Активен</span>
                        </label>
                        <button type="button" className="ui-btn ui-btn--ghost" onClick={() => removeExpert(idx)}>
                          Удалить
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Recruiters section */}
          <div className="glass city-form__section">
            <h3 className="city-form__section-title--compact">Ответственные рекрутёры</h3>
            <p className="subtitle city-form__section-note">Выберите одного или нескольких рекрутёров</p>

            <div className="city-form__recruiters-head">
              <input
                type="search"
                placeholder="Поиск рекрутёра"
                value={recruiterSearch}
                onChange={(e) => setRecruiterSearch(e.target.value)}
                className="city-form__recruiters-search"
              />
              <span
                className={`city-form__recruiters-counter ${
                  selectedRecruiterCount > 0 ? 'is-selected' : 'is-empty'
                }`}
              >
                {selectedRecruiterCount === 0 ? '0 выбрано' : selectedRecruiterCount === 1 ? '1 выбран' : `${selectedRecruiterCount} выбрано`}
              </span>
            </div>

            <div className="city-form__recruiters-grid">
              {filteredRecruiters.map(rec => {
                const selected = form.recruiter_ids.includes(rec.id)
                return (
                  <label
                    key={rec.id}
                    className={`city-form__recruiter-card ${selected ? 'is-selected' : ''}`}
                  >
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => toggleRecruiter(rec.id)}
                      className="city-form__recruiter-check-input"
                    />
                    {selected && (
                      <span className="city-form__recruiter-check">✓</span>
                    )}
                    <span className="city-form__recruiter-name">{rec.name}</span>
                    <span className="subtitle city-form__recruiter-tz">{rec.tz || '—'}</span>
                  </label>
                )
              })}
            </div>

            {filteredRecruiters.length === 0 && (
              <p className="subtitle">Рекрутёров не найдено</p>
            )}
          </div>

          <div className="ui-form-actions ui-form-actions--end">
            <button className="ui-btn ui-btn--primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
              {mutation.isPending ? 'Сохраняем…' : 'Создать'}
            </button>
            <Link to="/app/cities" className="ui-btn ui-btn--ghost">Отмена</Link>
          </div>
          {formError && <p className="ui-message ui-message--error">Ошибка: {formError}</p>}
        </div>
      </div>
    </RoleGuard>
  )
}
