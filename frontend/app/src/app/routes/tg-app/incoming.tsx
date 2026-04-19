/**
 * Telegram Mini App — Incoming candidates view.
 * Shows the incoming queue with urgency and next-step cues.
 */
import { useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import './surface.css'

interface Candidate {
  id: number
  fio: string
  city: string | null
  status: string | null
  status_label: string | null
  waiting_hours: number | null
}

type TelegramWebAppWindow = Window & {
  Telegram?: {
    WebApp?: {
      initData?: string
    }
  }
}

function useTgInitData(): string {
  try {
    return (window as TelegramWebAppWindow).Telegram?.WebApp?.initData || ''
  } catch {
    return ''
  }
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

function formatWaitingHours(waitingHours: number | null): string {
  if (waitingHours == null) return 'Время ожидания не рассчитано'
  if (waitingHours < 1) return 'В очереди меньше часа'
  return `В очереди ${Math.max(1, Math.round(waitingHours))} ч`
}

function resolveUrgency(waitingHours: number | null): {
  tone: 'neutral' | 'warning' | 'danger'
  label: string
} {
  if (waitingHours == null) return { tone: 'neutral', label: 'Без оценки' }
  if (waitingHours >= 24) return { tone: 'danger', label: 'Критично' }
  if (waitingHours >= 4) return { tone: 'warning', label: 'Срочно' }
  return { tone: 'neutral', label: 'На контроле' }
}

function resolveQueueBanner(candidates: Candidate[]): {
  tone: 'info' | 'warning' | 'danger'
  title: string
  text: string
} {
  const criticalCount = candidates.filter(candidate => (candidate.waiting_hours || 0) >= 24).length
  const urgentCount = candidates.filter(candidate => (candidate.waiting_hours || 0) >= 4).length

  if (criticalCount > 0) {
    return {
      tone: 'danger',
      title: `Есть кандидаты с долгим ожиданием`,
      text: `${criticalCount} ${pluralizeCandidates(criticalCount)} ждут 24+ часа. Откройте эти карточки в первую очередь.`,
    }
  }

  if (urgentCount > 0) {
    return {
      tone: 'warning',
      title: 'Очередь требует внимания',
      text: `${urgentCount} ${pluralizeCandidates(urgentCount)} ждут 4+ часа. Следующий шаг: обновить статус после фактического действия.`,
    }
  }

  return {
    tone: 'info',
    title: 'Очередь под контролем',
    text: 'Откройте карточку кандидата и сразу зафиксируйте следующий статус, чтобы очередь и SPA оставались синхронными.',
  }
}

export function TgIncomingPage() {
  const initData = useTgInitData()
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!initData) {
      setError('Откройте экран из Telegram Mini App, чтобы загрузить очередь.')
      setLoading(false)
      return
    }

    apiFetch<{ candidates?: Candidate[]; total?: number }>('/webapp/recruiter/incoming?limit=20', {
      headers: { 'X-Telegram-Init-Data': initData },
    })
      .then(data => {
        setCandidates(data.candidates || [])
        setTotal(data.total || 0)
      })
      .catch((fetchError: unknown) => setError(errorMessage(fetchError)))
      .finally(() => setLoading(false))
  }, [initData])

  if (loading) {
    return (
      <TgStateCard
        eyebrow="Загрузка"
        title="Загружаем входящую очередь"
        text="Подтягиваем кандидатов, статусы и время ожидания."
      />
    )
  }
  if (error) {
    return (
      <TgStateCard
        eyebrow="Ошибка"
        title="Не удалось открыть очередь"
        text={error}
        role="alert"
      />
    )
  }

  const queueBanner = resolveQueueBanner(candidates)

  return (
    <div className="tg-screen">
      <header className="tg-page-header">
        <div className="tg-page-header__top">
          <div>
            <p className="tg-page-header__eyebrow">Очередь Telegram</p>
            <h1 className="tg-page-header__title">Входящие</h1>
            <p className="tg-page-header__subtitle">
              {total > 0
                ? `${total} ${pluralizeCandidates(total)} требуют разбора.`
                : 'Сейчас новых ожиданий нет.'}
            </p>
          </div>
          <Link to="/tg-app" className="tg-inline-link">К сводке</Link>
        </div>
      </header>

      {candidates.length === 0 ? (
        <TgStateCard
          eyebrow="Пусто"
          title="Нет кандидатов в ожидании"
          text="Очередь спокойная. Вернитесь к сводке или откройте экран позже."
        />
      ) : (
        <div className="tg-list">
          <section className={`tg-banner tg-banner--${queueBanner.tone}`} aria-live="polite">
            <p className="tg-banner__eyebrow">Приоритет очереди</p>
            <h2 className="tg-banner__title">{queueBanner.title}</h2>
            <p className="tg-banner__text">{queueBanner.text}</p>
          </section>

          {candidates.map(c => (
            <CandidateCard key={c.id} candidate={c} />
          ))}
        </div>
      )}
    </div>
  )
}

function CandidateCard({ candidate: c }: { candidate: Candidate }) {
  const urgency = resolveUrgency(c.waiting_hours)
  const chipClassName = urgency.tone === 'danger'
    ? 'tg-chip tg-chip--danger'
    : urgency.tone === 'warning'
      ? 'tg-chip tg-chip--warning'
      : 'tg-chip'

  return (
    <Link
      to="/tg-app/candidates/$candidateId"
      params={{ candidateId: String(c.id) }}
      className="tg-candidate-link"
    >
      <article className="tg-candidate-card">
        <div className="tg-candidate-card__top">
          <div>
            <h2 className="tg-candidate-card__name">{c.fio}</h2>
            <p className="tg-candidate-card__meta">
              {c.city || 'Город не указан'} · {c.status_label || 'Статус не указан'}
            </p>
          </div>
          <span className={chipClassName}>{urgency.label}</span>
        </div>

        <p className="tg-candidate-card__body">{formatWaitingHours(c.waiting_hours)}</p>

        <div className="tg-card">
          <p className="tg-card__eyebrow">Следующий шаг</p>
          <p className="tg-card__text">Откройте карточку и зафиксируйте новый статус после действия по кандидату.</p>
        </div>

        <div className="tg-link-card__action">Открыть карточку</div>
      </article>
    </Link>
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
