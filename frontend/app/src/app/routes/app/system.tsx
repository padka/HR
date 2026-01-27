import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
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

  const [refreshingCities, setRefreshingCities] = useState(false)
  const [refreshResult, setRefreshResult] = useState<string | null>(null)

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
      </div>
    </RoleGuard>
  )
}
