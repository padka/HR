import { useState } from 'react'
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
  const profile = useProfile()
  const canUse = profile.data?.principal.type === 'recruiter'

  const { data: recruiters } = useQuery<RecruiterPayload[]>({
    queryKey: ['recruiters'],
    queryFn: () => apiFetch('/recruiters'),
    enabled: Boolean(canUse),
  })

  const { data: cities } = useQuery<CityPayload[]>({
    queryKey: ['cities'],
    queryFn: () => apiFetch('/cities'),
    enabled: Boolean(canUse),
  })

  const { register, handleSubmit, formState: { errors }, watch } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { recruiter_id: '', city_id: '' },
  })

  const selectedRecruiter = watch('recruiter_id')

  const [successMessage, setSuccessMessage] = useState<string | null>(null)

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
        const text = await res.text()
        throw new Error(text || 'Ошибка создания')
      }
      return res.json()
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['slots'] })
      setSuccessMessage('Слот успешно создан')
      setTimeout(() => setSuccessMessage(null), 3000)
    },
    onError: (err: unknown) => {
      setServerError((err as Error).message)
    }
  })

  const onSubmit = handleSubmit((values) => mutation.mutate(values))

  const filteredCities = (cities || []).filter((c) => {
    if (!selectedRecruiter) return true
    const rec = (recruiters || []).find((r) => String(r.id) === String(selectedRecruiter))
    if (rec?.city_ids && rec.city_ids.length) {
      return rec.city_ids.includes(c.id)
    }
    return String(c.owner_recruiter_id || '') === String(selectedRecruiter)
  })

  return (
    <RoleGuard allow={['recruiter']}>
      <div className="page">
        <div className="glass panel" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px' }}>
          <h1 className="title" style={{ margin: 0 }}>Создание слотов</h1>
          <Link to="/app/slots" className="glass action-link">← К списку слотов</Link>
        </div>

        <form onSubmit={onSubmit} className="glass panel" style={{ display: 'grid', gap: 10 }}>
          <h2 className="title" style={{ fontSize: 18, marginBottom: 4 }}>Один слот</h2>
          <p className="subtitle" style={{ margin: 0 }}>Создайте единичный слот на конкретную дату и время.</p>
        <label style={{ display: 'grid', gap: 4 }}>
          Рекрутёр
          <select {...register('recruiter_id')}>
            <option value="">— выберите —</option>
            {(recruiters || []).map((r) => (
              <option key={r.id} value={String(r.id)}>{r.name}</option>
            ))}
          </select>
          {errors.recruiter_id && <span style={{ color: '#f07373' }}>{errors.recruiter_id.message}</span>}
        </label>
        <label style={{ display: 'grid', gap: 4 }}>
          Город
          <select {...register('city_id')}>
            <option value="">— выберите —</option>
            {filteredCities.map((c) => (
              <option key={c.id} value={String(c.id)}>{c.name}</option>
            ))}
          </select>
          {errors.city_id && <span style={{ color: '#f07373' }}>{errors.city_id.message}</span>}
        </label>
        <label style={{ display: 'grid', gap: 4 }}>
          Дата
          <input {...register('date')} type="date" />
          {errors.date && <span style={{ color: '#f07373' }}>{errors.date.message}</span>}
        </label>
        <label style={{ display: 'grid', gap: 4 }}>
          Время
          <input {...register('time')} type="time" />
          {errors.time && <span style={{ color: '#f07373' }}>{errors.time.message}</span>}
        </label>
          <button className="ui-btn ui-btn--primary" type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Создаём…' : 'Создать'}
          </button>
          {serverError && <p style={{ color: '#f07373', margin: 0 }}>{serverError}</p>}
          {successMessage && (
            <div style={{ background: 'rgba(100, 200, 100, 0.15)', border: '1px solid rgba(100, 200, 100, 0.3)', borderRadius: 8, padding: 12 }}>
              <p style={{ color: 'rgb(100, 200, 100)', margin: 0 }}>{successMessage}</p>
            </div>
          )}
        </form>
        <BulkCreateForm recruiters={recruiters || []} cities={cities || []} />
      </div>
    </RoleGuard>
  )
}

