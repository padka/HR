import { useState } from 'react'
import { useProfile } from '@/app/hooks/useProfile'
import { useMutation, useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'

type BotIntegrationResponse = {
  config_enabled: boolean
  runtime_enabled: boolean
  updated_at: string | null
  service_health: string
  service_ready: boolean
}

export function ProfilePage() {
  const { data, isLoading, isError, error, refetch, isFetching } = useProfile()
  const isAdmin = data?.principal.type === 'admin'
  const snapshot = data?.profile
  const botQuery = useQuery<BotIntegrationResponse>({
    queryKey: ['botIntegration'],
    queryFn: () => apiFetch<BotIntegrationResponse>('/bot/integration'),
    enabled: Boolean(isAdmin),
    staleTime: 20_000,
  })

  if (isLoading) {
    return (
      <div className="glass panel">
        <h1 className="title">Профиль</h1>
        <p className="subtitle">Загрузка профиля…</p>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="glass panel">
        <h1 className="title">Профиль</h1>
        <p className="subtitle">Ошибка загрузки: {(error as Error).message}</p>
        <button className="ui-btn ui-btn--ghost" onClick={() => refetch()} style={{ marginTop: 12 }}>Повторить</button>
      </div>
    )
  }

  const principal = data?.principal
  const recruiter = data?.recruiter
  const stats = data?.stats
  const roleLabel = principal?.type === 'admin' ? 'Администратор' : 'Рекрутер'
  const displayName = recruiter?.name || (principal?.type === 'admin' ? 'Admin' : 'Пользователь')
  const adminHealth = snapshot?.admin_stats?.health || {}
  const slotsByStatus = snapshot?.admin_stats?.slots_by_status || {}

  const formatSlotTime = (value?: string | null) => {
    if (!value) return '—'
    try {
      const dt = new Date(value)
      const tz = recruiter?.tz || 'Europe/Moscow'
      return new Intl.DateTimeFormat('ru-RU', {
        timeZone: tz,
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      }).format(dt)
    } catch {
      return value
    }
  }

  return (
    <div className="page">
      <section className="glass panel" style={{ display: 'grid', gap: 12 }}>
        <div>
          <h1 className="title">Личный кабинет</h1>
          <p className="subtitle">
            Роль: {roleLabel} · ID: {principal?.id ?? '—'}
            {isFetching ? ' · обновление…' : ''}
          </p>
        </div>

        {isAdmin ? (
          <>
            <p className="subtitle">Контроль команды, слотов и инфраструктуры в одном месте.</p>
            <div className="grid-cards">
              <SummaryCard label="Кандидаты" value={snapshot?.candidate_count ?? 0} />
              <SummaryCard label="Слоты" value={snapshot?.slot_count ?? 0} />
              <SummaryCard label="Рекрутёры" value={snapshot?.recruiter_count ?? 0} />
              <SummaryCard label="Города" value={snapshot?.city_count ?? 0} />
              <SummaryCard label="Свободно" value={slotsByStatus.free ?? 0} />
              <SummaryCard label="Pending" value={slotsByStatus.pending ?? 0} />
              <SummaryCard label="Подтверждено" value={(slotsByStatus.booked ?? 0) + (slotsByStatus.confirmed ?? 0)} />
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              <span className="chip">DB: {adminHealth.db === false ? 'Down' : 'OK'}</span>
              <span className="chip">Redis: {String(adminHealth.redis ?? '—')}</span>
              <span className="chip">Cache: {String(adminHealth.cache ?? '—')}</span>
              <span className="chip">Bot: {adminHealth.bot ? 'ON' : 'OFF'}</span>
            </div>
          </>
        ) : (
          <>
            <div className="grid-cards">
              <SummaryCard label="Статус" value={recruiter?.active ? 'Активен' : 'Неактивен'} />
              <SummaryCard label="Часовой пояс" value={recruiter?.tz || '—'} />
              <SummaryCard label="Кандидаты" value={snapshot?.candidate_count ?? 0} />
              <SummaryCard label="Слоты" value={snapshot?.slot_count ?? 0} />
              <SummaryCard label="Сегодня" value={snapshot?.kpi?.today ?? 0} />
              <SummaryCard label="Предстоящие" value={snapshot?.kpi?.upcoming ?? 0} />
              <SummaryCard label="Pending" value={snapshot?.kpi?.pending ?? 0} />
              <SummaryCard label="Конверсия" value={`${snapshot?.kpi?.conversion ?? 0}%`} />
              <SummaryCard label="Ближайшая" value={snapshot?.kpi?.nearest_minutes ? `${Math.floor((snapshot.kpi.nearest_minutes || 0) / 60)}ч ${(snapshot.kpi.nearest_minutes || 0) % 60}м` : '—'} />
              <SummaryCard label="Средн. lead" value={snapshot?.kpi?.avg_lead_hours ? `${snapshot.kpi.avg_lead_hours} ч` : '—'} />
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {(snapshot?.city_names || []).length > 0 ? (
                snapshot?.city_names?.map((name) => (
                  <span key={name} className="chip">{name}</span>
                ))
              ) : (
                <span className="subtitle">Города не назначены</span>
              )}
            </div>
          </>
        )}

        <div className="action-row">
          {principal?.type === 'recruiter' && (
            <a href="/app/slots" className="glass action-link">
              Мои слоты
            </a>
          )}
          <a href="/app/candidates" className="glass action-link">
            Кандидаты
          </a>
          {principal?.type === 'admin' && (
            <>
              <a href="/app/recruiters" className="glass action-link">
                Управление рекрутерами
              </a>
              <a href="/app/templates" className="glass action-link">
                Шаблоны
              </a>
              <a href="/app/questions" className="glass action-link">
                Вопросы
              </a>
            </>
          )}
        </div>
      </section>

      <section className="glass panel">
        <h2 className="title">Сводка</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
          <SummaryCard label="Рекрутеры" value={stats?.recruiters ?? 0} />
          <SummaryCard label="Города" value={stats?.cities ?? 0} />
          <SummaryCard label="Слоты всего" value={stats?.slots_total ?? 0} />
          <SummaryCard label="Свободные" value={stats?.slots_free ?? 0} />
          <SummaryCard label="Ожидают" value={stats?.slots_pending ?? 0} />
          <SummaryCard label="Забронированы" value={stats?.slots_booked ?? 0} />
          <SummaryCard label="Тест 1 seen" value={stats?.test1_total_seen ?? 0} />
        </div>
      </section>

      {isAdmin && (
        <section className="glass panel" style={{ display: 'grid', gap: 16 }}>
          <div>
            <h2 className="title">Система и интеграции</h2>
            <p className="subtitle">
              Состояние ключевых сервисов и интеграций для контроля администратора.
            </p>
          </div>
          <div className="grid-cards">
            <div className="glass stat-card">
              <div className="stat-label">Интеграция с ботом</div>
              {botQuery.isLoading && <div className="subtitle" style={{ marginTop: 8 }}>Загрузка…</div>}
              {botQuery.isError && (
                <div className="subtitle" style={{ marginTop: 8 }}>
                  Не удалось загрузить статус
                </div>
              )}
              {botQuery.data && (
                <div style={{ marginTop: 8, display: 'grid', gap: 8 }}>
                  <StatusPill label="Конфигурация" active={botQuery.data.config_enabled} />
                  <StatusPill label="Runtime" active={botQuery.data.runtime_enabled} />
                  <StatusPill label="Готовность" active={botQuery.data.service_ready} />
                  <div className="stat-label">
                    Health: {botQuery.data.service_health}
                  </div>
                </div>
              )}
            </div>
            <div className="glass stat-card">
              <div className="stat-label">Управление доступом</div>
              <div style={{ marginTop: 8, display: 'grid', gap: 6 }}>
                <a href="/app/recruiters" className="action-link" style={{ padding: 0 }}>Настройка рекрутеров →</a>
                <a href="/app/cities" className="action-link" style={{ padding: 0 }}>Список городов →</a>
                <a href="/app/templates" className="action-link" style={{ padding: 0 }}>Шаблоны →</a>
                <a href="/app/questions" className="action-link" style={{ padding: 0 }}>Вопросы →</a>
              </div>
            </div>
            <div className="glass stat-card">
              <div className="stat-label">Показатели отдела</div>
              <div className="stat-value" style={{ marginTop: 8 }}>{stats?.slots_total ?? 0} слотов</div>
              <div className="stat-label" style={{ marginTop: 4 }}>
                Ожидают: {stats?.slots_pending ?? 0} · Бронь: {stats?.slots_booked ?? 0}
              </div>
              <div style={{ marginTop: 10 }}>
                <a href="/app/dashboard" className="action-link" style={{ padding: 0 }}>Открыть дашборд →</a>
              </div>
            </div>
          </div>
        </section>
      )}

      {!isAdmin && (
        <section className="glass panel" style={{ display: 'grid', gap: 16 }}>
          <div>
            <h2 className="title">Сегодня</h2>
            <p className="subtitle">Ближайшие встречи и статус по слотам.</p>
          </div>
          <div className="grid-cards">
            <div className="glass stat-card">
              <div className="stat-label">Встречи сегодня</div>
              <div className="stat-value">{snapshot?.today_meetings?.length ?? 0}</div>
              <div style={{ marginTop: 8, display: 'grid', gap: 6 }}>
                {(snapshot?.today_meetings || []).slice(0, 4).map((m) => (
                  <div key={m.id} className="action-row" style={{ justifyContent: 'space-between' }}>
                    <span className="subtitle">{formatSlotTime(m.start_utc)}</span>
                    <a href={`/app/slots?slot_id=${m.id}`} className="action-link">Открыть →</a>
                  </div>
                ))}
                {(snapshot?.today_meetings || []).length === 0 && <span className="subtitle">Нет встреч.</span>}
              </div>
            </div>
            <div className="glass stat-card">
              <div className="stat-label">Предстоящие</div>
              <div className="stat-value">{snapshot?.upcoming_meetings?.length ?? 0}</div>
              <div style={{ marginTop: 8, display: 'grid', gap: 6 }}>
                {(snapshot?.upcoming_meetings || []).slice(0, 4).map((m) => (
                  <div key={m.id} className="action-row" style={{ justifyContent: 'space-between' }}>
                    <span className="subtitle">{formatSlotTime(m.start_utc)}</span>
                    <a href={`/app/slots?slot_id=${m.id}`} className="action-link">Подробнее →</a>
                  </div>
                ))}
                {(snapshot?.upcoming_meetings || []).length === 0 && <span className="subtitle">Нет встреч.</span>}
              </div>
            </div>
          </div>
        </section>
      )}

      {!isAdmin && (
        <section className="glass panel" style={{ display: 'grid', gap: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h2 className="title">Кандидаты в работе</h2>
              <p className="subtitle">Последние активные кандидаты.</p>
            </div>
            <a href="/app/candidates" className="action-link">Открыть список →</a>
          </div>
          <div style={{ display: 'grid', gap: 8 }}>
            {(snapshot?.active_candidates || []).map((c) => (
              <div key={c.id} className="glass" style={{ padding: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <strong>{c.name}</strong>
                  <div className="subtitle">{c.city || 'Город не задан'}</div>
                </div>
                <a href={`/app/candidates/${c.id}`} className="action-link">Открыть →</a>
              </div>
            ))}
            {(snapshot?.active_candidates || []).length === 0 && <p className="subtitle">Нет активных кандидатов.</p>}
          </div>
        </section>
      )}

      {!isAdmin && (
        <section className="glass panel" style={{ display: 'grid', gap: 16 }}>
          <div>
            <h2 className="title">Планировщик</h2>
            <p className="subtitle">Создайте слот и следите за расписанием недели.</p>
          </div>
          <PlannerForm
            recruiterId={principal?.id}
            cities={snapshot?.city_options || []}
            onSuccess={() => refetch()}
          />
          <div style={{ display: 'grid', gap: 8 }}>
            {(snapshot?.planner_days || []).map((day) => (
              <div key={day.date} className="glass" style={{ padding: 10 }}>
                <strong>{day.date}</strong>
                <div style={{ marginTop: 6, display: 'grid', gap: 6 }}>
                  {day.entries.map((entry) => (
                    <div key={entry.id} className="action-row" style={{ justifyContent: 'space-between' }}>
                      <span className="subtitle">{entry.time || '—'} · {entry.status}</span>
                      <a href={`/app/slots?slot_id=${entry.id}`} className="action-link">→</a>
                    </div>
                  ))}
                </div>
              </div>
            ))}
            {(snapshot?.planner_days || []).length === 0 && <p className="subtitle">Слотов на неделю нет.</p>}
          </div>
        </section>
      )}

      {!isAdmin && (
        <section className="glass panel" style={{ display: 'grid', gap: 12 }}>
          <div>
            <h2 className="title">Напоминания</h2>
            <p className="subtitle">Контрольные точки по бронированиям и очередям.</p>
          </div>
          <div style={{ display: 'grid', gap: 8 }}>
            {(snapshot?.reminders || []).map((r, idx) => (
              <div key={`${r.title}-${idx}`} className="glass" style={{ padding: 10 }}>
                <div style={{ fontWeight: 600 }}>{r.title}</div>
                {r.when && <div className="subtitle">{r.when}</div>}
              </div>
            ))}
            {(snapshot?.reminders || []).length === 0 && <p className="subtitle">Напоминаний нет.</p>}
          </div>
        </section>
      )}

      <section className="glass panel" style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
        <div style={{ flex: '1 1 240px' }}>
          <h3 className="title" style={{ fontSize: 20 }}>Действия</h3>
          <p className="subtitle">
            Для переключения аккаунта используйте выход и войдите снова под нужной ролью.
          </p>
        </div>
        <form method="post" action="/auth/logout">
          <button type="submit" className="ui-btn ui-btn--ghost">Выйти из системы</button>
        </form>
      </section>
    </div>
  )
}

function SummaryCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="glass stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  )
}

function StatusPill({ label, active }: { label: string; active: boolean }) {
  return (
    <div
      className="status-pill"
      style={{
        background: active ? 'rgba(106,165,255,0.18)' : 'rgba(255,255,255,0.08)',
        color: active ? '#d7e6ff' : 'var(--muted)',
      }}
    >
      <span
        className="status-pill__dot"
        style={{
          background: active ? '#6aa5ff' : 'rgba(255,255,255,0.35)',
        }}
      />
      {label}
    </div>
  )
}

function PlannerForm({
  recruiterId,
  cities,
  onSuccess,
}: {
  recruiterId?: number
  cities: Array<{ id: number; name: string; tz?: string | null }>
  onSuccess: () => void
}) {
  const [form, setForm] = useState({ city_id: '', date: '', time: '', duration: 45 })
  const [message, setMessage] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: async () => {
      if (!recruiterId) throw new Error('Неизвестен рекрутёр')
      if (!form.city_id || !form.date || !form.time) {
        throw new Error('Заполните город, дату и время')
      }
      const payload = {
        recruiter_id: recruiterId,
        region_id: Number(form.city_id),
        starts_at_local: `${form.date}T${form.time}`,
        duration_min: Number(form.duration || 45),
      }
      return apiFetch('/slots', { method: 'POST', body: JSON.stringify(payload) })
    },
    onSuccess: () => {
      setMessage('Слот создан. Обновляем…')
      onSuccess()
    },
    onError: (err: unknown) => {
      setMessage((err as Error).message)
    },
  })

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        setMessage(null)
        mutation.mutate()
      }}
      className="glass panel--tight"
      style={{ display: 'grid', gap: 10 }}
    >
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 8 }}>
        <label style={{ display: 'grid', gap: 4 }}>
          Город
          <select value={form.city_id} onChange={(e) => setForm({ ...form, city_id: e.target.value })}>
            <option value="">Выберите город</option>
            {cities.map((city) => (
              <option key={city.id} value={String(city.id)}>{city.name}</option>
            ))}
          </select>
        </label>
        <label style={{ display: 'grid', gap: 4 }}>
          Дата
          <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
        </label>
        <label style={{ display: 'grid', gap: 4 }}>
          Время
          <input type="time" value={form.time} onChange={(e) => setForm({ ...form, time: e.target.value })} />
        </label>
        <label style={{ display: 'grid', gap: 4 }}>
          Длительность (мин)
          <input
            type="number"
            min={15}
            max={180}
            step={5}
            value={form.duration}
            onChange={(e) => setForm({ ...form, duration: Number(e.target.value) })}
          />
        </label>
      </div>
      <button className="ui-btn ui-btn--primary" type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? 'Создаём…' : 'Создать слот'}
      </button>
      {message && <p className="subtitle">{message}</p>}
    </form>
  )
}
