import { useNavigate, useParams } from '@tanstack/react-router'
import { startTransition, useEffect, useState } from 'react'

import {
  exchangeCandidatePortalToken,
  fetchCandidatePortalJourney,
  parseCandidatePortalError,
} from '@/api/candidate'
import { queryClient } from '@/api/client'
import {
  markCandidateWebAppReady,
  persistCandidatePortalAccessToken,
  resolveCandidatePortalToken,
} from './webapp'
import '../candidate-portal.css'

export function CandidateStartPage() {
  const { token } = useParams({ strict: false }) as { token?: string }
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [errorState, setErrorState] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    const run = async () => {
      setError(null)
      setErrorState(null)
      markCandidateWebAppReady()
      const resolvedToken = resolveCandidatePortalToken(token)
      if (!resolvedToken) {
        try {
          const payload = await fetchCandidatePortalJourney()
          if (cancelled) return
          queryClient.setQueryData(['candidate-portal-journey'], payload)
          startTransition(() => {
            void navigate({ to: '/candidate/journey' })
          })
        } catch (fallbackError) {
          if (cancelled) return
          const info = parseCandidatePortalError(fallbackError)
          setError(info?.message || 'Ссылка не содержит токен доступа. Откройте её заново из сообщения рекрутера.')
          setErrorState(info?.state || null)
        }
        return
      }
      try {
        const payload = await exchangeCandidatePortalToken(resolvedToken)
        if (cancelled) return
        persistCandidatePortalAccessToken(resolvedToken)
        queryClient.setQueryData(['candidate-portal-journey'], payload)
        startTransition(() => {
          void navigate({ to: '/candidate/journey' })
        })
      } catch (err) {
        if (cancelled) return
        const status = err instanceof Error && 'status' in err ? Number((err as { status?: number }).status) : undefined
        if (status === 401 || status === 422) {
          try {
            const payload = await fetchCandidatePortalJourney()
            if (cancelled) return
            queryClient.setQueryData(['candidate-portal-journey'], payload)
            startTransition(() => {
              void navigate({ to: '/candidate/journey' })
            })
            return
          } catch (fallbackError) {
            if (cancelled) return
            const info = parseCandidatePortalError(fallbackError)
            setError(info?.message || 'Ссылка для кабинета повреждена или неполная. Откройте новую ссылку из MAX.')
            setErrorState(info?.state || null)
            return
          }
        }
        const info = parseCandidatePortalError(err)
        setError(info?.message || 'Не удалось открыть ссылку.')
        setErrorState(info?.state || null)
      }
    }

    void run()
    return () => {
      cancelled = true
    }
  }, [navigate, token])

  return (
    <div className="candidate-portal">
      <div className="candidate-portal__loader">
        <div className="glass glass--elevated candidate-portal__card">
          <div className="candidate-portal__eyebrow">Candidate Portal</div>
          <h1 className="candidate-portal__title">
            {error
              ? errorState === 'blocked'
                ? 'Доступ к кабинету недоступен'
                : errorState === 'recoverable'
                  ? 'Сессия кабинета истекла'
                : errorState === 'needs_new_link'
                  ? 'Нужна новая ссылка'
                  : 'Не удалось восстановить кабинет'
              : 'Открываю вашу анкету'}
          </h1>
          <p className="candidate-portal__subtitle">
            {error
              ? errorState === 'blocked'
                ? 'Сессия отозвана или кабинет не найден. Попросите рекрутера восстановить доступ.'
                : errorState === 'recoverable'
                  ? 'Откройте кабинет заново из MAX или Telegram. Если resume-cookie ещё жив, доступ поднимется автоматически.'
                  : errorState === 'needs_new_link'
                  ? 'Старая ссылка устарела. Откройте свежую ссылку из MAX или Telegram.'
                  : 'Сейчас попробую открыть кабинет заново на этом устройстве.'
              : 'Проверяю ссылку, поднимаю кабинет и восстанавливаю прогресс прохождения.'}
          </p>
          {error ? <p className="candidate-portal__error">{error}</p> : null}
          {error ? (
            <div className="candidate-portal__actions" style={{ justifyContent: 'center' }}>
              <button className="ui-btn ui-btn--primary" onClick={() => window.location.reload()}>
                Повторить
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