function BulkCreateForm({ recruiters, cities }: { recruiters: RecruiterPayload[]; cities: CityPayload[] }) {
  const qc = useQueryClient()
  const [serverError, setServerError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const { register, handleSubmit, watch, formState: { errors } } = useForm<z.infer<typeof bulkSchema>>({
    resolver: zodResolver(bulkSchema),
    defaultValues: {
      include_weekends: false,
      use_break: true,
      start_time: '10:00',
      end_time: '16:00',
      break_start: '12:00',
      break_end: '13:00',
      step_min: 30,
    }
  })

  const selectedRecruiter = watch('recruiter_id')
  const startDate = watch('start_date')
  const endDate = watch('end_date')
  const includeWeekends = watch('include_weekends')
  const startTime = watch('start_time')
  const endTime = watch('end_time')
  const breakStart = watch('break_start')
  const breakEnd = watch('break_end')
  const stepMin = Number(watch('step_min') || 30)
  const useBreak = watch('use_break')

  const filteredCities = cities.filter((c) => {
    if (!selectedRecruiter) return true
    const rec = recruiters.find((r) => String(r.id) === String(selectedRecruiter))
    if (rec?.city_ids && rec.city_ids.length) {
      return rec.city_ids.includes(c.id)
    }
    return String(c.owner_recruiter_id || '') === String(selectedRecruiter)
  })

  const preview = computeBulkPreview(startDate, endDate, startTime, endTime, breakStart, breakEnd, stepMin, includeWeekends, useBreak)

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
        throw new Error(text || 'Ошибка bulk')
      }
      return true
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['slots'] })
      const p = preview
      setSuccessMessage(`Создано ${p.total} слотов (${p.days} дней × ${p.perDay} слотов/день)`)
      setTimeout(() => setSuccessMessage(null), 5000)
    },
    onError: (err: unknown) => {
      setServerError((err as Error).message)
    }
  })

  return (
    <form onSubmit={handleSubmit((values) => mutation.mutate(values))} className="glass panel" style={{ display: 'grid', gap: 10 }}>
      <h2 className="title" style={{ fontSize: 18, marginBottom: 4 }}>Серия слотов (Bulk)</h2>
      <p className="subtitle" style={{ margin: 0 }}>Создайте множество слотов на диапазон дат с заданным интервалом.</p>
      <label style={{ display: 'grid', gap: 4 }}>
        Рекрутёр
        <select {...register('recruiter_id')}>
          <option value="">— выберите —</option>
          {recruiters.map((r) => (
            <option key={r.id} value={String(r.id)}>{r.name}</option>
          ))}
        </select>
        {errors.recruiter_id && <span style={{ color: '#f07373' }}>Укажите рекрутёра</span>}
      </label>
      <label style={{ display: 'grid', gap: 4 }}>
        Город
        <select {...register('city_id')}>
          <option value="">— выберите —</option>
          {filteredCities.map((c) => (
            <option key={c.id} value={String(c.id)}>{c.name}</option>
          ))}
        </select>
        {errors.city_id && <span style={{ color: '#f07373' }}>Укажите город</span>}
      </label>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8 }}>
        <label style={{ display: 'grid', gap: 4 }}>
          Стартовая дата
          <input type="date" {...register('start_date')} />
          {errors.start_date && <span style={{ color: '#f07373' }}>{errors.start_date.message}</span>}
        </label>
        <label style={{ display: 'grid', gap: 4 }}>
          Конечная дата
          <input type="date" {...register('end_date')} />
          {errors.end_date && <span style={{ color: '#f07373' }}>{errors.end_date.message}</span>}
        </label>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8 }}>
        <label style={{ display: 'grid', gap: 4 }}>
          Окно (с)
          <input type="time" {...register('start_time')} />
          {errors.start_time && <span style={{ color: '#f07373' }}>{errors.start_time.message}</span>}
        </label>
        <label style={{ display: 'grid', gap: 4 }}>
          Окно (до)
          <input type="time" {...register('end_time')} />
          {errors.end_time && <span style={{ color: '#f07373' }}>{errors.end_time.message}</span>}
        </label>
        <label style={{ display: 'grid', gap: 4 }}>
          Перерыв (с)
          <input type="time" {...register('break_start')} />
          {errors.break_start && <span style={{ color: '#f07373' }}>{errors.break_start.message}</span>}
        </label>
        <label style={{ display: 'grid', gap: 4 }}>
          Перерыв (до)
          <input type="time" {...register('break_end')} />
          {errors.break_end && <span style={{ color: '#f07373' }}>{errors.break_end.message}</span>}
        </label>
        <label style={{ display: 'grid', gap: 4 }}>
          Шаг (мин)
          <input type="number" {...register('step_min')} />
          {errors.step_min && <span style={{ color: '#f07373' }}>{errors.step_min.message}</span>}
        </label>
      </div>
      <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <input type="checkbox" {...register('include_weekends')} />
        Включать выходные
      </label>
      <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <input type="checkbox" {...register('use_break')} />
        Учитывать перерыв
      </label>
      {/* Preview section */}
      <div className="glass" style={{ padding: 12, display: 'grid', gap: 8, gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))' }}>
        <div style={{ textAlign: 'center' }}>
          <div className="subtitle" style={{ fontSize: 11 }}>Дней</div>
          <div style={{ fontSize: 24, fontWeight: 600, color: preview.days > 0 ? 'var(--accent)' : 'var(--muted)' }}>{preview.days}</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div className="subtitle" style={{ fontSize: 11 }}>Слотов/день</div>
          <div style={{ fontSize: 24, fontWeight: 600, color: preview.perDay > 0 ? 'var(--accent)' : 'var(--muted)' }}>{preview.perDay}</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div className="subtitle" style={{ fontSize: 11 }}>Всего слотов</div>
          <div style={{ fontSize: 24, fontWeight: 600, color: preview.total > 0 ? 'rgb(100, 200, 100)' : 'var(--muted)' }}>{preview.total}</div>
        </div>
      </div>
      {preview.total > 100 && (
        <div style={{ background: 'rgba(255, 200, 100, 0.15)', border: '1px solid rgba(255, 200, 100, 0.3)', borderRadius: 8, padding: 10, fontSize: 13 }}>
          ⚠️ Будет создано много слотов ({preview.total}). Убедитесь, что параметры верны.
        </div>
      )}
      <button className="ui-btn ui-btn--primary" type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? 'Создаём…' : 'Создать серию'}
      </button>
      {serverError && <p style={{ color: '#f07373', margin: 0 }}>{serverError}</p>}
      {successMessage && (
        <div style={{ background: 'rgba(100, 200, 100, 0.15)', border: '1px solid rgba(100, 200, 100, 0.3)', borderRadius: 8, padding: 12 }}>
          <p style={{ color: 'rgb(100, 200, 100)', margin: 0 }}>{successMessage}</p>
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
