import { useNavigate, useParams } from '@tanstack/react-router'
import { startTransition, useEffect, useMemo, useState } from 'react'

import {
  exchangeCandidatePortalToken,
  fetchCandidatePortalJourney,
  parseCandidatePortalError,
  resolveCandidateEntryGateway,
  selectCandidateEntryChannel,
  type CandidateEntryChannel,
  type CandidateEntryGatewayResponse,
} from '@/api/candidate'
import { queryClient } from '@/api/client'
import {
  clearCandidatePortalAccessToken,
  persistCandidatePortalEntryTokenFromUrl,
  readCandidatePortalEntryToken,
  writeCandidatePortalEntryToken,
} from '@/shared/candidate-portal-session'
import {
  ensureCandidateWebAppBridge,
  hasCandidatePortalLocationToken,
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
  const [entryGateway, setEntryGateway] = useState<CandidateEntryGatewayResponse | null>(null)
  const [entryPendingChannel, setEntryPendingChannel] = useState<CandidateEntryChannel | null>(null)

  const entryToken = useMemo(() => {
    if (typeof window === 'undefined') return ''
    return new URLSearchParams(window.location.search).get('entry')?.trim() || ''
  }, [])
  const recoveryEntryToken = useMemo(
    () => entryToken || readCandidatePortalEntryToken(),
    [entryToken],
  )
  const recoveryEntryUrl = useMemo(
    () => (recoveryEntryToken ? `/candidate/start?entry=${encodeURIComponent(recoveryEntryToken)}` : '/candidate/start'),
    [recoveryEntryToken],
  )

  useEffect(() => {
    let cancelled = false

    const run = async () => {
      setError(null)
      setErrorState(null)
      setEntryGateway(null)
      setEntryPendingChannel(null)

      const recoverWithEntryToken = async () => {
        const fallbackEntryToken = entryToken || readCandidatePortalEntryToken()
        if (!fallbackEntryToken) return false
        try {
          const payload = await resolveCandidateEntryGateway(fallbackEntryToken)
          if (cancelled) return true
          writeCandidatePortalEntryToken(fallbackEntryToken)
          setEntryGateway(payload)
          setError(null)
          setErrorState(null)
          return true
        } catch {
          return false
        }
      }

      if (entryToken) {
        try {
          const payload = await resolveCandidateEntryGateway(entryToken)
          if (cancelled) return
          writeCandidatePortalEntryToken(entryToken)
          setEntryGateway(payload)
          return
        } catch (gatewayError) {
          if (cancelled) return
          const info = parseCandidatePortalError(gatewayError)
          setError(info?.message || 'Не удалось подготовить варианты входа. Попробуйте открыть кабинет на этом устройстве ещё раз.')
          setErrorState(info?.state || null)
          return
        }
      }
      if (!hasCandidatePortalLocationToken(token)) {
        await ensureCandidateWebAppBridge()
      }
      markCandidateWebAppReady()
      const resolvedToken = resolveCandidatePortalToken(token)
      if (!resolvedToken.token) {
        try {
          const payload = await fetchCandidatePortalJourney()
          if (cancelled) return
          persistCandidatePortalEntryTokenFromUrl(payload.candidate?.entry_url)
          queryClient.setQueryData(['candidate-portal-journey'], payload)
          startTransition(() => {
            void navigate({ to: '/candidate/journey' })
          })
        } catch (fallbackError) {
          if (cancelled) return
          if (await recoverWithEntryToken()) {
            return
          }
          const info = parseCandidatePortalError(fallbackError)
          setError(info?.message || 'Не удалось восстановить доступ автоматически.')
          setErrorState(info?.state || null)
        }
        return
      }
      try {
        const payload = await exchangeCandidatePortalToken(resolvedToken.token)
        if (cancelled) return
        persistCandidatePortalEntryTokenFromUrl(payload.candidate?.entry_url)
        persistCandidatePortalAccessToken(resolvedToken.token)
        queryClient.setQueryData(['candidate-portal-journey'], payload)
        startTransition(() => {
          void navigate({ to: '/candidate/journey' })
        })
      } catch (err) {
        if (cancelled) return
        const status = err instanceof Error && 'status' in err ? Number((err as { status?: number }).status) : undefined
        if (status === 401 || status === 422) {
          const initialError = parseCandidatePortalError(err)
          const shouldSkipStoredToken = resolvedToken.direct
          if (shouldSkipStoredToken) {
            clearCandidatePortalAccessToken()
          }
          try {
            const payload = await fetchCandidatePortalJourney({
              skipStoredPortalToken: shouldSkipStoredToken,
            })
            if (cancelled) return
            persistCandidatePortalEntryTokenFromUrl(payload.candidate?.entry_url)
            queryClient.setQueryData(['candidate-portal-journey'], payload)
            startTransition(() => {
              void navigate({ to: '/candidate/journey' })
            })
            return
          } catch (fallbackError) {
            if (cancelled) return
            if (await recoverWithEntryToken()) {
              return
            }
            const info = shouldSkipStoredToken ? initialError : parseCandidatePortalError(fallbackError)
            setError(info?.message || 'Не удалось восстановить кабинет автоматически.')
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
  }, [entryToken, navigate, token])

  const handleSelectEntryChannel = async (channel: CandidateEntryChannel) => {
    if (!entryToken) return
    setEntryPendingChannel(channel)
    setError(null)
    try {
      const payload = await selectCandidateEntryChannel(entryToken, channel)
      const launchUrl = String(payload.launch?.url || payload.cabinet_url || '').trim()
      if (!launchUrl) {
        setError('Ссылка для запуска канала пока не подготовлена. Продолжайте через веб-кабинет.')
        setEntryPendingChannel(null)
        return
      }
      window.location.assign(launchUrl)
    } catch (selectError) {
      const info = parseCandidatePortalError(selectError)
      setError(info?.message || 'Не удалось запустить выбранный канал. Попробуйте ещё раз или продолжайте через веб-кабинет.')
      setErrorState(info?.state || null)
      setEntryPendingChannel(null)
    }
  }

  return (
    <div className="candidate-portal">
      <div className="candidate-portal__loader">
        <div className="glass glass--elevated candidate-portal__card">
          <div className="candidate-portal__eyebrow">Candidate Portal</div>
          <h1 className="candidate-portal__title">
            {entryGateway
              ? 'Выберите, где продолжить общение'
              : error
                ? errorState === 'blocked'
                  ? 'Доступ к кабинету недоступен'
                  : errorState === 'recoverable'
                    ? 'Восстанавливаю доступ'
                    : errorState === 'needs_new_link'
                      ? 'Продолжим через выбор канала'
                      : 'Не удалось восстановить кабинет'
                : 'Открываю ваш кабинет'}
          </h1>
          <p className="candidate-portal__subtitle">
            {entryGateway
              ? entryGateway.journey.next_action || 'Можно продолжить в браузере, MAX или Telegram без потери прогресса.'
              : error
                ? errorState === 'blocked'
                  ? 'Кабинет сейчас недоступен в текущем режиме. Попробуйте вернуться к выбору способа входа.'
                  : errorState === 'recoverable'
                    ? 'Пробую вернуть вас в кабинет на этом устройстве без потери прогресса.'
                    : errorState === 'needs_new_link'
                      ? 'Текущий вход устарел, поэтому вернёмся к выбору Web, MAX или Telegram.'
                      : 'Сейчас попробую открыть кабинет заново на этом устройстве.'
                : 'Проверяю ссылку, поднимаю кабинет и восстанавливаю прогресс прохождения.'}
          </p>
          {error ? <p className="candidate-portal__error">{error}</p> : null}
          {entryGateway ? (
            <div className="candidate-portal__section-stack" style={{ marginTop: 18, textAlign: 'left' }}>
              <div className="candidate-portal__summary-grid" aria-label="Входной контекст">
                <article className="glass candidate-portal__summary-card">
                  <div className="candidate-portal__summary-label">Кандидат</div>
                  <div className="candidate-portal__summary-value">{entryGateway.candidate.fio || 'Кандидат'}</div>
                  <div className="candidate-portal__summary-meta">{entryGateway.candidate.city || 'Город уточняется'}</div>
                </article>
                <article className="glass candidate-portal__summary-card">
                  <div className="candidate-portal__summary-label">Вакансия</div>
                  <div className="candidate-portal__summary-value">{entryGateway.candidate.vacancy_label || 'Вакансия уточняется'}</div>
                  <div className="candidate-portal__summary-meta">{entryGateway.candidate.company || 'Компания'}</div>
                </article>
                <article className="glass candidate-portal__summary-card">
                  <div className="candidate-portal__summary-label">Этап</div>
                  <div className="candidate-portal__summary-value">{entryGateway.journey.current_step_label || 'В обработке'}</div>
                  <div className="candidate-portal__summary-meta">{entryGateway.journey.status_label || 'Статус обновляется автоматически'}</div>
                </article>
              </div>

              {entryGateway.company_preview?.summary ? (
                <div className="candidate-portal__resource-card">
                  <strong>Что дальше</strong>
                  <p>{entryGateway.company_preview.summary}</p>
                  <div className="candidate-portal__summary-tags">
                    {(entryGateway.company_preview.highlights || []).map((item) => (
                      <span key={item} className="candidate-portal__summary-tag">{item}</span>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="candidate-portal__resource-list">
                {(['web', 'max', 'telegram'] as CandidateEntryChannel[]).map((channel) => {
                  const option = entryGateway.options[channel]
                  const title =
                    channel === 'web' ? 'Продолжить в Web' : channel === 'max' ? 'Продолжить в MAX' : 'Продолжить в Telegram'
                  return (
                    <div key={channel} className="candidate-portal__resource-card">
                      <div className="candidate-portal__message-head">
                        <strong>{title}</strong>
                        <span className="candidate-portal__message-channel">
                          {option?.enabled ? 'ready' : 'blocked'}
                        </span>
                      </div>
                      <p>
                        {channel === 'web'
                          ? 'Открывает основной кабинет кандидата в браузере.'
                          : 'Запускает тот же процесс через бот и ведёт в тот же кабинет.'}
                      </p>
                      {option?.reason_if_blocked ? (
                        <p className="candidate-portal__helper">{option.reason_if_blocked}</p>
                      ) : null}
                      <div className="candidate-portal__actions">
                        <button
                          type="button"
                          className={`ui-btn ${channel === 'web' ? 'ui-btn--primary' : 'ui-btn--ghost'}`}
                          disabled={!option?.enabled || entryPendingChannel !== null}
                          onClick={() => handleSelectEntryChannel(channel)}
                        >
                          {entryPendingChannel === channel ? 'Открываю…' : title}
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ) : null}
          {error ? (
            <div className="candidate-portal__actions" style={{ justifyContent: 'center' }}>
              <button className="ui-btn ui-btn--primary" onClick={() => window.location.reload()}>
                Повторить
              </button>
              <a className="ui-btn ui-btn--ghost" href={recoveryEntryUrl}>
                Вернуться к выбору способа входа
              </a>
            </div>
          ) : null}
          {error ? (
            <p className="candidate-portal__helper" style={{ textAlign: 'center', marginTop: 12 }}>
              {recoveryEntryToken
                ? 'Использую сохранённый вход на этом устройстве, чтобы вернуть вас к выбору Web, MAX или Telegram.'
                : 'Если автоматическое восстановление не сработало, вернитесь на стартовую страницу и продолжите через удобный канал.'}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  )
}
