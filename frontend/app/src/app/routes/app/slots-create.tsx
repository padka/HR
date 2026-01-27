import { useMemo, useState, useEffect } from 'react'
import { z } from 'zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'
import { useProfile } from '@/app/hooks/useProfile'
type RecruiterPayload = {
  id: number
  name: string
  tz?: string | null
  tg_chat_id?: string | null
  active?: boolean | null
  city_ids?: number[]
}

type CityPayload = {
  id: number
  name: string
  tz?: string | null
  owner_recruiter_id?: number | null
}

const formSchema = z.object({
  recruiter_id: z.string().min(1, 'Выберите рекрутёра'),
  city_id: z.string().min(1, 'Выберите город'),
  date: z.string().min(1, 'Укажите дату'),
  time: z.string().min(1, 'Укажите время'),
})

type FormValues = z.infer<typeof formSchema>

const bulkSchema = z.object({
  recruiter_id: z.string().min(1),
  city_id: z.string().min(1),
  start_date: z.string().min(1),
  end_date: z.string().min(1),
  start_time: z.string().min(1),
  end_time: z.string().min(1),
  break_start: z.string().min(1),
  break_end: z.string().min(1),
  step_min: z.coerce.number().int().min(5, 'Минимум 5 минут').max(240, 'Слишком большой шаг'),
  include_weekends: z.boolean(),
  use_break: z.boolean(),
}).superRefine((data, ctx) => {
  if (data.start_date && data.end_date && data.start_date > data.end_date) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['end_date'], message: 'Дата окончания раньше даты начала' })
  }
  const toMin = (t: string) => {
    const [h, m] = t.split(':').map(Number)
    return h * 60 + m
  }
  const start = toMin(data.start_time)
  const end = toMin(data.end_time)
  if (end <= start) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['end_time'], message: 'Окно (до) должно быть позже старта' })
  }
  if (data.use_break) {
    const bStart = toMin(data.break_start)
    const bEnd = toMin(data.break_end)
    if (bEnd <= bStart) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['break_end'], message: 'Перерыв (до) должен быть позже старта' })
    }
    if (bStart < start || bEnd > end) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['break_start'], message: 'Перерыв должен быть внутри окна' })
    }
  }
})

