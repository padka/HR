import { useMutation, useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { apiFetch } from '@/api/client'
import { RoleGuard } from '@/app/components/RoleGuard'

type HealthPayload = {
  recruiters: number
  cities: number
  slots_total: number
  slots_free: number
  slots_pending: number
  slots_booked: number
  waiting_candidates_total: number
  test1_rejections_total: number
  test1_total_seen: number
  test1_rejections_percent: number
}

type BotStatus = {
  config_enabled: boolean
  runtime_enabled: boolean
  updated_at: string | null
  switch_source: 'operator' | 'runtime'
  switch_reason: string | null
  service_health: string
  service_ready: boolean
}

type ReminderKindConfig = {
  enabled: boolean
  offset_hours: number
}

type ReminderPolicy = {
  interview: {
    confirm_6h: ReminderKindConfig
    confirm_3h: ReminderKindConfig
    confirm_2h: ReminderKindConfig
  }
  intro_day: {
    intro_remind_3h: ReminderKindConfig
  }
  min_time_before_immediate_hours: number
}

type ReminderPolicyPayload = {
  policy: ReminderPolicy
  updated_at: string | null
  links: {
    questions: string
    message_templates: string
    templates: string
  }
}

type ReminderPolicyUpdatePayload = {
  ok: boolean
  policy: ReminderPolicy
  updated_at: string
  rescheduled_slots: number
  reschedule_failed: number
}

type OutboxItem = {
  id: number
  type: string
  status: string
  attempts: number
  created_at: string | null
  locked_at: string | null
  next_retry_at: string | null
  last_error: string | null
  booking_id: number | null
  candidate_tg_id: number | null
  recruiter_tg_id: number | null
  correlation_id: string | null
}

type OutboxFeedPayload = {
  items: OutboxItem[]
  latest_id: number
  degraded: boolean
}

export function SystemPage() {
  const healthQuery = useQuery<HealthPayload>({
    queryKey: ['system-health'],
    queryFn: () => apiFetch('/health'),
  })

  const botQuery = useQuery<BotStatus>({
    queryKey: ['system-bot'],
    queryFn: () => apiFetch('/bot/integration'),
  })

  const reminderPolicyQuery = useQuery<ReminderPolicyPayload>({
    queryKey: ['system-bot-reminder-policy'],
    queryFn: () => apiFetch('/bot/reminder-policy'),
  })

  const [outboxStatusFilter, setOutboxStatusFilter] = useState<string>('')
  const [outboxTypeFilter, setOutboxTypeFilter] = useState<string>('')

  const outboxQuery = useQuery<OutboxFeedPayload>({
    queryKey: ['system-outbox-feed', outboxStatusFilter, outboxTypeFilter],
    queryFn: () => {
      const params = new URLSearchParams()
      params.set('after_id', '0')
      params.set('limit', '50')
      if (outboxStatusFilter) params.set('status', outboxStatusFilter)
      if (outboxTypeFilter.trim()) params.set('type', outboxTypeFilter.trim())
      return apiFetch(`/notifications/feed?${params.toString()}`)
    },
    refetchInterval: 10_000,
  })

  const retryOutboxMutation = useMutation({
    mutationFn: async (id: number) => apiFetch(`/notifications/${id}/retry`, { method: 'POST' }),
    onSuccess: () => outboxQuery.refetch(),
  })

  const cancelOutboxMutation = useMutation({
    mutationFn: async (id: number) => apiFetch(`/notifications/${id}/cancel`, { method: 'POST' }),
    onSuccess: () => outboxQuery.refetch(),
  })

  const [refreshingCities, setRefreshingCities] = useState(false)
  const [refreshResult, setRefreshResult] = useState<string | null>(null)
  const [policyDraft, setPolicyDraft] = useState<ReminderPolicy | null>(null)
  const [savingPolicy, setSavingPolicy] = useState(false)
  const [policyResult, setPolicyResult] = useState<string | null>(null)

  useEffect(() => {
    if (reminderPolicyQuery.data?.policy) {
      setPolicyDraft(reminderPolicyQuery.data.policy)
    }
  }, [reminderPolicyQuery.data])

  const refreshBotCities = async () => {
    setRefreshingCities(true)
    setRefreshResult(null)
    try {
      await apiFetch('/bot/cities/refresh', { method: 'POST' })
      setRefreshResult('Города обновлены.')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Ошибка обновления городов.'
      setRefreshResult(message || 'Ошибка обновления городов.')
    } finally {
      setRefreshingCities(false)
    }
  }

  const updateInterviewPolicy = (
    kind: keyof ReminderPolicy['interview'],
    key: keyof ReminderKindConfig,
    value: boolean | number,
  ) => {
    setPolicyDraft((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        interview: {
          ...prev.interview,
          [kind]: {
            ...prev.interview[kind],
            [key]: value,
          },
        },
      }
    })
  }

  const updateIntroPolicy = (
    key: keyof ReminderKindConfig,
    value: boolean | number,
  ) => {
    setPolicyDraft((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        intro_day: {
          ...prev.intro_day,
          intro_remind_3h: {
            ...prev.intro_day.intro_remind_3h,
            [key]: value,
          },
        },
      }
    })
  }

  const saveReminderPolicy = async () => {
    if (!policyDraft) return
    setSavingPolicy(true)
    setPolicyResult(null)
    try {
      const payload = await apiFetch<ReminderPolicyUpdatePayload>('/bot/reminder-policy', {
        method: 'PUT',
        body: JSON.stringify({ policy: policyDraft }),
      })
      setPolicyDraft(payload.policy)
      setPolicyResult(
        `Сохранено. Пересобрано слотов: ${payload.rescheduled_slots}, ошибок: ${payload.reschedule_failed}.`,
      )
      await reminderPolicyQuery.refetch()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Ошибка сохранения политики.'
      setPolicyResult(message || 'Ошибка сохранения политики.')
    } finally {
      setSavingPolicy(false)
    }
  }

  return (
    <RoleGuard allow={['admin']}>
      <div className="page">
        <header className="glass glass--elevated page-header">
          <h1 className="title">Система</h1>
          <p className="subtitle">Состояние ключевых сервисов и оперативная статистика.</p>
        </header>

        <section className="glass page-section">
          <h2 className="section-title">Health snapshot</h2>
          {healthQuery.isLoading && <p className="subtitle">Загрузка…</p>}
          {healthQuery.isError && <p className="text-danger">Ошибка: {(healthQuery.error as Error).message}</p>}
          {healthQuery.data && (
            <div className="data-grid">
              <article className="glass glass--interactive data-card">
                <div className="data-card__label">Рекрутёры</div>
                <div className="data-card__value">{healthQuery.data.recruiters}</div>
              </article>
              <article className="glass glass--interactive data-card">
                <div className="data-card__label">Города</div>
                <div className="data-card__value">{healthQuery.data.cities}</div>
              </article>
              <article className="glass glass--interactive data-card">
                <div className="data-card__label">Слоты</div>
                <div className="data-card__value">{healthQuery.data.slots_total}</div>
              </article>
              <article className="glass glass--interactive data-card">
                <div className="data-card__label">Ожидают</div>
                <div className="data-card__value">{healthQuery.data.slots_pending}</div>
              </article>
              <article className="glass glass--interactive data-card">
                <div className="data-card__label">Бронь</div>
                <div className="data-card__value">{healthQuery.data.slots_booked}</div>
              </article>
              <article className="glass glass--interactive data-card">
                <div className="data-card__label">Ждут слот</div>
                <div className="data-card__value">{healthQuery.data.waiting_candidates_total}</div>
              </article>
            </div>
          )}
        </section>

        <section className="glass page-section">
          <h2 className="section-title">Бот и интеграции</h2>
          {botQuery.isLoading && <p className="subtitle">Загрузка…</p>}
          {botQuery.isError && <p className="text-danger">Ошибка: {(botQuery.error as Error).message}</p>}
          {botQuery.data && (
            <div className="data-grid">
              <article className="glass glass--interactive data-card">
                <div className="data-card__label">Config enabled</div>
                <div className="data-card__value">{botQuery.data.config_enabled ? 'Да' : 'Нет'}</div>
              </article>
              <article className="glass glass--interactive data-card">
                <div className="data-card__label">Runtime enabled</div>
                <div className="data-card__value">{botQuery.data.runtime_enabled ? 'Да' : 'Нет'}</div>
              </article>
              <article className="glass glass--interactive data-card">
                <div className="data-card__label">Switch source</div>
                <div className="data-card__value">{botQuery.data.switch_source}</div>
              </article>
              <article className="glass glass--interactive data-card">
                <div className="data-card__label">Switch reason</div>
                <div className="data-card__value">{botQuery.data.switch_reason || '-'}</div>
              </article>
              <article className="glass glass--interactive data-card">
                <div className="data-card__label">Health</div>
                <div className="data-card__value">{botQuery.data.service_health}</div>
              </article>
              <article className="glass glass--interactive data-card">
                <div className="data-card__label">Ready</div>
                <div className="data-card__value">{botQuery.data.service_ready ? 'Да' : 'Нет'}</div>
              </article>
              <article className="glass glass--interactive data-card">
                <div className="data-card__label">Города в боте</div>
                <div className="data-card__value">
                  <button
                    className="ui-btn ui-btn--primary ui-btn--sm"
                    onClick={refreshBotCities}
                    disabled={refreshingCities}
                  >
                    {refreshingCities ? 'Обновляем…' : 'Обновить кэш'}
                  </button>
                  {refreshResult && <div className="subtitle">{refreshResult}</div>}
                </div>
              </article>
            </div>
          )}
        </section>

        <section className="glass page-section">
          <h2 className="section-title">Контент бота</h2>
          <p className="subtitle">Единая точка управления вопросами, шаблонами и политикой напоминаний.</p>
          <div className="data-grid" style={{ marginBottom: 16 }}>
            <article className="glass glass--interactive data-card">
              <div className="data-card__label">Вопросы тестов</div>
              <div className="data-card__value">
                <Link to="/app/questions" className="ui-btn ui-btn--ghost ui-btn--sm">Открыть</Link>
              </div>
            </article>
            <article className="glass glass--interactive data-card">
              <div className="data-card__label">Шаблоны сообщений</div>
              <div className="data-card__value">
                <Link to="/app/message-templates" className="ui-btn ui-btn--ghost ui-btn--sm">Открыть</Link>
              </div>
            </article>
            <article className="glass glass--interactive data-card">
              <div className="data-card__label">Системные шаблоны</div>
              <div className="data-card__value">
                <Link to="/app/templates" className="ui-btn ui-btn--ghost ui-btn--sm">Открыть</Link>
              </div>
            </article>
          </div>

          {reminderPolicyQuery.isLoading && <p className="subtitle">Загрузка политики напоминаний…</p>}
          {reminderPolicyQuery.isError && (
            <p className="text-danger">Ошибка: {(reminderPolicyQuery.error as Error).message}</p>
          )}

          {policyDraft && (
            <div className="glass panel--tight" style={{ padding: 16 }}>
              <h3 className="section-title" style={{ marginTop: 0 }}>Политика напоминаний</h3>
              <div className="form-row">
                <label className="form-group">
                  <span className="form-group__label">
                    <input
                      type="checkbox"
                      checked={policyDraft.interview.confirm_6h.enabled}
                      onChange={(e) => updateInterviewPolicy('confirm_6h', 'enabled', e.target.checked)}
                    />{' '}
                    Confirm за 6ч
                  </span>
                  <input
                    type="number"
                    min={0.25}
                    max={72}
                    step={0.25}
                    value={policyDraft.interview.confirm_6h.offset_hours}
                    onChange={(e) =>
                      updateInterviewPolicy('confirm_6h', 'offset_hours', Number(e.target.value) || 0.25)
                    }
                  />
                </label>
                <label className="form-group">
                  <span className="form-group__label">
                    <input
                      type="checkbox"
                      checked={policyDraft.interview.confirm_3h.enabled}
                      onChange={(e) => updateInterviewPolicy('confirm_3h', 'enabled', e.target.checked)}
                    />{' '}
                    Confirm за 3ч
                  </span>
                  <input
                    type="number"
                    min={0.25}
                    max={72}
                    step={0.25}
                    value={policyDraft.interview.confirm_3h.offset_hours}
                    onChange={(e) =>
                      updateInterviewPolicy('confirm_3h', 'offset_hours', Number(e.target.value) || 0.25)
                    }
                  />
                </label>
                <label className="form-group">
                  <span className="form-group__label">
                    <input
                      type="checkbox"
                      checked={policyDraft.interview.confirm_2h.enabled}
                      onChange={(e) => updateInterviewPolicy('confirm_2h', 'enabled', e.target.checked)}
                    />{' '}
                    Confirm за 2ч
                  </span>
                  <input
                    type="number"
                    min={0.25}
                    max={72}
                    step={0.25}
                    value={policyDraft.interview.confirm_2h.offset_hours}
                    onChange={(e) =>
                      updateInterviewPolicy('confirm_2h', 'offset_hours', Number(e.target.value) || 0.25)
                    }
                  />
                </label>
              </div>

              <div className="form-row">
                <label className="form-group">
                  <span className="form-group__label">
                    <input
                      type="checkbox"
                      checked={policyDraft.intro_day.intro_remind_3h.enabled}
                      onChange={(e) => updateIntroPolicy('enabled', e.target.checked)}
                    />{' '}
                    Intro Day за 3ч
                  </span>
                  <input
                    type="number"
                    min={0.25}
                    max={72}
                    step={0.25}
                    value={policyDraft.intro_day.intro_remind_3h.offset_hours}
                    onChange={(e) => updateIntroPolicy('offset_hours', Number(e.target.value) || 0.25)}
                  />
                </label>
                <label className="form-group">
                  <span className="form-group__label">Порог immediate (часы)</span>
                  <input
                    type="number"
                    min={0}
                    max={24}
                    step={0.25}
                    value={policyDraft.min_time_before_immediate_hours}
                    onChange={(e) =>
                      setPolicyDraft((prev) =>
                        prev
                          ? {
                              ...prev,
                              min_time_before_immediate_hours: Number(e.target.value) || 0,
                            }
                          : prev,
                      )
                    }
                  />
                </label>
              </div>

              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <button className="ui-btn ui-btn--primary" onClick={saveReminderPolicy} disabled={savingPolicy}>
                  {savingPolicy ? 'Сохраняем…' : 'Сохранить политику'}
                </button>
                {policyResult && <span className="subtitle">{policyResult}</span>}
              </div>
            </div>
          )}
        </section>

        <section className="glass page-section">
          <h2 className="section-title">Доставка уведомлений (Outbox)</h2>
          <p className="subtitle">
            Очередь уведомлений Telegram. Используйте фильтры и ручной retry/cancel для triage.
          </p>

          <div className="form-row" style={{ alignItems: 'flex-end' }}>
            <label className="form-group" style={{ minWidth: 220 }}>
              <span className="form-group__label">Статус</span>
              <select value={outboxStatusFilter} onChange={(e) => setOutboxStatusFilter(e.target.value)}>
                <option value="">Все</option>
                <option value="pending">pending</option>
                <option value="failed">failed</option>
                <option value="sent">sent</option>
              </select>
            </label>
            <label className="form-group" style={{ flex: 1, minWidth: 260 }}>
              <span className="form-group__label">Тип</span>
              <input
                value={outboxTypeFilter}
                onChange={(e) => setOutboxTypeFilter(e.target.value)}
                placeholder="Например: slot_assignment_offer"
              />
            </label>
            <button className="ui-btn ui-btn--ghost" onClick={() => outboxQuery.refetch()}>
              Обновить
            </button>
          </div>

          {outboxQuery.isLoading && <p className="subtitle">Загрузка outbox…</p>}
          {outboxQuery.isError && <p className="text-danger">Ошибка: {(outboxQuery.error as Error).message}</p>}

          {outboxQuery.data?.degraded && (
            <p className="text-danger">DB degraded: данные outbox недоступны.</p>
          )}

          {outboxQuery.data && (
            <>
              <p className="subtitle">Latest ID: {outboxQuery.data.latest_id}</p>
              <div className="glass panel--tight" style={{ overflowX: 'auto' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Type</th>
                      <th>Status</th>
                      <th>Attempts</th>
                      <th>Next retry</th>
                      <th>Last error</th>
                      <th>Target</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {outboxQuery.data.items.length === 0 && (
                      <tr>
                        <td colSpan={8} className="subtitle">Пусто</td>
                      </tr>
                    )}
                    {outboxQuery.data.items.map((item) => {
                      const target = item.candidate_tg_id
                        ? `cand:${item.candidate_tg_id}`
                        : item.recruiter_tg_id
                          ? `rec:${item.recruiter_tg_id}`
                          : '-'
                      const canRetry = item.status !== 'sent'
                      const canCancel = item.status === 'pending' || item.status === 'failed'
                      return (
                        <tr key={item.id}>
                          <td>{item.id}</td>
                          <td style={{ whiteSpace: 'nowrap' }}>{item.type}</td>
                          <td>{item.status}</td>
                          <td>{item.attempts}</td>
                          <td style={{ whiteSpace: 'nowrap' }}>{item.next_retry_at || '-'}</td>
                          <td style={{ maxWidth: 360, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {item.last_error || '-'}
                          </td>
                          <td style={{ whiteSpace: 'nowrap' }}>{target}</td>
                          <td>
                            <div className="toolbar toolbar--compact">
                              <button
                                className="ui-btn ui-btn--ghost ui-btn--sm"
                                onClick={() => retryOutboxMutation.mutate(item.id)}
                                disabled={!canRetry || retryOutboxMutation.isPending}
                              >
                                Retry
                              </button>
                              <button
                                className="ui-btn ui-btn--danger ui-btn--sm"
                                onClick={() =>
                                  canCancel
                                  && window.confirm(`Cancel outbox #${item.id}?`)
                                  && cancelOutboxMutation.mutate(item.id)
                                }
                                disabled={!canCancel || cancelOutboxMutation.isPending}
                              >
                                Cancel
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      </div>
    </RoleGuard>
  )
}
