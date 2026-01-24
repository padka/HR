import { useQuery } from '@tanstack/react-query'
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
  service_health: string
  service_ready: boolean
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

  return (
    <RoleGuard allow={['admin']}>
      <div className="page">
        <div className="glass panel">
          <h1 className="title">Система</h1>
          <p className="subtitle">Состояние ключевых сервисов и оперативная статистика.</p>
        </div>

        <div className="glass panel" style={{ display: 'grid', gap: 12 }}>
          <h2 className="section-title">Health snapshot</h2>
          {healthQuery.isLoading && <p className="subtitle">Загрузка…</p>}
          {healthQuery.isError && <p style={{ color: '#f07373' }}>Ошибка: {(healthQuery.error as Error).message}</p>}
          {healthQuery.data && (
            <div className="grid-cards">
              <div className="glass stat-card">
                <div className="stat-label">Рекрутёры</div>
                <div className="stat-value">{healthQuery.data.recruiters}</div>
              </div>
              <div className="glass stat-card">
                <div className="stat-label">Города</div>
                <div className="stat-value">{healthQuery.data.cities}</div>
              </div>
              <div className="glass stat-card">
                <div className="stat-label">Слоты</div>
                <div className="stat-value">{healthQuery.data.slots_total}</div>
              </div>
              <div className="glass stat-card">
                <div className="stat-label">Ожидают</div>
                <div className="stat-value">{healthQuery.data.slots_pending}</div>
              </div>
              <div className="glass stat-card">
                <div className="stat-label">Бронь</div>
                <div className="stat-value">{healthQuery.data.slots_booked}</div>
              </div>
              <div className="glass stat-card">
                <div className="stat-label">Ждут слот</div>
                <div className="stat-value">{healthQuery.data.waiting_candidates_total}</div>
              </div>
            </div>
          )}
        </div>

        <div className="glass panel" style={{ display: 'grid', gap: 12 }}>
          <h2 className="section-title">Бот и интеграции</h2>
          {botQuery.isLoading && <p className="subtitle">Загрузка…</p>}
          {botQuery.isError && <p style={{ color: '#f07373' }}>Ошибка: {(botQuery.error as Error).message}</p>}
          {botQuery.data && (
            <div className="grid-cards">
              <div className="glass stat-card">
                <div className="stat-label">Config enabled</div>
                <div className="stat-value">{botQuery.data.config_enabled ? 'Да' : 'Нет'}</div>
              </div>
              <div className="glass stat-card">
                <div className="stat-label">Runtime enabled</div>
                <div className="stat-value">{botQuery.data.runtime_enabled ? 'Да' : 'Нет'}</div>
              </div>
              <div className="glass stat-card">
                <div className="stat-label">Health</div>
                <div className="stat-value">{botQuery.data.service_health}</div>
              </div>
              <div className="glass stat-card">
                <div className="stat-label">Ready</div>
                <div className="stat-value">{botQuery.data.service_ready ? 'Да' : 'Нет'}</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </RoleGuard>
  )
}
