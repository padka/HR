/**
 * Telegram Mini App — Candidate detail view.
 * Shows lightweight candidate context and explicit status actions.
 */
import { useEffect, useState } from 'react'
import { Link, useParams } from '@tanstack/react-router'
import { apiFetch } from '@/api/client'
import './surface.css'

interface CandidateDetail {
  id: number
  fio: string
  city: string | null
  phone: string | null
  status: string | null
  status_label: string | null
  transitions: Array<{ status: string; label: string }>
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
  return error instanceof Error ? error.message : 'Не удалось выполнить действие'
}

function resolveStatusNote(transitionsCount: number): string {
  if (transitionsCount > 0) {
    return 'Выберите новый статус сразу после фактического действия, чтобы карточка и очередь оставались синхронными.'
  }

  return 'Сейчас доступных переходов нет. Если работа продолжается, проверьте карточку позже в SPA.'
}

export function TgCandidatePage() {
  const { candidateId } = useParams({ strict: false }) as { candidateId: string }
  const initData = useTgInitData()
  const [candidate, setCandidate] = useState<CandidateDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [pendingStatus, setPendingStatus] = useState<string | null>(null)
  const [statusNotice, setStatusNotice] = useState<{
    tone: 'info' | 'success' | 'danger'
    title: string
    text: string
  } | null>(null)

  useEffect(() => {
    if (!initData || !candidateId) {
      setError('Откройте экран из Telegram Mini App, чтобы загрузить карточку кандидата.')
      setLoading(false)
      return
    }

    apiFetch<CandidateDetail>(`/webapp/recruiter/candidates/${candidateId}`, {
      headers: { 'X-Telegram-Init-Data': initData },
    })
      .then(setCandidate)
      .catch((fetchError: unknown) => setError(errorMessage(fetchError)))
      .finally(() => setLoading(false))
  }, [initData, candidateId])

  const handleStatusChange = async (status: string) => {
    if (!initData || !candidateId || pendingStatus) return
    setPendingStatus(status)
    setStatusNotice({
      tone: 'info',
      title: 'Обновляем статус',
      text: 'Фиксируем изменение и перечитываем карточку кандидата.',
    })

    try {
      await apiFetch(`/webapp/recruiter/candidates/${candidateId}/status`, {
        method: 'POST',
        headers: {
          'X-Telegram-Init-Data': initData,
        },
        body: { status },
      })
      const updated = await apiFetch<CandidateDetail>(`/webapp/recruiter/candidates/${candidateId}`, {
        headers: { 'X-Telegram-Init-Data': initData },
      })
      setCandidate(updated)
      setStatusNotice({
        tone: 'success',
        title: 'Статус обновлён',
        text: updated.status_label
          ? `Текущий статус: ${updated.status_label}.`
          : 'Карточка синхронизирована с сервером.',
      })
    } catch (error: unknown) {
      setStatusNotice({
        tone: 'danger',
        title: 'Не удалось обновить статус',
        text: errorMessage(error),
      })
    } finally {
      setPendingStatus(null)
    }
  }

  if (loading) {
    return (
      <TgStateCard
        eyebrow="Загрузка"
        title="Загружаем карточку кандидата"
        text="Подтягиваем текущий статус и доступные переходы."
      />
    )
  }
  if (error || !candidate) {
    return (
      <TgStateCard
        eyebrow="Ошибка"
        title="Карточка недоступна"
        text={error || 'Кандидат не найден или недоступен в этой сессии.'}
        role="alert"
      />
    )
  }

  return (
    <div className="tg-screen">
      <header className="tg-page-header">
        <div className="tg-page-header__top">
          <div>
            <p className="tg-page-header__eyebrow">Карточка кандидата</p>
            <h1 className="tg-page-header__title">{candidate.fio}</h1>
            <p className="tg-page-header__subtitle">
              {candidate.city || 'Город не указан'} · {candidate.phone || 'Телефон не указан'}
            </p>
          </div>
          <Link to="/tg-app/incoming" className="tg-inline-link">К очереди</Link>
        </div>
      </header>

      <section className="tg-card">
        <p className="tg-card__eyebrow">Текущий статус</p>
        <div className="tg-chip-row">
          <span className="tg-chip tg-chip--success">{candidate.status_label || 'Статус не указан'}</span>
        </div>
        <p className="tg-card__text">{resolveStatusNote(candidate.transitions.length)}</p>
      </section>

      <section className="tg-card">
        <p className="tg-card__eyebrow">Следующий шаг</p>
        <h2 className="tg-card__title">
          {candidate.transitions.length > 0 ? 'Выберите новый статус' : 'Доступных переходов нет'}
        </h2>
        <p className="tg-card__text">
          {candidate.transitions.length > 0
            ? 'Статус обновится без перехода на другой экран.'
            : 'Новый статус на этой поверхности сейчас не доступен.'}
        </p>

        {candidate.transitions.length > 0 ? (
          <div className="tg-actions">
            {candidate.transitions.map((transition, index) => (
              <button
                key={transition.status}
                type="button"
                onClick={() => handleStatusChange(transition.status)}
                disabled={pendingStatus !== null}
                className={`tg-button ${index === 0 ? 'tg-button--primary' : ''}`}
              >
                {pendingStatus === transition.status ? 'Обновляем…' : transition.label}
              </button>
            ))}
          </div>
        ) : null}
      </section>

      {statusNotice ? (
        <section className={`tg-banner tg-banner--${statusNotice.tone}`} aria-live="polite">
          <p className="tg-banner__eyebrow">Статус действия</p>
          <h2 className="tg-banner__title">{statusNotice.title}</h2>
          <p className="tg-banner__text">{statusNotice.text}</p>
        </section>
      ) : null}
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