export function SlotsCreateForm() {
  const qc = useQueryClient()
  const [serverError, setServerError] = useState<string | null>(null)
  const [toast, setToast] = useState<{ message: string; tone?: 'success' | 'warning' | 'error' } | null>(null)
  const profile = useProfile()
  const canUse = profile.data?.principal.type === 'recruiter'
  const [mode, setMode] = useState<'single' | 'bulk'>('single')
  const recruiter = profile.data?.recruiter
  const recruiterId = recruiter ? String(recruiter.id) : ''

  const { data: cities } = useQuery<CityPayload[]>({
    queryKey: ['cities'],
    queryFn: () => apiFetch('/cities'),
    enabled: Boolean(canUse),
  })

  const { register, handleSubmit, formState: { errors }, watch, setValue } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { recruiter_id: recruiterId, city_id: '' },
  })

  const selectedCity = watch('city_id')
  const date = watch('date')
  const time = watch('time')

  const cityObj = (cities || []).find((c) => String(c.id) === String(selectedCity))

  useEffect(() => {
    if (recruiterId) {
      setValue('recruiter_id', recruiterId)
    }
  }, [recruiterId, setValue])

  const singlePreview = useMemo(() => {
    if (!date || !time || !cityObj?.tz) return null
    const tzCity = cityObj.tz || 'Europe/Moscow'
    const tzRecruiter = recruiter?.tz || tzCity
    const utc = localToUtc(date, time, tzCity)
    if (!utc) return null
    return {
      tzCity,
      tzRecruiter,
      cityLabel: formatInTz(utc, tzCity),
      recruiterLabel: formatInTz(utc, tzRecruiter),
    }
  }, [date, time, cityObj?.tz, recruiter?.tz])

  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const showToast = (message: string, tone?: 'success' | 'warning' | 'error') => {
    setToast({ message, tone })
    window.clearTimeout((showToast as any)._t)
    ;(showToast as any)._t = window.setTimeout(() => setToast(null), 2800)
  }

  const mutation = useMutation({
    mutationFn: async (data: FormValues) => {
      setServerError(null)
      setSuccessMessage(null)
      const payload = {
        recruiter_id: Number(data.recruiter_id),
        city_id: Number(data.city_id),
        starts_at_local: `${data.date}T${data.time}`,
      }
      const res = await fetch('/slots', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        let message = `Ошибка ${res.status}`
        const contentType = res.headers.get('content-type') || ''
        if (contentType.includes('application/json')) {
          const data = await res.json().catch(() => null)
          if (data && typeof data === 'object') {
            message = (data.detail || data.message || message) as string
          }
        } else {
          const text = await res.text()
          if (text) message = text
        }
        throw new Error(message || 'Ошибка создания')
      }
      return res.json()
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['slots'] })
      setSuccessMessage('Слот успешно создан')
      showToast('Слот успешно создан', 'success')
      setTimeout(() => setSuccessMessage(null), 3000)
    },
    onError: (err: unknown) => {
      const message = (err as Error).message
      setServerError(message)
      showToast(message, 'error')
    }
  })

  const onSubmit = handleSubmit((values) => mutation.mutate(values))

  const filteredCities = cities || []

  return (
    <RoleGuard allow={['recruiter']}>
      <div className="page">
        <div className="glass panel slot-create-header">
          <div>
            <h1 className="title">Создание слотов</h1>
            <p className="subtitle">Создайте один слот или серию, а затем проверьте превью времени.</p>
          </div>
          <Link to="/app/slots" className="glass action-link">← К списку слотов</Link>
        </div>

        <div className="slot-create-tabs">
          <button
            type="button"
            className={`slot-create-tab ${mode === 'single' ? 'is-active' : ''}`}
            onClick={() => setMode('single')}
          >
            Один слот
          </button>
          <button
            type="button"
            className={`slot-create-tab ${mode === 'bulk' ? 'is-active' : ''}`}
            onClick={() => setMode('bulk')}
          >
            Серия слотов
          </button>
        </div>

        {mode === 'single' && (
          <form onSubmit={onSubmit} className="glass panel slot-create-form">
            <div className="slot-create-section">
              <h2 className="title title--sm">Один слот</h2>
              <p className="subtitle">Единичная встреча на конкретную дату и время.</p>
            </div>
            <div className="slot-create-grid">
              <input type="hidden" {...register('recruiter_id')} />
              <label className="form-group">
                <span className="form-group__label">Город</span>
                <select {...register('city_id')}>
                  <option value="">— выберите —</option>
                  {filteredCities.map((c) => (
                    <option key={c.id} value={String(c.id)}>{c.name}</option>
                  ))}
                </select>
                {errors.city_id && <span className="form-group__error">{errors.city_id.message}</span>}
              </label>
              <label className="form-group">
                <span className="form-group__label">Дата</span>
                <input {...register('date')} type="date" />
                {errors.date && <span className="form-group__error">{errors.date.message}</span>}
              </label>
              <label className="form-group">
                <span className="form-group__label">Время</span>
                <input {...register('time')} type="time" />
                {errors.time && <span className="form-group__error">{errors.time.message}</span>}
              </label>
            </div>

            <div className="slot-preview glass glass--subtle">
              <div>
                <div className="slot-preview__label">Превью времени</div>
                <div className="slot-preview__value">
                  {singlePreview
                    ? `${singlePreview.cityLabel} · ${singlePreview.tzCity}`
                    : 'Выберите город, дату и время'}
                </div>
                <div className="slot-preview__hint">Время региона (города)</div>
              </div>
              {singlePreview && singlePreview.tzRecruiter !== singlePreview.tzCity && (
                <div>
                  <div className="slot-preview__label">Ваше время</div>
                  <div className="slot-preview__value">
                    {singlePreview.recruiterLabel} · {singlePreview.tzRecruiter}
                  </div>
                  <div className="slot-preview__hint">Ваш часовой пояс отличается</div>
                </div>
              )}
            </div>

            <div className="slot-create-actions">
              <button className="ui-btn ui-btn--primary" type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? 'Создаём…' : 'Создать'}
              </button>
              {serverError && <p className="text-danger text-sm">{serverError}</p>}
              {successMessage && (
                <div className="form-success">
                  <p>{successMessage}</p>
                </div>
              )}
            </div>
          </form>
        )}

        {mode === 'bulk' && (
          <BulkCreateForm recruiter={recruiter || null} recruiterId={recruiterId} cities={cities || []} />
        )}
        {toast && (
          <div className="toast" data-tone={toast.tone}>
            {toast.message}
          </div>
        )}
      </div>
    </RoleGuard>
  )
}

