/**
 * Telegram Mini App — Dashboard view.
 * Shows KPIs, urgency summary, and the next recruiter action.
 */
import { useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import './surface.css'

interface DashboardData {
  waiting_candidates_total: number
  scheduled_today: number
  free_slots: number
  recruiter_name: string
}

type BannerTone = 'info' | 'warning' | 'success'

type TelegramWebAppWindow = Window & {
  Telegram?: {
    WebApp?: {
      initData?: string
    }
  }
}

function useTgInitData(): string {
  // In Telegram Mini App, window.Telegram.WebApp.initData is available
  try {
    return (window as TelegramWebAppWindow).Telegram?.WebApp?.initData || ''
  } catch {
    return ''
  }
}

async function fetchDashboard(initData: string): Promise<DashboardData> {
  return apiFetch<DashboardData>('/webapp/recruiter/dashboard', {
    headers: { 'X-Telegram-Init-Data': initData },
  })
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Не удалось загрузить экран'
}

function pluralizeCandidates(count: number): string {
  const mod10 = count % 10
  const mod100 = count % 100

  if (mod10 === 1 && mod100 !== 11) return 'кандидат'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return 'кандидата'
  return 'кандидатов'
}

function resolveSummary(data: DashboardData): { tone: BannerTone; title: string; text: string; actionLabel: string } {
  if (data.waiting_candidates_total > 0) {
    return {
      tone: data.waiting_candidates_total >= 5 ? 'warning' : 'info',
      title: `Во входящих ждут ${data.waiting_candidates_total} ${pluralizeCandidates(data.waiting_candidates_total)}`,
      text: 'Откройте очередь и начните с кандидатов, которые дольше всего ждут ответа.',
      actionLabel: 'Разобрать входящие',
    }
  }

  if (data.scheduled_today > 0) {
    return {
      tone: 'success',
      title: 'Очередь под контролем',
      text: 'Новых ожиданий нет. Следующий шаг: проверьте встречи на сегодня и готовность свободных слотов.',
      actionLabel: 'Проверить очередь',
    }
  }

  return {
    tone: 'success',
    title: 'Срочных входящих нет',
    text: 'Экран спокойный. Следующий шаг: держите под рукой очередь и свободные слоты для новых кандидатов.',
    actionLabel: 'Открыть входящие',
  }
}

export function TgDashboardPage() {
  const initData = useTgInitData()
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!initData) {
      setError('Откройте экран из Telegram Mini App, чтобы загрузить рабочие данные.')
      return
    }
    fetchDashboard(initData).then(setData).catch((fetchError: unknown) => setError(errorMessage(fetchError)))
  }, [initData])

  if (error) {
    return (
      <TgStateCard
        title="Нужен доступ через Telegram"
        text={error}
        eyebrow="Доступ"
        role="alert"
      />
    )
  }
  if (!data) {
    return (
      <TgStateCard
        title="Загружаем рабочий экран"
        text="Подтягиваем очередь, встречи и свободные слоты."
        eyebrow="Загрузка"
      />
    )
  }

  const summary = resolveSummary(data)
  const recruiterName = data.recruiter_name?.trim() || 'Рабочий экран'

  return (
    <div className="tg-screen">
      <header className="tg-page-header">
        <p className="tg-page-header__eyebrow">Telegram</p>
        <div className="tg-page-header__top">
          <div>
            <h1 className="tg-page-header__title">{recruiterName}</h1>
            <p className="tg-page-header__subtitle">
              Короткая сводка по очереди и ближайшему действию без лишней обвязки.
            </p>
          </div>
        </div>
      </header>

      <section className={`tg-banner tg-banner--${summary.tone}`} aria-live="polite">
        <p className="tg-banner__eyebrow">В приоритете</p>
        <h2 className="tg-banner__title">{summary.title}</h2>
        <p className="tg-banner__text">{summary.text}</p>
      </section>

      <section className="tg-metric-grid" aria-label="Ключевые показатели">
        <KpiCard label="Ожидают" value={data.waiting_candidates_total} tone="warning" />
        <KpiCard label="Сегодня" value={data.scheduled_today} tone="accent" />
        <KpiCard label="Свободно" value={data.free_slots} tone="success" />
      </section>

      <Link to="/tg-app/incoming" className="tg-link-card">
        <div>
          <p className="tg-card__eyebrow">Следующий шаг</p>
          <h2 className="tg-link-card__title">Очередь входящих кандидатов</h2>
          <p className="tg-card__text">
            {data.waiting_candidates_total > 0
              ? `Сейчас ждут внимания ${data.waiting_candidates_total} ${pluralizeCandidates(data.waiting_candidates_total)}.`
              : 'Очередь спокойная, но экран стоит держать под рукой.'}
          </p>
        </div>
        <span className="tg-link-card__action">{summary.actionLabel}</span>
      </Link>
    </div>
  )
}

function TgStateCard({
  eyebrow,
  title,
  text,
  role = 'status',
}: {
  eyebrow: string
  title: string
  text: string
  role?: 'status' | 'alert'
}) {
  return (
    <div className="tg-state-card" role={role}>
      <p className="tg-card__eyebrow">{eyebrow}</p>
      <h1 className="tg-state-card__title">{title}</h1>
      <p className="tg-state-card__text">{text}</p>
    </div>
  )
}

function KpiCard({
  label,
  value,
  tone,
}: {
  label: string
  value: number
  tone: 'warning' | 'accent' | 'success'
}) {
  return (
    <div className="tg-metric-card">
      <div className={`tg-metric-card__value tg-metric-card__value--${tone}`}>{value}</div>
      <div className="tg-metric-card__label">{label}</div>
    </div>
  )
}
