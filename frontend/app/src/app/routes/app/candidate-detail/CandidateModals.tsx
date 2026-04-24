import { useEffect, useMemo, useState } from 'react'
import type { CandidateDetail, TestSection } from '@/api/services/candidates'
import { ApiErrorBanner } from '@/app/components/ApiErrorBanner'
import { ModalPortal } from '@/shared/components/ModalPortal'
import { formatDateTime, formatSecondsToMinutes, formatTzOffset, getTomorrowDate } from '@/shared/utils/formatters'
import { browserTimeZone, buildSlotTimePreview } from '@/app/lib/timezonePreview'
import { useCandidateActions, useCandidateHh, useCitiesOptions } from './candidate-detail.api'
import type {
  City,
  IntroDayTemplateContext,
  ReportPreviewState,
  TestAttemptPreview,
} from './candidate-detail.types'
import { renderIntroDayTemplate } from './candidate-detail.utils'
import { CandidateTests, TestScoreBar } from './CandidateTests'

type CandidateModalsProps = {
  candidateId: number
  candidate?: CandidateDetail | null
  scheduleSlotOpen: boolean
  scheduleIntroDayOpen: boolean
  rejectState: { actionKey: string; title?: string } | null
  testsOpen: boolean
  testSections: TestSection[]
  hhProfileOpen: boolean
  reportPreview: ReportPreviewState | null
  attemptPreview: TestAttemptPreview | null
  onCloseScheduleSlot: () => void
  onCloseScheduleIntroDay: () => void
  onCloseReject: () => void
  onCloseTests: () => void
  onCloseHhProfile: () => void
  onCloseReportPreview: () => void
  onCloseAttemptPreview: () => void
  onOpenReportPreview: (title: string, url: string) => void
  onOpenAttemptPreview: (testTitle: string, attempt: TestAttemptPreview['attempt']) => void
  onDetailChanged: (message?: string) => void
}

type ReportPreviewModalProps = {
  title: string
  url: string
  onClose: () => void
}

