import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import {
  fetchHHConnection,
  getHHAuthorizeUrl,
  importHHNegotiations,
  importHHVacancies,
  listHHSyncJobs,
  listHHWebhooks,
  refreshHHTokens,
  registerHHWebhooks,
  retryHHSyncJob,
  type HHConnectionPayload,
  type HHImportResult,
} from '@/api/services/hh-integration'
import {
  cancelNotification,
  fetchBotIntegration,
  fetchMessengerHealth,
  fetchNotificationLogs,
  fetchNotificationsFeed,
  fetchQuestionGroups,
  fetchReminderJobs,
  fetchReminderPolicy,
  fetchSystemHealth,
  refreshBotCities as refreshBotCitiesRequest,
  resyncReminderJobs,
  retryNotification,
  type BotStatus,
  type HealthPayload,
  type MessengerHealthPayload,
  type NotificationLogsPayload,
  type OutboxFeedPayload,
  type QuestionGroup,
  type ReminderKindConfig,
  type ReminderPolicy,
  type ReminderPolicyPayload,
  updateReminderPolicy,
} from '@/api/services/system'
import { RoleGuard } from '@/app/components/RoleGuard'
import { MessengerHealthCards } from './system.delivery-health'

type BotCenterTab = 'health' | 'tests' | 'templates' | 'reminders' | 'delivery' | 'hh'
type HHJobStatusFilter = '' | 'pending' | 'running' | 'completed' | 'failed'

function formatSystemDateTime(value?: string | null) {
  if (!value) return '—'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return dt.toLocaleString('ru-RU')
}

function getHHConnectionStatus(payload?: HHConnectionPayload | null) {
  if (!payload?.enabled) {
    return { label: 'Выключена', tone: 'warning' as const }
  }
  if (!payload.connected || !payload.connection) {
    return { label: 'Не подключено', tone: 'info' as const }
  }
  if (payload.connection.status === 'error') {
    return { label: 'Ошибка', tone: 'danger' as const }
  }
  if (payload.connection.status === 'revoked') {
    return { label: 'Отозвано', tone: 'warning' as const }
  }
  return { label: 'Подключено', tone: 'success' as const }
}

function getHHJobStatusMeta(status?: string | null) {
  switch (status) {
    case 'pending':
      return { label: 'pending', tone: 'warning' as const }
    case 'running':
      return { label: 'running', tone: 'info' as const }
    case 'done':
      return { label: 'completed', tone: 'success' as const }
    case 'dead':
      return { label: 'failed', tone: 'danger' as const }
    case 'error':
      return { label: 'error', tone: 'danger' as const }
    default:
      return { label: status || 'unknown', tone: 'info' as const }
  }
}

function summarizeHHImportResult(result: HHImportResult) {
  const totalSeen = result.total_seen ?? result.negotiations_seen ?? 0
  const created = result.created ?? result.negotiations_created ?? 0
  const updated = result.updated ?? result.negotiations_updated ?? 0
  const skipped = Math.max(totalSeen - created - updated, 0)
  return `Создано: ${created}, Обновлено: ${updated}, Пропущено: ${skipped}`
}

function mapHHStatusFilterToApi(status: HHJobStatusFilter): string | undefined {
  if (status === 'completed') return 'done'
  if (status === 'failed') return 'dead'
  return status || undefined
}