function BulkCreateForm({
  recruiter,
  recruiterId,
  cities
}: {
  recruiter?: RecruiterPayload | null
  recruiterId: string
  cities: CityPayload[]
}) {
  const qc = useQueryClient()
  const [serverError, setServerError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [toast, setToast] = useState<{ message: string; tone?: 'success' | 'warning' | 'error' } | null>(null)

  const { register, handleSubmit, watch, formState: { errors }, setValue } = useForm<z.infer<typeof bulkSchema>>({
    resolver: zodResolver(bulkSchema),
    defaultValues: {
      recruiter_id: recruiterId,
      include_weekends: false,
      use_break: true,
      start_time: '10:00',
      end_time: '16:00',
      break_start: '12:00',
      break_end: '13:00',
      step_min: 30,
    }
  })

  useEffect(() => {
    if (recruiterId) {
      setValue('recruiter_id', recruiterId)
    }
  }, [recruiterId, setValue])

  const startDate = watch('start_date')
  const endDate = watch('end_date')
  const includeWeekends = watch('include_weekends')
  const startTime = watch('start_time')
  const endTime = watch('end_time')
  const breakStart = watch('break_start')
  const breakEnd = watch('break_end')
  const stepMin = Number(watch('step_min') || 30)
  const useBreak = watch('use_break')

  const filteredCities = cities

  const preview = computeBulkPreview(startDate, endDate, startTime, endTime, breakStart, breakEnd, stepMin, includeWeekends, useBreak)

  const showToast = (message: string, tone?: 'success' | 'warning' | 'error') => {
    setToast({ message, tone })
    window.clearTimeout((showToast as any)._t)
    ;(showToast as any)._t = window.setTimeout(() => setToast(null), 2800)
  }

  const mutation = useMutation({
    mutationFn: async (data: z.infer<typeof bulkSchema>) => {
      setServerError(null)
      setSuccessMessage(null)
      const body = new URLSearchParams({
        recruiter_id: String(data.recruiter_id),
        city_id: String(data.city_id),
        start_date: data.start_date,
        end_date: data.end_date,
        start_time: data.start_time,
        end_time: data.end_time,
        break_start: data.break_start,
        break_end: data.break_end,
        step_min: String(data.step_min),
        include_weekends: data.include_weekends ? '1' : '',
        use_break: data.use_break ? '1' : '',
      })
      const res = await fetch('/slots/bulk_create', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `Ошибка ${res.status}`)
      }
      return true
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['slots'] })
      const p = preview
      setSuccessMessage(`Создано ${p.total} слотов (${p.days} дней × ${p.perDay} слотов/день)`)
      showToast('Серия слотов создана', 'success')
      setTimeout(() => setSuccessMessage(null), 5000)
    },
    onError: (err: unknown) => {
      const message = (err as Error).message
      setServerError(message)
      showToast(message, 'error')
    }
  })

  const cityObj = cities.find((c) => String(c.id) === String(watch('city_id')))
  const samplePreview = useMemo(() => {
    if (!startDate || !startTime || !cityObj?.tz) return null
    const tzCity = cityObj.tz || 'Europe/Moscow'
    const tzRecruiter = recruiter?.tz || tzCity
    const utc = localToUtc(startDate, startTime, tzCity)
    if (!utc) return null
    return {
      tzCity,
      tzRecruiter,
      cityLabel: formatInTz(utc, tzCity),
      recruiterLabel: formatInTz(utc, tzRecruiter),
    }
  }, [startDate, startTime, cityObj?.tz, recruiter?.tz])

  return (
    <form onSubmit={handleSubmit((values) => mutation.mutate(values))} className="glass panel slot-create-form">
      <div className="slot-create-section">
        <h2 className="title title--sm">Серия слотов</h2>
        <p className="subtitle">Диапазон дат, окно времени и шаг.</p>
      </div>
      <div className="slot-create-grid">
        <input type="hidden" {...register('recruiter_id')} />
        <label className="form-group">
          <span className="form-group__label">Город</span>
          <select {...register('city_id')}>
            <option value="">— выберите —</option>
            {filteredCities.map((c) => (
              <option key={c.id} value={String(c.id)}>{c.name}</option>
            ))}
          </select>
          {errors.city_id && <span className="form-group__error">Укажите город</span>}
        </label>
      </div>
      <div className="slot-create-grid">
        <label className="form-group">
          <span className="form-group__label">Стартовая дата</span>
          <input type="date" {...register('start_date')} />
          {errors.start_date && <span className="form-group__error">{errors.start_date.message}</span>}
        </label>
        <label className="form-group">
          <span className="form-group__label">Конечная дата</span>
          <input type="date" {...register('end_date')} />
          {errors.end_date && <span className="form-group__error">{errors.end_date.message}</span>}
        </label>
      </div>
      <div className="slot-create-grid">
        <label className="form-group">
          <span className="form-group__label">Окно (с)</span>
          <input type="time" {...register('start_time')} />
          {errors.start_time && <span className="form-group__error">{errors.start_time.message}</span>}
        </label>
        <label className="form-group">
          <span className="form-group__label">Окно (до)</span>
          <input type="time" {...register('end_time')} />
          {errors.end_time && <span className="form-group__error">{errors.end_time.message}</span>}
        </label>
        <label className="form-group">
          <span className="form-group__label">Перерыв (с)</span>
          <input type="time" {...register('break_start')} />
          {errors.break_start && <span className="form-group__error">{errors.break_start.message}</span>}
        </label>
        <label className="form-group">
          <span className="form-group__label">Перерыв (до)</span>
          <input type="time" {...register('break_end')} />
          {errors.break_end && <span className="form-group__error">{errors.break_end.message}</span>}
        </label>
        <label className="form-group">
          <span className="form-group__label">Шаг (мин)</span>
          <input type="number" {...register('step_min')} />
          {errors.step_min && <span className="form-group__error">{errors.step_min.message}</span>}
        </label>
      </div>
      <div className="slot-create-switches">
        <label className="toggle-label">
          <input type="checkbox" {...register('include_weekends')} />
          Включать выходные
        </label>
        <label className="toggle-label">
          <input type="checkbox" {...register('use_break')} />
          Учитывать перерыв
        </label>
      </div>

      <div className="slot-preview glass glass--subtle">
        <div>
          <div className="slot-preview__label">Дней</div>
          <div className="slot-preview__value">{preview.days}</div>
          <div className="slot-preview__hint">Рабочие дни в диапазоне</div>
        </div>
        <div>
          <div className="slot-preview__label">Слотов/день</div>
          <div className="slot-preview__value">{preview.perDay}</div>
          <div className="slot-preview__hint">С учётом перерыва</div>
        </div>
        <div>
          <div className="slot-preview__label">Всего</div>
          <div className="slot-preview__value">{preview.total}</div>
          <div className="slot-preview__hint">Суммарно будет создано</div>
        </div>
      </div>

      <div className="slot-preview glass glass--subtle">
        <div>
          <div className="slot-preview__label">Пример времени</div>
          <div className="slot-preview__value">
            {samplePreview ? `${samplePreview.cityLabel} · ${samplePreview.tzCity}` : '—'}
          </div>
          <div className="slot-preview__hint">Время региона</div>
        </div>
        <div>
          <div className="slot-preview__label">Время рекрутёра</div>
          <div className="slot-preview__value">
            {samplePreview ? `${samplePreview.recruiterLabel} · ${samplePreview.tzRecruiter}` : '—'}
          </div>
          <div className="slot-preview__hint">Для первого слота</div>
        </div>
      </div>

      {preview.total > 100 && (
        <div className="form-warning">
          ⚠️ Будет создано много слотов ({preview.total}). Убедитесь, что параметры верны.
        </div>
      )}
      <div className="slot-create-actions">
        <button className="ui-btn ui-btn--primary" type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? 'Создаём…' : 'Создать серию'}
        </button>
        {serverError && <p className="text-danger text-sm">{serverError}</p>}
        {successMessage && (
          <div className="form-success">
            <p>{successMessage}</p>
          </div>
        )}
      </div>
      {toast && (
        <div className="toast" data-tone={toast.tone}>
          {toast.message}
        </div>
      )}
    </form>
  )
}

