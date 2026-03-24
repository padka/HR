import { useNavigate, useParams } from '@tanstack/react-router'
import { startTransition, useEffect, useState } from 'react'

import { exchangeCandidatePortalToken, fetchCandidatePortalJourney } from '@/api/candidate'
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

  useEffect(() => {
    let cancelled = false

    const run = async () => {
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
          const message = fallbackError instanceof Error ? fallbackError.message : ''
          setError(message || 'Ссылка не содержит токен доступа. Откройте её заново из сообщения рекрутера.')
        }
        return
      }
      persistCandidatePortalAccessToken(resolvedToken)
      try {
        const payload = await exchangeCandidatePortalToken(resolvedToken)
        if (cancelled) return
        queryClient.setQueryData(['candidate-portal-journey'], payload)
        startTransition(() => {
          void navigate({ to: '/candidate/journey' })
        })
      } catch (err) {
        if (cancelled) return
        const status = err instanceof Error && 'status' in err ? Number((err as { status?: number }).status) : undefined
        if (status === 422) {
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
            const message = fallbackError instanceof Error ? fallbackError.message : ''
            setError(message || 'Ссылка для кабинета повреждена или неполная. Откройте новую ссылку из MAX.')
            return
          }
        }
        const message = err instanceof Error ? err.message : ''
        setError(message || 'Не удалось открыть ссылку.')
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
          <h1 className="candidate-portal__title">Открываю вашу анкету</h1>
          <p className="candidate-portal__subtitle">
            Проверяю ссылку, поднимаю кабинет и восстанавливаю прогресс прохождения.
          </p>
          {error ? <p className="candidate-portal__error">{error}</p> : null}
        </div>
      </div>
    </div>
  )
}
