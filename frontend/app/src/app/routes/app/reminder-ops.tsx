import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '@/api/client'

type ReminderJob = {
  id: number
  slot_id: number
  kind: string
  job_id: string
  scheduled_at: string
  slot_start_utc: string
  slot_status: string
  purpose: string
  candidate_tg_id: number
  candidate_fio: string
}

type ReminderJobsResponse = {
  items: ReminderJob[]
  now_utc: string
}

const KIND_LABELS: Record<string, string> = {
  confirm_6h: 'Подтверждение 6ч',
  confirm_3h: 'Подтверждение 3ч',
  confirm_2h: 'Подтверждение 2ч',
  remind_2h: 'Напоминание 2ч',
  intro_remind_3h: 'Интро 3ч',
}

const KIND_CLASSES: Record<string, string> = {
  confirm_6h: 'reminder-kind-badge--confirm',
  confirm_3h: 'reminder-kind-badge--confirm',
  confirm_2h: 'reminder-kind-badge--confirm',
  remind_2h: 'reminder-kind-badge--remind',
  intro_remind_3h: 'reminder-kind-badge--intro',
}

function formatDt(iso: string): string {
  try {
    return new Date(iso).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return iso
  }
}

async function fetchReminderJobs(kind?: string): Promise<ReminderJobsResponse> {
  const params = kind ? `?kind=${encodeURIComponent(kind)}` : ''
  return apiFetch<ReminderJobsResponse>(`/bot/reminder-jobs${params}`)
}

async function cancelReminderJob(jobId: string): Promise<void> {
  await apiFetch<unknown>(`/bot/reminder-jobs/${encodeURIComponent(jobId)}`, { method: 'DELETE' })
}

export default function ReminderOpsPage() {
  const [kindFilter, setKindFilter] = useState('')
  const [autoRefresh, setAutoRefresh] = useState(true)
  const qc = useQueryClient()

  const { data, isLoading, error, dataUpdatedAt } = useQuery({
    queryKey: ['reminder-jobs', kindFilter],
    queryFn: () => fetchReminderJobs(kindFilter || undefined),
    refetchInterval: autoRefresh ? 30_000 : false,
  })

  const cancelMutation = useMutation({
    mutationFn: cancelReminderJob,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reminder-jobs'] }),
  })

  const items = data?.items ?? []

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Ops: Напоминания</h1>
        <div className="page-header__actions" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <label style={{ fontSize: 13, display: 'flex', gap: 6, alignItems: 'center', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            Авто-обновление (30с)
          </label>
          <button
            className="ui-btn ui-btn--ghost ui-btn--sm"
            onClick={() => qc.invalidateQueries({ queryKey: ['reminder-jobs'] })}
          >
            Обновить
          </button>
        </div>
      </div>

      <div className="page-section">
        <div className="toolbar toolbar--compact" style={{ marginBottom: 16 }}>
          <select
            className="ui-select"
            value={kindFilter}
            onChange={(e) => setKindFilter(e.target.value)}
          >
            <option value="">Все типы</option>
            {Object.entries(KIND_LABELS).map(([k, label]) => (
              <option key={k} value={k}>{label}</option>
            ))}
          </select>

          {data && (
            <span style={{ fontSize: 12, color: 'var(--fg-muted)', marginLeft: 8 }}>
              {items.length} записей · обновлено {formatDt(new Date(dataUpdatedAt).toISOString())}
            </span>
          )}
        </div>

        {isLoading && <div>Загрузка...</div>}
        {error && <div style={{ color: 'var(--danger)' }}>Ошибка загрузки</div>}

        {!isLoading && items.length === 0 && (
          <div className="empty-state">
            <p>
              Нет запланированных напоминаний
              {kindFilter ? ` для фильтра «${KIND_LABELS[kindFilter] ?? kindFilter}»` : ''}.
            </p>
          </div>
        )}

        {items.length > 0 && (
          <div className="glass" style={{ overflow: 'auto' }}>
            <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', padding: '8px 12px', borderBottom: '1px solid var(--glass-border)', fontWeight: 600, fontSize: 12 }}>Кандидат</th>
                  <th style={{ textAlign: 'left', padding: '8px 12px', borderBottom: '1px solid var(--glass-border)', fontWeight: 600, fontSize: 12 }}>Тип</th>
                  <th style={{ textAlign: 'left', padding: '8px 12px', borderBottom: '1px solid var(--glass-border)', fontWeight: 600, fontSize: 12 }}>Запланировано</th>
                  <th style={{ textAlign: 'left', padding: '8px 12px', borderBottom: '1px solid var(--glass-border)', fontWeight: 600, fontSize: 12 }}>Слот</th>
                  <th style={{ textAlign: 'left', padding: '8px 12px', borderBottom: '1px solid var(--glass-border)', fontWeight: 600, fontSize: 12 }}>Назначение</th>
                  <th style={{ padding: '8px 12px', borderBottom: '1px solid var(--glass-border)' }}></th>
                </tr>
              </thead>
              <tbody>
                {items.map((job) => (
                  <tr key={job.id} style={{ borderBottom: '1px solid var(--glass-border)' }}>
                    <td style={{ padding: '8px 12px', fontSize: 13 }}>
                      <div style={{ fontWeight: 500 }}>{job.candidate_fio || '—'}</div>
                      <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>tg:{job.candidate_tg_id}</div>
                    </td>
                    <td style={{ padding: '8px 12px' }}>
                      <span className={`chip reminder-kind-badge ${KIND_CLASSES[job.kind] ?? ''}`}>
                        {KIND_LABELS[job.kind] ?? job.kind}
                      </span>
                    </td>
                    <td style={{ padding: '8px 12px', fontSize: 13 }}>
                      <div>{formatDt(job.scheduled_at)}</div>
                      <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>
                        слот: {formatDt(job.slot_start_utc)}
                      </div>
                    </td>
                    <td style={{ padding: '8px 12px', fontSize: 13 }}>
                      <a
                        href={`/app/candidates?slot=${job.slot_id}`}
                        style={{ color: 'var(--accent)', textDecoration: 'none' }}
                      >
                        #{job.slot_id}
                      </a>
                      <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>{job.slot_status}</div>
                    </td>
                    <td style={{ padding: '8px 12px', fontSize: 12 }}>
                      <span className={`status-badge ${job.purpose === 'intro_day' ? 'status-badge--info' : 'status-badge--muted'}`}>
                        {job.purpose === 'intro_day' ? 'Интро-день' : 'Собеседование'}
                      </span>
                    </td>
                    <td style={{ padding: '8px 12px' }}>
                      <button
                        className="ui-btn ui-btn--ghost ui-btn--sm"
                        disabled={cancelMutation.isPending}
                        onClick={() => {
                          if (confirm(`Отменить напоминание ${KIND_LABELS[job.kind] ?? job.kind} для ${job.candidate_fio}?`)) {
                            cancelMutation.mutate(job.job_id)
                          }
                        }}
                        title="Отменить напоминание"
                        style={{ color: 'var(--danger)' }}
                      >
                        Отмена
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