function computeBulkPreview(
  startDate?: string,
  endDate?: string,
  startTime?: string,
  endTime?: string,
  breakStart?: string,
  breakEnd?: string,
  step = 30,
  includeWeekends = false,
  useBreak = true
) {
  if (!startDate || !endDate || !startTime || !endTime) return { days: 0, perDay: 0, total: 0 }
  const d0 = new Date(startDate)
  const d1 = new Date(endDate)
  const a = d0 < d1 ? d0 : d1
  const b = d0 < d1 ? d1 : d0
  let days = 0
  const cur = new Date(a)
  while (cur <= b) {
    const w = cur.getDay()
    if (includeWeekends || (w >= 1 && w <= 5)) days++
    cur.setDate(cur.getDate() + 1)
  }
  const toMin = (t: string) => {
    const [h, m] = t.split(':').map(Number)
    return h * 60 + m
  }
  const s = toMin(startTime)
  const e = toMin(endTime)
  const steps = Math.max(0, Math.floor((e - s) / step))
  let perDay = steps
  if (useBreak && breakStart && breakEnd) {
    const bs = toMin(breakStart)
    const be = toMin(breakEnd)
    const before = Math.max(0, Math.floor((bs - s) / step))
    const after = Math.max(0, Math.floor((e - be) / step))
    perDay = before + after
  }
  return { days, perDay, total: days * perDay }
}

function formatInTz(date: Date, tz: string) {
  try {
    return new Intl.DateTimeFormat('ru-RU', {
      timeZone: tz,
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date)
  } catch {
    return date.toISOString()
  }
}

function getOffsetMinutes(date: Date, tz: string) {
  const dtf = new Intl.DateTimeFormat('en-US', {
    timeZone: tz,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
  const parts = dtf.formatToParts(date)
  const pick = (type: string) => Number(parts.find((p) => p.type === type)?.value || '0')
  const asUTC = Date.UTC(
    pick('year'),
    pick('month') - 1,
    pick('day'),
    pick('hour'),
    pick('minute'),
    pick('second')
  )
  return (asUTC - date.getTime()) / 60000
}

function localToUtc(date: string, time: string, tz: string) {
  if (!date || !time) return null
  const [y, m, d] = date.split('-').map(Number)
  const [hh, mm] = time.split(':').map(Number)
  if (!y || !m || !d) return null
  const utcGuess = new Date(Date.UTC(y, m - 1, d, hh, mm, 0))
  const offset = getOffsetMinutes(utcGuess, tz)
  return new Date(utcGuess.getTime() - offset * 60000)
}