function ReportPreviewModal({ title, url, onClose }: ReportPreviewModalProps) {
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [contentType, setContentType] = useState<string>('')
  const [text, setText] = useState<string>('')
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const controller = new AbortController()
    setStatus('loading')
    setError(null)
    setText('')
    setContentType('')
    setBlobUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })

    // raw fetch: report preview needs direct PDF/text/blob handling, while apiFetch is JSON-oriented.
    fetch(url, { credentials: 'include', signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) {
          const msg = await res.text().catch(() => '')
          throw new Error(msg || res.statusText)
        }
        const ct = res.headers.get('content-type') || ''
        if (!active) return
        setContentType(ct)
        if (ct.includes('application/pdf')) {
          const blob = await res.blob()
          if (!active) return
          const objectUrl = URL.createObjectURL(blob)
          setBlobUrl(objectUrl)
          setStatus('ready')
          return
        }
        const bodyText = await res.text()
        if (!active) return
        setText(bodyText)
        setStatus('ready')
      })
      .catch((err: unknown) => {
        if (!active) return
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(err instanceof Error ? err.message : 'Не удалось загрузить отчёт')
        setStatus('error')
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [url])

  useEffect(() => {
    return () => {
      if (blobUrl) URL.revokeObjectURL(blobUrl)
    }
  }, [blobUrl])

  const isPdf = contentType.includes('application/pdf')

  return (
    <ModalPortal>
      <div className="modal-overlay" onClick={(event) => event.target === event.currentTarget && onClose()} role="dialog" aria-modal="true">
        <div className="glass glass--elevated modal">
          <div className="modal__header">
            <div>
              <h2 className="modal__title">Отчёт · {title}</h2>
              <p className="modal__subtitle">{isPdf ? 'PDF-документ' : 'Текстовый отчёт'}</p>
            </div>
            <div className="report-preview__actions">
              <a href={url} className="ui-btn ui-btn--ghost" target="_blank" rel="noopener">
                Скачать
              </a>
              <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
            </div>
          </div>
          <div className="modal__body">
            {status === 'loading' && <p className="subtitle">Загрузка отчёта...</p>}
            {status === 'error' && <div className="ui-alert ui-alert--error">{error}</div>}
            {status === 'ready' && (
              <div className="report-preview__frame">
                {isPdf && blobUrl ? (
                  <iframe className="report-preview__pdf" title={title} src={blobUrl} />
                ) : (
                  <pre className="report-preview__text">{text || 'Отчёт пустой.'}</pre>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </ModalPortal>
  )
}

function TestAttemptModal({ testTitle, attempt, onClose }: NonNullable<CandidateModalsProps['attemptPreview']> & { onClose: () => void }) {
  const stats = attempt.details?.stats
  const questions = attempt.details?.questions || []
  const totalQuestions = stats?.total_questions ?? questions.length
  const correctAnswers = stats?.correct_answers ?? questions.filter((question) => question.is_correct).length
  const attemptLabel = attempt.id > 0 ? `попытка #${attempt.id}` : 'последний результат'

  return (
    <ModalPortal>
      <div className="modal-overlay" onClick={(event) => event.target === event.currentTarget && onClose()} role="dialog" aria-modal="true">
        <div className="glass glass--elevated modal">
          <div className="modal__header">
            <div>
              <h2 className="modal__title">{testTitle} · {attemptLabel}</h2>
              <p className="modal__subtitle">
                {formatDateTime(attempt.completed_at)}
                {attempt.source ? ` · ${attempt.source}` : ''}
              </p>
            </div>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
          </div>
          <div className="modal__body">
            <div className="cd-test-attempt-modal__summary">
              <TestScoreBar
                correct={correctAnswers}
                total={totalQuestions}
                score={stats?.final_score ?? attempt.final_score}
              />
              <div className="cd-test-card__extra">
                <span>Сырые: {typeof (stats?.raw_score ?? attempt.raw_score) === 'number' ? (stats?.raw_score ?? attempt.raw_score) : '—'}</span>
                <span>Время: {formatSecondsToMinutes(stats?.total_time)}</span>
                <span>Просрочено: {stats?.overtime_questions ?? 0}</span>
              </div>
            </div>
            {questions.length === 0 ? (
              <p className="subtitle">Для этой попытки нет подробных ответов.</p>
            ) : (
              <div className="cd-test-attempt-modal__questions">
                {questions.map((question, index) => (
                  <div key={`${attempt.id}-${question.question_index ?? index}`} className="glass cd-test-attempt-question">
                    <div className="cd-test-attempt-question__header">
                      <span>Вопрос {question.question_index ?? index + 1}</span>
                      <span className={`cd-chip cd-chip--small ${question.is_correct ? 'cd-chip--success' : 'cd-chip--danger'}`}>
                        {question.is_correct ? 'Верно' : 'Неверно'}
                      </span>
                    </div>
                    {question.question_text && <div className="cd-test-attempt-question__prompt">{question.question_text}</div>}
                    <div className="cd-test-attempt-question__body">
                      <div>
                        <div className="cd-test-attempt-question__label">Ответ кандидата</div>
                        <div className="cd-test-attempt-question__text">{question.user_answer || '—'}</div>
                      </div>
                      <div>
                        <div className="cd-test-attempt-question__label">Ожидаемый ответ</div>
                        <div className="cd-test-attempt-question__text">{question.correct_answer || '—'}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </ModalPortal>
  )
}

function TestsModal({
  testSections,
  onClose,
  onOpenReportPreview,
  onOpenAttemptPreview,
}: {
  testSections: TestSection[]
  onClose: () => void
  onOpenReportPreview: (title: string, url: string) => void
  onOpenAttemptPreview: (testTitle: string, attempt: TestAttemptPreview['attempt']) => void
}) {
  return (
    <ModalPortal>
      <div className="modal-overlay" onClick={(event) => event.target === event.currentTarget && onClose()} role="dialog" aria-modal="true">
        <div className="glass glass--elevated modal cd-modal cd-modal--wide">
          <div className="modal__header">
            <div>
              <h2 className="modal__title">Тесты кандидата</h2>
              <p className="modal__subtitle">Все попытки, баллы и подробные отчёты в одном окне.</p>
            </div>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
          </div>
          <div className="modal__body">
            <CandidateTests
              embedded
              testSections={testSections}
              onOpenReportPreview={onOpenReportPreview}
              onOpenAttemptPreview={onOpenAttemptPreview}
            />
          </div>
        </div>
      </div>
    </ModalPortal>
  )
}

function HhResumeModal({
  candidateId,
  candidate,
  onClose,
}: {
  candidateId: number
  candidate?: CandidateDetail | null
  onClose: () => void
}) {
  const hhSummaryQuery = useCandidateHh(candidateId, true)
  const hhSummary = hhSummaryQuery.data
  const resumeUrl = hhSummary?.resume?.url || candidate?.hh_profile_url || null
  const vacancyTitle = hhSummary?.vacancy?.title || '—'
  const resumeTitle = hhSummary?.resume?.title || hhSummary?.resume?.id || 'Резюме не найдено'
  const negotiationState = hhSummary?.negotiation?.employer_state || '—'

  return (
    <ModalPortal>
      <div className="modal-overlay" onClick={(event) => event.target === event.currentTarget && onClose()} role="dialog" aria-modal="true">
        <div className="glass glass--elevated modal cd-modal cd-modal--wide">
          <div className="modal__header">
            <div>
              <h2 className="modal__title">Резюме HeadHunter</h2>
              <p className="modal__subtitle">Быстрый просмотр профиля кандидата внутри RecruitSmart.</p>
            </div>
            <div className="report-preview__actions">
              {resumeUrl ? (
                <a href={resumeUrl} className="ui-btn ui-btn--ghost" target="_blank" rel="noopener">
                  Открыть в HH
                </a>
              ) : null}
              <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
            </div>
          </div>
          <div className="modal__body cd-hh-modal">
            {hhSummaryQuery.isPending ? (
              <p className="subtitle">Загрузка резюме HH...</p>
            ) : hhSummaryQuery.isError ? (
              <ApiErrorBanner
                title="Не удалось загрузить данные HH"
                error={hhSummaryQuery.error}
                onRetry={() => hhSummaryQuery.refetch()}
              />
            ) : (
              <>
                <div className="cd-hh-modal__summary">
                  <div className="cd-hh-card">
                    <div className="cd-hh-card__label">Резюме</div>
                    <div className="cd-hh-card__value">{resumeTitle}</div>
                  </div>
                  <div className="cd-hh-card">
                    <div className="cd-hh-card__label">Вакансия</div>
                    <div className="cd-hh-card__value">{vacancyTitle}</div>
                  </div>
                  <div className="cd-hh-card">
                    <div className="cd-hh-card__label">Статус переговоров</div>
                    <div className="cd-hh-card__value">{negotiationState}</div>
                  </div>
                </div>
                {resumeUrl ? (
                  <div className="report-preview__frame cd-hh-modal__frame">
                    <iframe
                      className="cd-hh-modal__iframe"
                      title="HeadHunter resume preview"
                      src={resumeUrl}
                    />
                  </div>
                ) : (
                  <div className="ui-alert ui-alert--info">
                    У резюме нет прямой ссылки для предпросмотра внутри системы.
                  </div>
                )}
                <p className="subtitle">
                  Если HH запрещает встраивание, используйте кнопку «Открыть в HH».
                </p>
              </>
            )}
          </div>
        </div>
      </div>
    </ModalPortal>
  )
}

function ScheduleSlotModal({
  candidateId,
  candidateFio,
  candidateCity,
  onClose,
  onSuccess,
}: {
  candidateId: number
  candidateFio: string
  candidateCity?: string | null
  onClose: () => void
  onSuccess: () => void
}) {
  const [form, setForm] = useState({
    date: getTomorrowDate(),
    time: '10:00',
    custom_message: '',
  })
  const [resolvedCityId, setResolvedCityId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const citiesQuery = useCitiesOptions()
  const { scheduleInterviewMutation } = useCandidateActions(candidateId)
  const cities = useMemo(() => citiesQuery.data || [], [citiesQuery.data])

  useEffect(() => {
    if (candidateCity && cities.length > 0 && resolvedCityId === null) {
      const match = cities.find((city) => city.name.toLowerCase() === candidateCity.toLowerCase())
      if (match) {
        setResolvedCityId(match.id)
      }
    }
  }, [candidateCity, cities, resolvedCityId])

  const selectedCity = useMemo(() => cities.find((city) => city.id === resolvedCityId), [cities, resolvedCityId])
  const cityTz = selectedCity?.tz || 'Europe/Moscow'
  const recruiterTz = browserTimeZone()
  const slotPreview = useMemo(
    () => buildSlotTimePreview(form.date, form.time, recruiterTz, cityTz),
    [form.date, form.time, recruiterTz, cityTz],
  )

  const canSubmit = resolvedCityId && form.date && form.time

  return (
    <ModalPortal>
      <div className="modal-overlay" onClick={(event) => event.target === event.currentTarget && onClose()} role="dialog" aria-modal="true">
        <div className="glass glass--elevated modal modal--md">
          <div className="modal__header">
            <div>
              <h2 className="modal__title">Предложить время собеседования</h2>
              <p className="modal__subtitle">Кандидат: <strong>{candidateFio}</strong></p>
            </div>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
          </div>
          {error && <div className="ui-alert ui-alert--error">{error}</div>}
          <div className="modal__body">
            <p className="text-muted text-sm subtitle--mt-0">
              Кандидату придёт предложение времени. После подтверждения отправится приглашение на собеседование.
            </p>
            <div className="form-grid">
              {selectedCity && (
                <div className="form-group">
                  <span className="form-group__label">Город</span>
                  <span>{selectedCity.name} — {cityTz} ({formatTzOffset(cityTz)})</span>
                </div>
              )}
              <div className="form-row">
                <label className="form-group">
                  <span className="form-group__label">Дата</span>
                  <input type="date" value={form.date} onChange={(event) => setForm({ ...form, date: event.target.value })} />
                </label>
                <label className="form-group">
                  <span className="form-group__label">Время ({recruiterTz})</span>
                  <input type="time" value={form.time} onChange={(event) => setForm({ ...form, time: event.target.value })} />
                </label>
              </div>
              {slotPreview && (
                <div className="glass slot-preview">
                  <div>
                    <div className="slot-preview__label">Вы вводите (ваша TZ)</div>
                    <div className="slot-preview__value">{slotPreview.recruiterLabel}</div>
                    <div className="slot-preview__hint">{slotPreview.recruiterTz}</div>
                  </div>
                  <div>
                    <div className="slot-preview__label">Кандидат увидит</div>
                    <div className="slot-preview__value">{slotPreview.candidateLabel}</div>
                    <div className="slot-preview__hint">{slotPreview.candidateTz}</div>
                  </div>
                </div>
              )}
              <label className="form-group">
                <span className="form-group__label">Сообщение кандидату (опционально)</span>
                <textarea
                  rows={3}
                  value={form.custom_message}
                  onChange={(event) => setForm({ ...form, custom_message: event.target.value })}
                  placeholder="Например: Мы предлагаем собеседование в это время. Подойдёт ли вам?"
                />
              </label>
            </div>
          </div>
          <div className="modal__footer">
            <button
              className="ui-btn ui-btn--primary"
              onClick={() => scheduleInterviewMutation.mutate({
                city_id: resolvedCityId,
                date: form.date,
                time: form.time,
                custom_message: form.custom_message || null,
              }, {
                onSuccess: () => {
                  onSuccess()
                  onClose()
                },
                onError: (err) => {
                  setError((err as Error).message)
                },
              })}
              disabled={!canSubmit || scheduleInterviewMutation.isPending}
            >
              {scheduleInterviewMutation.isPending ? 'Отправляем...' : 'Отправить предложение'}
            </button>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Отмена</button>
          </div>
        </div>
      </div>
    </ModalPortal>
  )
}

function ScheduleIntroDayModal({
  candidateId,
  candidateFio,
  candidateCity,
  introDayTemplate,
  introDayTemplateContext,
  onClose,
  onSuccess,
}: {
  candidateId: number
  candidateFio: string
  candidateCity?: string | null
  introDayTemplate?: string | null
  introDayTemplateContext?: IntroDayTemplateContext | null
  onClose: () => void
  onSuccess: () => void
}) {
  const [form, setForm] = useState({
    date: getTomorrowDate(),
    time: '10:00',
    customMessage: '',
  })
  const [error, setError] = useState<string | null>(null)
  const [template, setTemplate] = useState<string>('')
  const recruiterTz = browserTimeZone()
  const citiesQuery = useCitiesOptions()
  const { scheduleIntroDayMutation } = useCandidateActions(candidateId)

  const introCityTz = useMemo(() => {
    const cities = (citiesQuery.data || []) as City[]
    if (!candidateCity) return 'Europe/Moscow'
    const match = cities.find((city) => city.name.toLowerCase() === candidateCity.toLowerCase())
    return match?.tz || 'Europe/Moscow'
  }, [citiesQuery.data, candidateCity])

  useEffect(() => {
    if (!introDayTemplate) {
      setTemplate('')
      return
    }
    setTemplate(introDayTemplate)
    setForm((prev) => ({
      ...prev,
      customMessage: renderIntroDayTemplate(
        introDayTemplate,
        candidateFio,
        prev.date,
        prev.time,
        introDayTemplateContext,
      ),
    }))
  }, [candidateFio, introDayTemplate, introDayTemplateContext])

  useEffect(() => {
    if (!template) return
    setForm((prev) => ({
      ...prev,
      customMessage: renderIntroDayTemplate(
        template,
        candidateFio,
        prev.date,
        prev.time,
        introDayTemplateContext,
      ),
    }))
  }, [candidateFio, form.date, form.time, introDayTemplateContext, template])

  const introPreview = useMemo(
    () => buildSlotTimePreview(form.date, form.time, recruiterTz, introCityTz),
    [form.date, form.time, recruiterTz, introCityTz],
  )

  return (
    <ModalPortal>
      <div className="modal-overlay" onClick={(event) => event.target === event.currentTarget && onClose()} role="dialog" aria-modal="true">
        <div className="glass glass--elevated modal modal--sm">
          <div className="modal__header">
            <div>
              <h2 className="modal__title">Назначить ознакомительный день</h2>
              <p className="modal__subtitle">
                Кандидат: <strong>{candidateFio}</strong>
                {candidateCity && <><br />Город: {candidateCity}</>}
              </p>
            </div>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
          </div>
          {error && <div className="ui-alert ui-alert--error">{error}</div>}
          <div className="modal__body">
            <div className="form-row">
              <label className="form-group">
                <span className="form-group__label">Дата</span>
                <input type="date" value={form.date} onChange={(event) => setForm({ ...form, date: event.target.value })} />
              </label>
              <label className="form-group">
                <span className="form-group__label">Время ({recruiterTz})</span>
                <input type="time" value={form.time} onChange={(event) => setForm({ ...form, time: event.target.value })} />
              </label>
            </div>
            {introPreview && (
              <div className="glass slot-preview">
                <div>
                  <div className="slot-preview__label">Вы вводите (ваша TZ)</div>
                  <div className="slot-preview__value">{introPreview.recruiterLabel}</div>
                  <div className="slot-preview__hint">{introPreview.recruiterTz}</div>
                </div>
                <div>
                  <div className="slot-preview__label">Кандидат увидит</div>
                  <div className="slot-preview__value">{introPreview.candidateLabel}</div>
                  <div className="slot-preview__hint">{introPreview.candidateTz}</div>
                </div>
              </div>
            )}
            <label className="form-group form-group--mt">
              <span className="form-group__label">Сообщение кандидату</span>
              <textarea
                rows={6}
                value={form.customMessage}
                onChange={(event) => setForm({ ...form, customMessage: event.target.value })}
                placeholder="Текст приглашения..."
                className="ui-input ui-input--multiline"
              />
            </label>
            <p className="subtitle subtitle--mt-sm">Адрес и контакт руководителя будут взяты из шаблона города.</p>
          </div>
          <div className="modal__footer">
            <button
              className="ui-btn ui-btn--primary"
              onClick={() => scheduleIntroDayMutation.mutate({
                date: form.date,
                time: form.time,
                custom_message: form.customMessage,
              }, {
                onSuccess: () => {
                  onSuccess()
                  onClose()
                },
                onError: (err) => {
                  setError((err as Error).message)
                },
              })}
              disabled={!form.date || !form.time || scheduleIntroDayMutation.isPending}
            >
              {scheduleIntroDayMutation.isPending ? 'Назначаем...' : 'Назначить ОД'}
            </button>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Отмена</button>
          </div>
        </div>
      </div>
    </ModalPortal>
  )
}

function RejectModal({
  candidateId,
  actionKey,
  title,
  onClose,
  onSuccess,
}: {
  candidateId: number
  actionKey: string
  title?: string
  onClose: () => void
  onSuccess: () => void
}) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const { actionMutation } = useCandidateActions(candidateId)

  return (
    <ModalPortal>
      <div className="modal-overlay" onClick={(event) => event.target === event.currentTarget && onClose()} role="dialog" aria-modal="true">
        <div className="glass glass--elevated modal modal--sm">
          <div className="modal__header">
            <h2 className="modal__title">{title || 'Укажите причину отказа'}</h2>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
          </div>
          <div className="modal__body">
            {error && <p className="subtitle subtitle--danger">{error}</p>}
            <textarea
              rows={4}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Причина отказа..."
              className="ui-input ui-input--multiline"
              autoFocus
            />
          </div>
          <div className="modal__footer">
            <button
              className="ui-btn ui-btn--danger"
              onClick={() => {
                actionMutation
                  .mutateAsync({ actionKey, payload: { reason } })
                  .then(() => {
                    onSuccess()
                    onClose()
                  })
                  .catch((err: unknown) => {
                    setError((err as Error).message)
                  })
              }}
              disabled={!reason.trim() || actionMutation.isPending}
            >
              {actionMutation.isPending ? 'Сохраняем...' : 'Подтвердить отказ'}
            </button>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Отмена</button>
          </div>
        </div>
      </div>
    </ModalPortal>
  )
}

export function CandidateModals({
  candidateId,
  candidate,
  scheduleSlotOpen,
  scheduleIntroDayOpen,
  rejectState,
  testsOpen,
  testSections,
  hhProfileOpen,
  reportPreview,
  attemptPreview,
  onCloseScheduleSlot,
  onCloseScheduleIntroDay,
  onCloseReject,
  onCloseTests,
  onCloseHhProfile,
  onCloseReportPreview,
  onCloseAttemptPreview,
  onOpenReportPreview,
  onOpenAttemptPreview,
  onDetailChanged,
}: CandidateModalsProps) {
  return (
    <>
      {scheduleSlotOpen && candidate && (
        <ScheduleSlotModal
          candidateId={candidateId}
          candidateFio={candidate.fio || `Кандидат #${candidateId}`}
          candidateCity={candidate.city}
          onClose={onCloseScheduleSlot}
          onSuccess={() => onDetailChanged('Предложение отправлено кандидату')}
        />
      )}

      {scheduleIntroDayOpen && candidate && (
        <ScheduleIntroDayModal
          candidateId={candidateId}
          candidateFio={candidate.fio || 'Кандидат'}
          candidateCity={candidate.city}
          introDayTemplate={candidate.intro_day_template}
          introDayTemplateContext={candidate.intro_day_template_context}
          onClose={onCloseScheduleIntroDay}
          onSuccess={() => onDetailChanged('Ознакомительный день назначен')}
        />
      )}

      {rejectState && (
        <RejectModal
          candidateId={candidateId}
          actionKey={rejectState.actionKey}
          title={rejectState.title}
          onClose={onCloseReject}
          onSuccess={() => onDetailChanged()}
        />
      )}

      {testsOpen && (
        <TestsModal
          testSections={testSections}
          onClose={onCloseTests}
          onOpenReportPreview={onOpenReportPreview}
          onOpenAttemptPreview={onOpenAttemptPreview}
        />
      )}

      {hhProfileOpen && (
        <HhResumeModal
          candidateId={candidateId}
          candidate={candidate}
          onClose={onCloseHhProfile}
        />
      )}

      {reportPreview && (
        <ReportPreviewModal
          title={reportPreview.title}
          url={reportPreview.url}
          onClose={onCloseReportPreview}
        />
      )}

      {attemptPreview && (
        <TestAttemptModal
          testTitle={attemptPreview.testTitle}
          attempt={attemptPreview.attempt}
          onClose={onCloseAttemptPreview}
        />
      )}
    </>
  )
}