function HHIntegrationSection({ active }: { active: boolean }) {
  const queryClient = useQueryClient()
  const [jobsStatusFilter, setJobsStatusFilter] = useState<HHJobStatusFilter>('')
  const [connectionResult, setConnectionResult] = useState<string | null>(null)
  const [webhookResult, setWebhookResult] = useState<string | null>(null)
  const [vacanciesImportResult, setVacanciesImportResult] = useState<string | null>(null)
  const [negotiationsImportResult, setNegotiationsImportResult] = useState<string | null>(null)
  const [jobsResult, setJobsResult] = useState<string | null>(null)

  const connectionQuery = useQuery<HHConnectionPayload>({
    queryKey: ['hh-connection'],
    queryFn: fetchHHConnection,
    enabled: active,
    refetchInterval: active ? 30_000 : false,
  })

  const isConnected = Boolean(connectionQuery.data?.connected && connectionQuery.data.connection)
  const connectionStatus = getHHConnectionStatus(connectionQuery.data)

  const webhooksQuery = useQuery({
    queryKey: ['hh-webhooks'],
    queryFn: listHHWebhooks,
    enabled: active && isConnected,
    refetchInterval: active && isConnected ? 30_000 : false,
  })

  const jobsQuery = useQuery({
    queryKey: ['hh-sync-jobs', jobsStatusFilter],
    queryFn: () => listHHSyncJobs(20, mapHHStatusFilterToApi(jobsStatusFilter)),
    enabled: active && isConnected,
    refetchInterval: active && isConnected ? 10_000 : false,
  })

  const invalidateHHQueries = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['hh-connection'] }),
      queryClient.invalidateQueries({ queryKey: ['hh-webhooks'] }),
      queryClient.invalidateQueries({ queryKey: ['hh-sync-jobs'] }),
    ])
  }

  const connectMutation = useMutation({
    mutationFn: () => getHHAuthorizeUrl(typeof window !== 'undefined' ? window.location.href : undefined),
    onSuccess: ({ authorize_url }) => {
      setConnectionResult(null)
      window.location.assign(authorize_url)
    },
    onError: (err: unknown) => {
      const message = err instanceof Error ? err.message : 'Не удалось получить URL авторизации HH.'
      setConnectionResult(message || 'Не удалось получить URL авторизации HH.')
    },
  })

  const refreshTokensMutation = useMutation({
    mutationFn: refreshHHTokens,
    onSuccess: async () => {
      setConnectionResult('Токен HH обновлён.')
      await invalidateHHQueries()
    },
    onError: (err: unknown) => {
      const message = err instanceof Error ? err.message : 'Ошибка обновления токена HH.'
      setConnectionResult(message || 'Ошибка обновления токена HH.')
    },
  })

  const registerWebhooksMutation = useMutation({
    mutationFn: registerHHWebhooks,
    onSuccess: async (payload) => {
      setWebhookResult(`Вебхуки зарегистрированы: ${payload.actions.join(', ')}`)
      await invalidateHHQueries()
    },
    onError: (err: unknown) => {
      const message = err instanceof Error ? err.message : 'Ошибка регистрации вебхуков.'
      setWebhookResult(message || 'Ошибка регистрации вебхуков.')
    },
  })

  const importVacanciesMutation = useMutation({
    mutationFn: importHHVacancies,
    onSuccess: async (result) => {
      setVacanciesImportResult(summarizeHHImportResult(result))
      await invalidateHHQueries()
    },
    onError: (err: unknown) => {
      const message = err instanceof Error ? err.message : 'Ошибка импорта вакансий.'
      setVacanciesImportResult(message || 'Ошибка импорта вакансий.')
    },
  })

  const importNegotiationsMutation = useMutation({
    mutationFn: () => importHHNegotiations(),
    onSuccess: async (result) => {
      setNegotiationsImportResult(summarizeHHImportResult(result))
      await invalidateHHQueries()
    },
    onError: (err: unknown) => {
      const message = err instanceof Error ? err.message : 'Ошибка импорта откликов.'
      setNegotiationsImportResult(message || 'Ошибка импорта откликов.')
    },
  })

  const retryJobMutation = useMutation({
    mutationFn: retryHHSyncJob,
    onSuccess: async (payload) => {
      setJobsResult(`Job #${payload.job.id} поставлен в retry.`)
      await invalidateHHQueries()
    },
    onError: (err: unknown) => {
      const message = err instanceof Error ? err.message : 'Ошибка retry HH job.'
      setJobsResult(message || 'Ошибка retry HH job.')
    },
  })

  return (
    <>
      <section className="glass page-section">
        <div className="toolbar" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div>
            <h2 className="section-title" style={{ marginTop: 0, marginBottom: 4 }}>HH интеграция</h2>
            <p className="subtitle" style={{ margin: 0 }}>
              OAuth-подключение, вебхуки и состояние токенов HH.
            </p>
          </div>
          <div className="toolbar toolbar--compact">
            <button
              type="button"
              className="ui-btn ui-btn--primary ui-btn--sm"
              onClick={() => {
                setConnectionResult(null)
                connectMutation.mutate()
              }}
              disabled={connectMutation.isPending || !connectionQuery.data?.enabled}
            >
              {connectMutation.isPending ? 'Переходим…' : 'Подключить HH'}
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--ghost ui-btn--sm"
              onClick={() => {
                setConnectionResult(null)
                refreshTokensMutation.mutate()
              }}
              disabled={!isConnected || refreshTokensMutation.isPending}
            >
              {refreshTokensMutation.isPending ? 'Обновляем…' : 'Обновить токен'}
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--ghost ui-btn--sm"
              onClick={() => {
                setWebhookResult(null)
                registerWebhooksMutation.mutate()
              }}
              disabled={!isConnected || registerWebhooksMutation.isPending}
            >
              {registerWebhooksMutation.isPending ? 'Регистрируем…' : 'Зарегистрировать вебхуки'}
            </button>
          </div>
        </div>

        {connectionQuery.isLoading && <p className="subtitle">Загрузка HH подключения…</p>}
        {connectionQuery.isError && (
          <p className="text-danger">Ошибка: {(connectionQuery.error as Error).message}</p>
        )}

        {connectionQuery.data && (
          <>
            <div className="data-grid">
              <article className="glass glass--interactive data-card">
                <div className="data-card__label">Интеграция</div>
                <div className="data-card__value">
                  <span className={`status-badge status-badge--${connectionQuery.data.enabled ? 'success' : 'warning'}`}>
                    {connectionQuery.data.enabled ? 'enabled' : 'disabled'}
                  </span>
                </div>
              </article>
              <article className="glass glass--interactive data-card">
                <div className="data-card__label">Статус</div>
                <div className="data-card__value">
                  <span className={`status-badge status-badge--${connectionStatus.tone}`}>
                    {connectionStatus.label}
                  </span>
                </div>
              </article>
              <article className="glass glass--interactive data-card">
                <div className="data-card__label">Работодатель</div>
                <div className="data-card__value">{connectionQuery.data.connection?.employer_name || '—'}</div>
              </article>
              <article className="glass glass--interactive data-card">
                <div className="data-card__label">Менеджер</div>
                <div className="data-card__value">{connectionQuery.data.connection?.manager_name || '—'}</div>
              </article>
              <article className="glass glass--interactive data-card">
                <div className="data-card__label">Вебхуки HH</div>
                <div className="data-card__value">
                  {isConnected ? String(webhooksQuery.data?.subscriptions.length ?? 0) : '—'}
                </div>
              </article>
              <article className="glass glass--interactive data-card">
                <div className="data-card__label">Токен истекает</div>
                <div className="data-card__value">
                  {formatSystemDateTime(connectionQuery.data.connection?.token_expires_at)}
                </div>
              </article>
            </div>

            {connectionQuery.data.connection && (
              <div className="glass panel--tight" style={{ overflowX: 'auto', marginTop: 16 }}>
                <table className="data-table">
                  <tbody>
                    <tr>
                      <th>Employer</th>
                      <td>{connectionQuery.data.connection.employer_name || '—'}</td>
                    </tr>
                    <tr>
                      <th>Manager</th>
                      <td>{connectionQuery.data.connection.manager_name || '—'}</td>
                    </tr>
                    <tr>
                      <th>Manager account ID</th>
                      <td>{connectionQuery.data.connection.manager_account_id || '—'}</td>
                    </tr>
                    <tr>
                      <th>Webhook URL</th>
                      <td>{connectionQuery.data.connection.webhook_url || '—'}</td>
                    </tr>
                    <tr>
                      <th>Connected at</th>
                      <td>—</td>
                    </tr>
                    <tr>
                      <th>Token expires</th>
                      <td>{formatSystemDateTime(connectionQuery.data.connection.token_expires_at)}</td>
                    </tr>
                    <tr>
                      <th>Last sync</th>
                      <td>{formatSystemDateTime(connectionQuery.data.connection.last_sync_at)}</td>
                    </tr>
                    <tr>
                      <th>Last error</th>
                      <td>{connectionQuery.data.connection.last_error || '—'}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            )}

            {webhooksQuery.isError && (
              <p className="text-danger" style={{ marginTop: 12 }}>
                Ошибка чтения вебхуков: {(webhooksQuery.error as Error).message}
              </p>
            )}
          </>
        )}

        {connectionResult && <p className="subtitle" style={{ marginTop: 12 }}>{connectionResult}</p>}
        {webhookResult && <p className="subtitle" style={{ marginTop: 8 }}>{webhookResult}</p>}
      </section>

      <section className="glass page-section">
        <h2 className="section-title">Импорт из HH</h2>
        <p className="subtitle">Ручной запуск прямого импорта вакансий и откликов из HH.</p>

        <div className="toolbar" style={{ gap: 12, marginBottom: 12 }}>
          <button
            type="button"
            className="ui-btn ui-btn--primary"
            onClick={() => {
              setVacanciesImportResult(null)
              importVacanciesMutation.mutate()
            }}
            disabled={!isConnected || importVacanciesMutation.isPending}
          >
            {importVacanciesMutation.isPending ? 'Импортируем…' : 'Импорт вакансий'}
          </button>
          <button
            type="button"
            className="ui-btn ui-btn--ghost"
            onClick={() => {
              setNegotiationsImportResult(null)
              importNegotiationsMutation.mutate()
            }}
            disabled={!isConnected || importNegotiationsMutation.isPending}
          >
            {importNegotiationsMutation.isPending ? 'Импортируем…' : 'Импорт откликов'}
          </button>
        </div>

        {!isConnected && <p className="subtitle">Сначала подключите HH, чтобы запускать импорт.</p>}
        {vacanciesImportResult && <p className="subtitle">Вакансии: {vacanciesImportResult}</p>}
        {negotiationsImportResult && <p className="subtitle">Отклики: {negotiationsImportResult}</p>}
      </section>

      <section className="glass page-section">
        <div className="toolbar" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div>
            <h2 className="section-title" style={{ marginTop: 0, marginBottom: 4 }}>Лог HH sync jobs</h2>
            <p className="subtitle" style={{ margin: 0 }}>
              Очередь импортов обновляется каждые 10 секунд.
            </p>
          </div>
          <div className="toolbar toolbar--compact">
            <label className="form-group" style={{ minWidth: 180 }}>
              <span className="form-group__label">Статус</span>
              <select value={jobsStatusFilter} onChange={(e) => setJobsStatusFilter(e.target.value as HHJobStatusFilter)}>
                <option value="">Все</option>
                <option value="pending">pending</option>
                <option value="running">running</option>
                <option value="completed">completed</option>
                <option value="failed">failed</option>
              </select>
            </label>
            <button
              type="button"
              className="ui-btn ui-btn--ghost ui-btn--sm"
              onClick={() => jobsQuery.refetch()}
              disabled={!isConnected || jobsQuery.isFetching}
            >
              Обновить
            </button>
          </div>
        </div>

        {!isConnected && <p className="subtitle">Лог jobs появится после подключения HH.</p>}
        {jobsQuery.isLoading && isConnected && <p className="subtitle">Загрузка HH job-ов…</p>}
        {jobsQuery.isError && (
          <p className="text-danger">Ошибка: {(jobsQuery.error as Error).message}</p>
        )}

        {jobsQuery.data && (
          <div className="glass panel--tight" style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Type</th>
                  <th>Entity</th>
                  <th>Status</th>
                  <th>Attempts</th>
                  <th>Last Error</th>
                  <th>Created</th>
                  <th>Finished</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {jobsQuery.data.jobs.length === 0 && (
                  <tr>
                    <td colSpan={9} className="subtitle">Пусто</td>
                  </tr>
                )}
                {jobsQuery.data.jobs.map((job) => {
                  const statusMeta = getHHJobStatusMeta(job.status)
                  const entityLabel = [job.entity_type, job.entity_external_id].filter(Boolean).join(': ') || '—'
                  const canRetry = !['pending', 'running'].includes(job.status)
                  return (
                    <tr key={job.id}>
                      <td>{job.id}</td>
                      <td style={{ whiteSpace: 'nowrap' }}>{job.job_type}</td>
                      <td style={{ whiteSpace: 'nowrap' }}>{entityLabel}</td>
                      <td>
                        <span className={`status-badge status-badge--${statusMeta.tone}`}>
                          {statusMeta.label}
                        </span>
                      </td>
                      <td>{job.attempts}</td>
                      <td style={{ maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {job.last_error || '—'}
                      </td>
                      <td style={{ whiteSpace: 'nowrap' }}>{formatSystemDateTime(job.created_at)}</td>
                      <td style={{ whiteSpace: 'nowrap' }}>{formatSystemDateTime(job.finished_at)}</td>
                      <td>
                        <button
                          type="button"
                          className="ui-btn ui-btn--ghost ui-btn--sm"
                          onClick={() => {
                            setJobsResult(null)
                            retryJobMutation.mutate(job.id)
                          }}
                          disabled={!canRetry || retryJobMutation.isPending}
                        >
                          Retry
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {jobsResult && <p className="subtitle" style={{ marginTop: 12 }}>{jobsResult}</p>}
      </section>
    </>
  )
}

export function SystemPage() {
  const [activeTab, setActiveTab] = useState<BotCenterTab>(() => {
    if (typeof window === 'undefined') return 'health'
    return new URLSearchParams(window.location.search).get('hh') ? 'hh' : 'health'
  })

  const healthQuery = useQuery<HealthPayload>({
    queryKey: ['system-health'],
    queryFn: fetchSystemHealth,
    enabled: activeTab === 'health',
  })

  const botQuery = useQuery<BotStatus>({
    queryKey: ['system-bot'],
    queryFn: fetchBotIntegration,
    enabled: activeTab === 'health',
  })

  const questionsQuery = useQuery<QuestionGroup[]>({
    queryKey: ['bot-center-questions'],
    queryFn: fetchQuestionGroups,
    enabled: activeTab === 'tests',
  })

  const reminderPolicyQuery = useQuery<ReminderPolicyPayload>({
    queryKey: ['system-bot-reminder-policy'],
    queryFn: fetchReminderPolicy,
    enabled: activeTab === 'reminders',
  })

  const reminderJobsQuery = useQuery({
    queryKey: ['system-bot-reminder-jobs'],
    queryFn: () => fetchReminderJobs(50),
    enabled: activeTab === 'reminders',
    refetchInterval: 15_000,
  })

  const [resyncResult, setResyncResult] = useState<string | null>(null)
  const resyncRemindersMutation = useMutation({
    mutationFn: resyncReminderJobs,
    onSuccess: async (payload) => {
      setResyncResult(`Resync: scheduled=${payload.scheduled}, failed=${payload.failed}`)
      await reminderJobsQuery.refetch()
    },
    onError: (err: unknown) => {
      const message = err instanceof Error ? err.message : 'Ошибка ресинка напоминаний.'
      setResyncResult(message || 'Ошибка ресинка напоминаний.')
    },
  })

  const [outboxStatusFilter, setOutboxStatusFilter] = useState<string>('')
  const [outboxTypeFilter, setOutboxTypeFilter] = useState<string>('')
  const messengerHealthQuery = useQuery<MessengerHealthPayload>({
    queryKey: ['system-messenger-health'],
    queryFn: fetchMessengerHealth,
    refetchInterval: 15_000,
    enabled: activeTab === 'delivery',
  })

  const outboxQuery = useQuery<OutboxFeedPayload>({
    queryKey: ['system-outbox-feed', outboxStatusFilter, outboxTypeFilter],
    queryFn: () => {
      const params = new URLSearchParams()
      params.set('after_id', '0')
      params.set('limit', '50')
      if (outboxStatusFilter) params.set('status', outboxStatusFilter)
      if (outboxTypeFilter.trim()) params.set('type', outboxTypeFilter.trim())
      return fetchNotificationsFeed(params.toString())
    },
    refetchInterval: 10_000,
    enabled: activeTab === 'delivery',
  })

  const [logStatusFilter, setLogStatusFilter] = useState<string>('')
  const [logTypeFilter, setLogTypeFilter] = useState<string>('')
  const [logCandidateFilter, setLogCandidateFilter] = useState<string>('')

  const logsQuery = useQuery<NotificationLogsPayload>({
    queryKey: ['system-notification-logs', logStatusFilter, logTypeFilter, logCandidateFilter],
    queryFn: () => {
      const params = new URLSearchParams()
      params.set('after_id', '0')
      params.set('limit', '50')
      if (logStatusFilter) params.set('status', logStatusFilter)
      if (logTypeFilter.trim()) params.set('type', logTypeFilter.trim())
      const candidate = Number(logCandidateFilter)
      if (Number.isFinite(candidate) && candidate > 0) params.set('candidate_tg_id', String(candidate))
      return fetchNotificationLogs(params.toString())
    },
    refetchInterval: 15_000,
    enabled: activeTab === 'delivery',
  })

  const retryOutboxMutation = useMutation({
    mutationFn: retryNotification,
    onSuccess: () => outboxQuery.refetch(),
  })

  const cancelOutboxMutation = useMutation({
    mutationFn: cancelNotification,
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
      await refreshBotCitiesRequest()
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
      const payload = await updateReminderPolicy(policyDraft)
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
          <h1 className="title">Bot Center</h1>
          <p className="subtitle">Контент тестов, шаблоны, напоминания и доставка уведомлений.</p>
        </header>

        <div className="slot-create-tabs" style={{ marginTop: 16 }}>
          <button type="button" className={`slot-create-tab ${activeTab === 'health' ? 'is-active' : ''}`} onClick={() => setActiveTab('health')}>
            Health / Switch
          </button>
          <button type="button" className={`slot-create-tab ${activeTab === 'tests' ? 'is-active' : ''}`} onClick={() => setActiveTab('tests')}>
            Тесты
          </button>
          <button type="button" className={`slot-create-tab ${activeTab === 'templates' ? 'is-active' : ''}`} onClick={() => setActiveTab('templates')}>
            Шаблоны
          </button>
          <button type="button" className={`slot-create-tab ${activeTab === 'reminders' ? 'is-active' : ''}`} onClick={() => setActiveTab('reminders')}>
            Напоминания
          </button>
          <button type="button" className={`slot-create-tab ${activeTab === 'delivery' ? 'is-active' : ''}`} onClick={() => setActiveTab('delivery')}>
            Доставка
          </button>
          <button type="button" className={`slot-create-tab ${activeTab === 'hh' ? 'is-active' : ''}`} onClick={() => setActiveTab('hh')}>
            HH
          </button>
        </div>

        {activeTab === 'health' && (
          <>
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
          </>
        )}

        {activeTab === 'tests' && (
          <section className="glass page-section">
            <h2 className="section-title">Контент тестов</h2>
            <p className="subtitle">Вопросы и варианты ответов берутся из БД и применяются ботом без рестарта.</p>
            <div className="toolbar" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
              <div className="toolbar toolbar--compact">
                <Link to="/app/test-builder" className="ui-btn ui-btn--ghost ui-btn--sm">
                  Конструктор
                </Link>
                <Link to="/app/questions/new" className="ui-btn ui-btn--primary ui-btn--sm">
                  + Новый вопрос
                </Link>
                <Link to="/app/questions" className="ui-btn ui-btn--ghost ui-btn--sm">
                  Все вопросы
                </Link>
              </div>
              <div className="subtitle" style={{ margin: 0 }}>
                Источник правды: <code>tests/questions/answer_options</code>
              </div>
            </div>

            {questionsQuery.isLoading && <p className="subtitle">Загрузка…</p>}
            {questionsQuery.isError && <p className="text-danger">Ошибка: {(questionsQuery.error as Error).message}</p>}

            {questionsQuery.data && (
              <div className="page-section__content">
                {questionsQuery.data.map((group) => (
                  <article key={group.test_id} className="glass glass--subtle data-card" style={{ marginBottom: 12 }}>
                    <h3 className="data-card__title">{group.title}</h3>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>ID</th>
                          <th>Индекс</th>
                          <th>Вопрос</th>
                          <th>Статус</th>
                          <th>Действия</th>
                        </tr>
                      </thead>
                      <tbody>
                        {group.questions.map((q) => (
                          <tr key={q.id}>
                            <td>{q.id}</td>
                            <td>{q.index}</td>
                            <td>{q.title}</td>
                            <td>
                              <span className={`status-badge status-badge--${q.is_active ? 'success' : 'muted'}`}>
                                {q.is_active ? 'Активен' : 'Отключён'}
                              </span>
                            </td>
                            <td>
                              <Link
                                to="/app/questions/$questionId/edit"
                                params={{ questionId: String(q.id) }}
                                className="ui-btn ui-btn--ghost ui-btn--sm"
                              >
                                Редактировать
                              </Link>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </article>
                ))}
              </div>
            )}
          </section>
        )}

        {activeTab === 'templates' && (
          <section className="glass page-section">
            <h2 className="section-title">Шаблоны / уведомления</h2>
            <p className="subtitle">Простой вход в редактирование. Выберите нужный раздел.</p>
            <div className="glass panel--tight" style={{ display: 'grid', gap: 10, padding: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                <div>
                  <div style={{ fontWeight: 600 }}>Шаблоны уведомлений</div>
                  <div className="text-muted" style={{ fontSize: 12 }}>Точечные сообщения, версии, история изменений.</div>
                </div>
                <Link to="/app/message-templates" className="ui-btn ui-btn--ghost ui-btn--sm">Открыть редактор</Link>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                <div>
                  <div style={{ fontWeight: 600 }}>Системные шаблоны</div>
                  <div className="text-muted" style={{ fontSize: 12 }}>Шаблоны по этапам воронки и городам.</div>
                </div>
                <Link to="/app/templates" className="ui-btn ui-btn--ghost ui-btn--sm">Открыть редактор</Link>
              </div>
            </div>
          </section>
        )}

        {activeTab === 'reminders' && (
          <section className="glass page-section">
            <h2 className="section-title">Напоминания</h2>
            <p className="subtitle">Политика (offsets) + очередь запланированных job-ов.</p>

            {reminderPolicyQuery.isLoading && <p className="subtitle">Загрузка политики напоминаний…</p>}
            {reminderPolicyQuery.isError && (
              <p className="text-danger">Ошибка: {(reminderPolicyQuery.error as Error).message}</p>
            )}

            {policyDraft && (
              <div className="glass panel--tight" style={{ padding: 16, marginBottom: 16 }}>
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

            <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12 }}>
              <button
                className="ui-btn ui-btn--ghost"
                onClick={() => {
                  setResyncResult(null)
                  resyncRemindersMutation.mutate()
                }}
                disabled={resyncRemindersMutation.isPending}
              >
                {resyncRemindersMutation.isPending ? 'Resync…' : 'Resync jobs'}
              </button>
              <button className="ui-btn ui-btn--ghost" onClick={() => reminderJobsQuery.refetch()} disabled={reminderJobsQuery.isFetching}>
                Обновить
              </button>
              {resyncResult && <span className="subtitle">{resyncResult}</span>}
            </div>

            {reminderJobsQuery.isLoading && <p className="subtitle">Загрузка job-ов…</p>}
            {reminderJobsQuery.isError && <p className="text-danger">Ошибка: {(reminderJobsQuery.error as Error).message}</p>}
            {reminderJobsQuery.data?.degraded && <p className="text-danger">DB degraded: данные job-ов недоступны.</p>}

            {reminderJobsQuery.data && (
              <div className="glass panel--tight" style={{ overflowX: 'auto' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Kind</th>
                      <th>Run at</th>
                      <th>Slot</th>
                      <th>Slot start</th>
                      <th>Candidate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reminderJobsQuery.data.items.length === 0 && (
                      <tr>
                        <td colSpan={6} className="subtitle">Пусто</td>
                      </tr>
                    )}
                    {reminderJobsQuery.data.items.map((job) => (
                      <tr key={job.id}>
                        <td>{job.id}</td>
                        <td style={{ whiteSpace: 'nowrap' }}>{job.kind}</td>
                        <td style={{ whiteSpace: 'nowrap' }}>{job.scheduled_at || '-'}</td>
                        <td style={{ whiteSpace: 'nowrap' }}>
                          #{job.slot_id} · {job.purpose} · {job.slot_status}
                        </td>
                        <td style={{ whiteSpace: 'nowrap' }}>{job.slot_start_utc || '-'}</td>
                        <td style={{ whiteSpace: 'nowrap' }}>
                          {job.candidate_tg_id ? `cand:${job.candidate_tg_id}` : '-'}{job.candidate_fio ? ` · ${job.candidate_fio}` : ''}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {activeTab === 'delivery' && (
          <section className="glass page-section">
            <h2 className="section-title">Доставка уведомлений (Outbox)</h2>
            <p className="subtitle">
              Очередь уведомлений Telegram/MAX. Используйте фильтры и ручной requeue/cancel для triage.
            </p>

            <div className="form-row" style={{ alignItems: 'flex-end' }}>
              <label className="form-group" style={{ minWidth: 220 }}>
                <span className="form-group__label">Статус</span>
                <select value={outboxStatusFilter} onChange={(e) => setOutboxStatusFilter(e.target.value)}>
                  <option value="">Все</option>
                  <option value="pending">pending</option>
                  <option value="failed">failed</option>
                  <option value="dead_letter">dead_letter</option>
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
                <MessengerHealthCards channels={messengerHealthQuery.data?.channels} />
                <p className="subtitle">Latest ID: {outboxQuery.data.latest_id}</p>
                <div className="glass panel--tight" style={{ overflowX: 'auto' }}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Type</th>
                        <th>Channel</th>
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
                          <td colSpan={9} className="subtitle">Пусто</td>
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
                            <td>{item.channel || 'telegram'}</td>
                            <td>{item.status}</td>
                            <td>{item.attempts}</td>
                            <td style={{ whiteSpace: 'nowrap' }}>{item.next_retry_at || '-'}</td>
                            <td style={{ maxWidth: 360, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {item.last_error || item.degraded_reason || '-'}
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

            <div style={{ height: 16 }} />

            <h3 className="section-title" style={{ marginTop: 0 }}>Логи доставки</h3>
            <p className="subtitle">История попыток отправки (NotificationLog).</p>

            <div className="form-row" style={{ alignItems: 'flex-end' }}>
              <label className="form-group" style={{ minWidth: 220 }}>
                <span className="form-group__label">Статус</span>
                <select value={logStatusFilter} onChange={(e) => setLogStatusFilter(e.target.value)}>
                  <option value="">Все</option>
                  <option value="sent">sent</option>
                  <option value="failed">failed</option>
                  <option value="dead_letter">dead_letter</option>
                  <option value="pending">pending</option>
                </select>
              </label>
              <label className="form-group" style={{ flex: 1, minWidth: 260 }}>
                <span className="form-group__label">Тип</span>
                <input
                  value={logTypeFilter}
                  onChange={(e) => setLogTypeFilter(e.target.value)}
                  placeholder="Например: slot_reminder"
                />
              </label>
              <label className="form-group" style={{ minWidth: 220 }}>
                <span className="form-group__label">Candidate TG</span>
                <input
                  value={logCandidateFilter}
                  onChange={(e) => setLogCandidateFilter(e.target.value)}
                  placeholder="123456"
                />
              </label>
              <button className="ui-btn ui-btn--ghost" onClick={() => logsQuery.refetch()}>
                Обновить
              </button>
            </div>

            {logsQuery.isLoading && <p className="subtitle">Загрузка логов…</p>}
            {logsQuery.isError && <p className="text-danger">Ошибка: {(logsQuery.error as Error).message}</p>}
            {logsQuery.data?.degraded && <p className="text-danger">DB degraded: логи недоступны.</p>}

            {logsQuery.data && (
              <div className="glass panel--tight" style={{ overflowX: 'auto' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Type</th>
                      <th>Channel</th>
                      <th>Status</th>
                      <th>Attempts</th>
                      <th>Created</th>
                      <th>Last error</th>
                      <th>Booking</th>
                      <th>Candidate</th>
                      <th>Template</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logsQuery.data.items.length === 0 && (
                      <tr>
                        <td colSpan={10} className="subtitle">Пусто</td>
                      </tr>
                    )}
                    {logsQuery.data.items.map((item) => (
                      <tr key={item.id}>
                        <td>{item.id}</td>
                        <td style={{ whiteSpace: 'nowrap' }}>{item.type}</td>
                        <td>{item.channel || 'telegram'}</td>
                        <td>{item.status}</td>
                        <td>{item.attempts}</td>
                        <td style={{ whiteSpace: 'nowrap' }}>{item.created_at || '-'}</td>
                        <td style={{ maxWidth: 360, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {item.last_error || '-'}
                        </td>
                        <td style={{ whiteSpace: 'nowrap' }}>#{item.booking_id}</td>
                        <td style={{ whiteSpace: 'nowrap' }}>{item.candidate_tg_id ? `cand:${item.candidate_tg_id}` : '-'}</td>
                        <td style={{ whiteSpace: 'nowrap' }}>
                          {item.template_key ? `${item.template_key}${item.template_version ? ` v${item.template_version}` : ''}` : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {activeTab === 'hh' && <HHIntegrationSection active={activeTab === 'hh'} />}
      </div>
    </RoleGuard>
  )
}
