import { Fragment, useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { ApiErrorBanner } from '@/app/components/ApiErrorBanner'
import CandidateTimeline from '@/app/components/CandidateTimeline/CandidateTimeline'
import CohortComparison from '@/app/components/CohortComparison/CohortComparison'
import QuickNotes from '@/app/components/QuickNotes/QuickNotes'
import { ModalPortal } from '@/shared/components/ModalPortal'
import { fadeIn, slideInRight } from '@/shared/motion'
import { formatDateTime } from '@/shared/utils/formatters'
import { scorecardRecommendationLabel } from '@/shared/utils/labels'
import { normalizeTelegramUsername } from '@/shared/utils/normalizers'
import { useCandidateAi, useCandidateCohort, useCandidateHh } from './candidate-detail.api'
import {
  finalOutcomeLabel,
  fitLevelFromScore,
  fitLevelLabel,
  getHhSyncBadge,
  scorecardMetricStatusLabel,
} from './candidate-detail.constants'
import type { CandidateDetail } from './candidate-detail.types'
import { buildCandidateTimeline } from './candidate-detail.utils'

type CandidateDrawerProps = {
  candidateId: number
  candidate: CandidateDetail
  statusLabel: string
  isOpen: boolean
  onClose: () => void
  onOpenInterviewScript: () => void
  onInsertChatDraft: (text: string) => void
}

export function CandidateDrawer({
  candidateId,
  candidate,
  statusLabel,
  isOpen,
  onClose,
  onOpenInterviewScript,
  onInsertChatDraft,
}: CandidateDrawerProps) {
  const queryClient = useQueryClient()
  const reduceMotion = useReducedMotion()
  const hhSummaryQuery = useCandidateHh(candidateId, isOpen)
  const cohortComparisonQuery = useCandidateCohort(candidateId, isOpen)
  const ai = useCandidateAi(candidateId)
  const [aiDraftMode, setAiDraftMode] = useState<'short' | 'neutral' | 'supportive'>('neutral')
  const [aiCoachDrafts, setAiCoachDrafts] = useState(ai.coachQuery.data?.coach?.message_drafts || null)
  const [aiResumeText, setAiResumeText] = useState('')
  const [aiResumeStatus, setAiResumeStatus] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  useEffect(() => {
    setAiCoachDrafts(null)
    setAiResumeStatus(null)
    setAiResumeText('')
  }, [candidateId])

  const candidateJourney = candidate.journey || null
  const archiveInfo = candidate.archive || candidateJourney?.archive || null
  const finalOutcomeDisplay = candidateJourney?.final_outcome_label || finalOutcomeLabel(candidate.final_outcome) || null
  const telegramUsername = normalizeTelegramUsername(candidate.telegram_username)
  const hhSummary = hhSummaryQuery.data
  const hhBadge = getHhSyncBadge(hhSummary?.sync_status ?? candidate.hh_sync_status)
  const hhAvailableActions = (hhSummary?.available_actions || []).filter((item) => item.enabled !== false)
  const shouldShowHhPanel = Boolean(
    hhSummaryQuery.isPending
      || hhSummary?.linked
      || hhSummaryQuery.isError
      || candidate.hh_resume_id
      || candidate.hh_negotiation_id
      || candidate.hh_sync_status,
  )

  const aiSummaryData = ai.summaryQuery.data?.summary || null
  const aiSummaryError = (ai.summaryQuery.error as Error | null) || (ai.refreshSummaryMutation.error as Error | null)
  const aiFit = aiSummaryData?.fit || null
  const aiScorecard = aiSummaryData?.scorecard || null
  const aiStrengths = aiSummaryData?.strengths || []
  const aiWeaknesses = aiSummaryData?.weaknesses || []
  const aiCriteriaChecklist = (aiSummaryData?.criteria_checklist || []).filter((item) => Boolean(item?.label || item?.evidence))
  const aiRisks = aiSummaryData?.risks || []
  const aiNextActions = aiSummaryData?.next_actions || []
  const aiTestInsights = aiSummaryData?.test_insights || null
  const aiScorecardMetrics = (aiScorecard?.metrics || []).filter((metric) => Boolean(metric?.label || metric?.evidence))
  const aiScorecardBlockers = (aiScorecard?.blockers || []).filter((item) => Boolean(item?.label || item?.evidence))
  const aiScorecardMissingData = (aiScorecard?.missing_data || []).filter((item) => Boolean(item?.label || item?.evidence))
  const aiDisplayScore = aiScorecard?.final_score ?? aiFit?.score ?? null
  const aiDisplayLevel = aiScorecard?.final_score != null ? fitLevelFromScore(aiScorecard.final_score) : (aiFit?.level || 'unknown')

  const aiCoachData = ai.coachQuery.data?.coach || null
  const aiCoachError = (ai.coachQuery.error as Error | null) || (ai.refreshCoachMutation.error as Error | null)
  const aiCoachStrengths = aiCoachData?.strengths || []
  const aiCoachRisks = aiCoachData?.risks || []
  const aiCoachQuestions = aiCoachData?.interview_questions || []
  const aiCoachDraftItems = aiCoachDrafts || aiCoachData?.message_drafts || []

  const quickNotesStorageKey = `candidate-quick-notes:${candidateId}`
  const detailTimelineEvents = useMemo(
    () => buildCandidateTimeline(candidate.timeline || [], hhSummary),
    [candidate.timeline, hhSummary],
  )
  const drawerInfoRows = useMemo<Array<{ label: string; value: string; href?: string | null }>>(() => {
    const rows = [
      { label: 'ID', value: `#${candidateId}` },
      {
        label: 'Телефон',
        value: candidate.phone || '—',
        href: candidate.phone ? `tel:${candidate.phone.replace(/[^\d+]/g, '')}` : null,
      },
      {
        label: 'Telegram',
        value: telegramUsername ? `@${telegramUsername}` : candidate.telegram_id ? `ID ${candidate.telegram_id}` : 'Не привязан',
      },
      { label: 'Город', value: candidate.city || '—' },
      { label: 'Рекрутер', value: candidate.responsible_recruiter?.name || '—' },
      { label: 'Состояние', value: statusLabel },
    ]

    if (finalOutcomeDisplay || archiveInfo?.label) {
      rows.push({ label: 'Итог', value: finalOutcomeDisplay || archiveInfo?.label || '—' })
    }

    return rows
  }, [
    archiveInfo?.label,
    candidate.city,
    candidate.phone,
    candidate.responsible_recruiter?.name,
    candidate.telegram_id,
    candidateId,
    finalOutcomeDisplay,
    statusLabel,
    telegramUsername,
  ])

  return (
    <ModalPortal>
      <AnimatePresence>
        {isOpen ? (
          <motion.div
            className="drawer-overlay candidate-drawer-overlay candidate-drawer-overlay--insights"
            onClick={(event) => event.target === event.currentTarget && onClose()}
            initial={reduceMotion ? false : fadeIn.initial}
            animate={reduceMotion ? undefined : fadeIn.animate}
            exit={reduceMotion ? undefined : fadeIn.exit}
            transition={reduceMotion ? { duration: 0 } : fadeIn.transition}
          >
            <motion.aside
              className="candidate-chat-drawer candidate-drawer candidate-insights-drawer glass"
              onClick={(event) => event.stopPropagation()}
              data-testid="candidate-insights-drawer"
              initial={reduceMotion ? false : slideInRight.initial}
              animate={reduceMotion ? undefined : slideInRight.animate}
              exit={reduceMotion ? undefined : slideInRight.exit}
              transition={reduceMotion ? { duration: 0 } : slideInRight.transition}
            >
              <header className="candidate-chat-drawer__header candidate-drawer__header">
                <h3 className="candidate-chat-drawer__title">Детали кандидата</h3>
                <button type="button" className="ui-btn ui-btn--ghost" onClick={onClose}>
                  Закрыть
                </button>
              </header>

              <div className="candidate-chat-drawer__body candidate-drawer__body candidate-insights-drawer__body">
                <section className="glass panel candidate-insights-drawer__section">
                  <div className="cd-section-header">
                    <h2 className="cd-section-title">Карточка кандидата</h2>
                  </div>
                  <div className="candidate-drawer__info-grid">
                    {drawerInfoRows.map((item) => (
                      item.href ? (
                        <Fragment key={item.label}>
                          <span className="candidate-drawer__info-label">{item.label}</span>
                          <a href={item.href} className="candidate-drawer__info-value candidate-drawer__info-value--phone">
                            {item.value}
                          </a>
                        </Fragment>
                      ) : (
                        <Fragment key={item.label}>
                          <span className="candidate-drawer__info-label">{item.label}</span>
                          <span className="candidate-drawer__info-value">{item.value}</span>
                        </Fragment>
                      )
                    ))}
                  </div>
                </section>

                <CandidateTimeline events={detailTimelineEvents} />
                <QuickNotes storageKey={quickNotesStorageKey} />

                {shouldShowHhPanel && (
                  <section className="glass panel cd-hh-panel candidate-insights-drawer__section">
                    <div className="cd-section-header">
                      <h2 className="cd-section-title">HH.ru</h2>
                      <div className="ui-section-header__actions">
                        {hhSummary?.resume?.url ? (
                          <a href={hhSummary.resume.url} className="ui-btn ui-btn--ghost ui-btn--sm" target="_blank" rel="noopener">
                            Открыть в HH
                          </a>
                        ) : null}
                      </div>
                    </div>

                {hhSummaryQuery.isPending ? (
                  <div className="ui-state ui-state--loading">
                    <p className="ui-state__text">Загружаю данные HH…</p>
                  </div>
                ) : hhSummaryQuery.isError ? (
                  <ApiErrorBanner
                    title="Не удалось загрузить данные HH"
                    error={hhSummaryQuery.error}
                    onRetry={() => hhSummaryQuery.refetch()}
                  />
                ) : hhSummary?.linked ? (
                  <div className="cd-hh-panel__grid">
                    <div className="cd-hh-card">
                      <div className="cd-hh-card__label">Резюме</div>
                      <div className="cd-hh-card__value">{hhSummary.resume?.title || hhSummary.resume?.id || '—'}</div>
                      <div className="cd-hh-card__meta">
                        {hhSummary.resume?.id ? <span className="cd-chip">resume {hhSummary.resume.id}</span> : null}
                        {hhSummary.resume?.source_updated_at ? (
                          <span className="cd-chip">обновлено {formatDateTime(hhSummary.resume.source_updated_at)}</span>
                        ) : null}
                      </div>
                    </div>

                    <div className="cd-hh-card">
                      <div className="cd-hh-card__label">Переговоры</div>
                      <div className="cd-hh-card__value">{hhSummary.negotiation?.employer_state || '—'}</div>
                      <div className="cd-hh-card__meta">
                        {hhSummary.negotiation?.collection_name ? (
                          <span className="cd-chip">{hhSummary.negotiation.collection_name}</span>
                        ) : null}
                        {hhSummary.negotiation?.id ? (
                          <span className="cd-chip">negotiation {hhSummary.negotiation.id}</span>
                        ) : null}
                      </div>
                    </div>

                    <div className="cd-hh-card">
                      <div className="cd-hh-card__label">Вакансия</div>
                      <div className="cd-hh-card__value">{hhSummary.vacancy?.title || hhSummary.vacancy?.id || '—'}</div>
                      <div className="cd-hh-card__meta">
                        {hhSummary.vacancy?.id ? <span className="cd-chip">vacancy {hhSummary.vacancy.id}</span> : null}
                        {hhSummary.vacancy?.area_name ? <span className="cd-chip">{hhSummary.vacancy.area_name}</span> : null}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="ui-state ui-state--empty">
                    <p className="ui-state__text">Прямая HH-связка для этого кандидата ещё не сформирована.</p>
                  </div>
                )}

                {hhSummary?.linked ? (
                  <>
                    <div className="cd-hh-panel__meta">
                      {hhBadge ? (
                        <span className={`cd-chip ${hhBadge.tone === 'success' ? 'cd-chip--success' : hhBadge.tone === 'danger' ? 'cd-chip--danger' : hhBadge.tone === 'warning' ? 'cd-chip--warning' : ''}`}>
                          {hhBadge.label}
                        </span>
                      ) : null}
                      {hhSummary.last_hh_sync_at ? (
                        <span className="cd-chip">синхронизация {formatDateTime(hhSummary.last_hh_sync_at)}</span>
                      ) : null}
                      {hhSummary.sync_error ? (
                        <span className="cd-chip cd-chip--danger" title={hhSummary.sync_error}>есть ошибка синхронизации</span>
                      ) : null}
                    </div>

                    {hhAvailableActions.length > 0 ? (
                      <div className="cd-hh-panel__actions">
                        {hhAvailableActions.slice(0, 8).map((action) => (
                          <span key={action.id || action.name} className="cd-chip cd-chip--accent" title={action.resulting_employer_state?.name || undefined}>
                            {action.name || action.id}
                          </span>
                        ))}
                      </div>
                    ) : null}

                    {hhSummary.recent_jobs && hhSummary.recent_jobs.length > 0 ? (
                      <div className="cd-hh-panel__jobs">
                        <div className="cd-hh-card__label">Последние HH задачи</div>
                        <div className="cd-hh-panel__job-list">
                          {hhSummary.recent_jobs.slice(0, 3).map((job) => (
                            <div key={job.id} className="cd-hh-job">
                              <span className="cd-hh-job__title">{job.job_type}</span>
                              <span className={`cd-chip ${job.status === 'done' ? 'cd-chip--success' : job.status === 'dead' ? 'cd-chip--danger' : job.status === 'running' ? 'cd-chip--warning' : ''}`}>
                                {job.status}
                              </span>
                              <span className="cd-hh-job__meta">
                                #{job.id}
                                {job.finished_at ? ` · ${formatDateTime(job.finished_at)}` : ''}
                                {job.attempts ? ` · попыток ${job.attempts}` : ''}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </>
                ) : null}
              </section>
            )}

            <section className="glass panel cd-ai candidate-insights-drawer__section">
              <div className="cd-section-header">
                <h2 className="cd-section-title">AI-помощник</h2>
                <div className="cd-ai__actions candidate-drawer__ai-actions">
                  {ai.summaryQuery.data ? (
                    <span
                      className={`candidate-drawer__ai-action candidate-drawer__ai-action--ghost ${ai.summaryQuery.data.cached ? '' : 'candidate-drawer__ai-action--fresh'}`}
                    >
                      {ai.summaryQuery.data.cached ? 'Кэш' : 'Новый'}
                    </span>
                  ) : (
                    <button
                      type="button"
                      className="candidate-drawer__ai-action candidate-drawer__ai-action--ghost"
                      onClick={() => ai.summaryQuery.refetch()}
                      disabled={ai.summaryQuery.isFetching}
                    >
                      {ai.summaryQuery.isFetching ? 'Генерация…' : 'Новый'}
                    </button>
                  )}
                  <button
                    type="button"
                    className="candidate-drawer__ai-action candidate-drawer__ai-action--secondary"
                    onClick={() => ai.refreshSummaryMutation.mutate()}
                    disabled={!ai.summaryQuery.data || ai.refreshSummaryMutation.isPending}
                    title="Форс-обновление сводки"
                  >
                    {ai.refreshSummaryMutation.isPending ? 'Обновление…' : 'Обновить'}
                  </button>
                  <button
                    type="button"
                    className="candidate-drawer__ai-action candidate-drawer__ai-action--primary"
                    onClick={onOpenInterviewScript}
                  >
                    Скрипт интервью
                  </button>
                </div>
              </div>

              <textarea
                rows={6}
                value={aiResumeText}
                onChange={(event) => {
                  setAiResumeText(event.target.value)
                  if (aiResumeStatus) setAiResumeStatus(null)
                }}
                placeholder="Вставьте текст резюме для усиления AI-анализа..."
                aria-label="Резюме для AI"
                className="candidate-drawer__resume-input"
              />
              <div className="candidate-drawer__resume-actions">
                <button
                  className="ui-btn ui-btn--ghost"
                  type="button"
                  onClick={() => ai.resumeMutation.mutate(aiResumeText.trim(), {
                    onSuccess: () => {
                      setAiResumeStatus('Текст резюме сохранён. AI-контекст обновлён.')
                      queryClient.invalidateQueries({ queryKey: ['ai-summary', candidateId] })
                      queryClient.invalidateQueries({ queryKey: ['ai-coach', candidateId] })
                      queryClient.invalidateQueries({ queryKey: ['ai-interview-script', candidateId] })
                      void ai.summaryQuery.refetch()
                      void ai.coachQuery.refetch()
                    },
                    onError: (error) => {
                      setAiResumeStatus((error as Error).message)
                    },
                  })}
                  disabled={!aiResumeText.trim() || ai.resumeMutation.isPending}
                >
                  {ai.resumeMutation.isPending ? 'Сохраняем…' : 'Сохранить резюме'}
                </button>
                {aiResumeStatus ? <span className="subtitle">{aiResumeStatus}</span> : null}
              </div>

              <details className="ui-disclosure cd-ai__disclosure">
                <summary className="ui-disclosure__trigger" data-testid="cd-ai-section-toggle-coach">Подсказки рекрутеру</summary>
                <div className="ui-disclosure__content">
                  <div className="cd-ai-coach__toolbar">
                    {!aiCoachData ? (
                      <button className="ui-btn ui-btn--ghost" onClick={() => ai.coachQuery.refetch()} disabled={ai.coachQuery.isFetching}>
                        {ai.coachQuery.isFetching ? 'Генерация…' : 'Сгенерировать подсказки'}
                      </button>
                    ) : (
                      <button className="ui-btn ui-btn--ghost" onClick={() => ai.refreshCoachMutation.mutate()} disabled={ai.refreshCoachMutation.isPending}>
                        {ai.refreshCoachMutation.isPending ? 'Обновление…' : 'Обновить подсказки'}
                      </button>
                    )}
                    <div className="cd-ai-drafts__modes">
                      {(['short', 'neutral', 'supportive'] as const).map((mode) => (
                        <button
                          key={`coach-${mode}`}
                          type="button"
                          className={`cd-ai-drafts__mode ${aiDraftMode === mode ? 'cd-ai-drafts__mode--active' : ''}`}
                          onClick={() => {
                            setAiDraftMode(mode)
                            ai.coachDraftsMutation.mutate(mode, {
                              onSuccess: (data) => {
                                setAiCoachDrafts(data.drafts || [])
                              },
                            })
                          }}
                          disabled={ai.coachDraftsMutation.isPending || !aiCoachData}
                        >
                          {mode === 'short' ? 'Коротко' : mode === 'neutral' ? 'Нейтр.' : 'Поддерж.'}
                        </button>
                      ))}
                    </div>
                  </div>

                  {aiCoachError && <p className="subtitle subtitle--danger">Подсказки: {aiCoachError.message}</p>}
                  {ai.coachDraftsMutation.error && (
                    <p className="subtitle subtitle--danger">
                      Черновики: {(ai.coachDraftsMutation.error as Error).message}
                    </p>
                  )}
                  {!aiCoachData && !ai.coachQuery.isFetching && !ai.refreshCoachMutation.isPending && (
                    <p className="subtitle">Сгенерируйте рекомендации по релевантности, рискам и вопросам интервью.</p>
                  )}

                  {aiCoachData && (
                    <div className="cd-ai-coach__grid">
                      <div className="cd-ai__card">
                        <div className="cd-ai__label">Релевантность</div>
                        <div className="cd-ai-fit">
                          <div className="cd-ai-fit__score">
                            {aiCoachData.relevance_score != null ? `${aiCoachData.relevance_score}/100` : '—'}
                          </div>
                          <div className={`cd-ai-fit__badge cd-ai-fit__badge--${aiCoachData.relevance_level || 'unknown'}`}>
                            {aiCoachData.relevance_level === 'high'
                              ? 'Высокая'
                              : aiCoachData.relevance_level === 'medium'
                                ? 'Средняя'
                                : aiCoachData.relevance_level === 'low'
                                  ? 'Низкая'
                                  : 'Неизвестно'}
                          </div>
                        </div>
                        {aiCoachData.rationale && <div className="cd-ai__text">{aiCoachData.rationale}</div>}
                      </div>

                      <div className="cd-ai__card">
                        <div className="cd-ai__label">Следующий шаг</div>
                        <div className="cd-ai__text">{aiCoachData.next_best_action || '—'}</div>
                      </div>

                      <div className="cd-ai__card">
                        <div className="cd-ai__label">Сильные стороны</div>
                        {aiCoachStrengths.length === 0 ? (
                          <div className="subtitle">Нет данных</div>
                        ) : (
                          <ul className="cd-ai__list">
                            {aiCoachStrengths.slice(0, 5).map((strength) => (
                              <li key={`coach-strength-${strength.key}`} className="cd-ai__point cd-ai__point--strength">
                                <div className="cd-ai__point-title">{strength.label}</div>
                                <div className="cd-ai__point-text">{strength.evidence}</div>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>

                      <div className="cd-ai__card">
                        <div className="cd-ai__label">Риски</div>
                        {aiCoachRisks.length === 0 ? (
                          <div className="subtitle">Нет рисков</div>
                        ) : (
                          <ul className="cd-ai__list">
                            {aiCoachRisks.slice(0, 5).map((risk) => (
                              <li key={`coach-risk-${risk.key}`} className={`cd-ai__risk cd-ai__risk--${risk.severity}`}>
                                <div className="cd-ai__risk-title">{risk.label}</div>
                                <div className="cd-ai__risk-text">{risk.explanation}</div>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>

                      <div className="cd-ai__card">
                        <div className="cd-ai__label">Вопросы интервью</div>
                        {aiCoachQuestions.length === 0 ? (
                          <div className="subtitle">Нет предложенных вопросов</div>
                        ) : (
                          <ol className="cd-ai__list cd-ai__list--ordered">
                            {aiCoachQuestions.slice(0, 6).map((question, index) => (
                              <li key={`coach-question-${index}`} className="cd-ai__action">
                                <div className="cd-ai__action-text">{question}</div>
                              </li>
                            ))}
                          </ol>
                        )}
                      </div>

                      <div className="cd-ai__card cd-ai__card--span">
                        <div className="cd-ai__label">Черновики сообщений</div>
                        {ai.coachDraftsMutation.isPending && <div className="subtitle">Генерация черновиков…</div>}
                        {aiCoachDraftItems.length === 0 ? (
                          <div className="subtitle">Нет черновиков. Нажмите один из режимов выше.</div>
                        ) : (
                          <div className="cd-ai-drafts__list">
                            {aiCoachDraftItems.map((draft, index) => (
                              <div key={`coach-draft-${index}-${draft.reason}`} className="cd-ai-drafts__item">
                                <div className="cd-ai-drafts__text">{draft.text}</div>
                                <div className="cd-ai-drafts__actions">
                                  <span className="cd-ai-drafts__reason">{draft.reason}</span>
                                  <button
                                    type="button"
                                    className="ui-btn ui-btn--primary"
                                    onClick={() => onInsertChatDraft(draft.text)}
                                  >
                                    Вставить в чат
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </details>

              {aiSummaryError && <p className="subtitle subtitle--danger">AI: {aiSummaryError.message}</p>}
              {!aiSummaryData && !ai.summaryQuery.isFetching && !ai.refreshSummaryMutation.isPending && (
                <p className="subtitle">Сгенерируйте краткую сводку и рекомендации по следующему шагу.</p>
              )}

              {aiSummaryData && (
                <>
                  <div className="cd-ai__grid">
                    <div className="cd-ai__card">
                      <div className="cd-ai__label">TL;DR</div>
                      <div className="cd-ai__text">{aiSummaryData.tldr}</div>
                    </div>

                    <div className="cd-ai__card">
                      <div className="cd-ai__label">Релевантность</div>
                      <div className="cd-ai-fit">
                        <div className="cd-ai-fit__score">{aiDisplayScore != null ? `${aiDisplayScore}/100` : '—'}</div>
                        <div className={`cd-ai-fit__badge cd-ai-fit__badge--${aiDisplayLevel || 'unknown'}`}>
                          {fitLevelLabel(aiDisplayLevel)}
                        </div>
                      </div>
                      {aiScorecard?.recommendation && (
                        <div className="cd-hh-card__meta">
                          <span className="cd-chip cd-chip--small">{scorecardRecommendationLabel(aiScorecard.recommendation)}</span>
                          {aiScorecard.objective_score != null ? <span className="cd-chip cd-chip--small">объективно {aiScorecard.objective_score}/100</span> : null}
                          {aiScorecard.semantic_score != null ? <span className="cd-chip cd-chip--small">по смыслу {aiScorecard.semantic_score}/100</span> : null}
                        </div>
                      )}
                      {aiFit?.criteria_used === false && <div className="subtitle">Критерии города не заданы, оценка ограничена.</div>}
                      {aiFit?.rationale && <div className="cd-ai__text">{aiFit.rationale}</div>}
                    </div>
                  </div>

                  <details className="ui-disclosure cd-ai__disclosure">
                    <summary className="ui-disclosure__trigger" data-testid="cd-ai-section-toggle-analysis">Развернуть полный анализ</summary>
                    <div className="ui-disclosure__content">
                      <div className="cd-ai__grid">
                        {aiSummaryData.vacancy_fit && (
                          <div className="cd-ai__card cd-ai__card--span">
                            <div className="cd-ai__label">Оценка релевантности вакансии</div>
                            <div className="cd-ai-fit cd-ai-fit--spaced">
                              <div className="cd-ai-fit__score">{aiSummaryData.vacancy_fit.score != null ? `${aiSummaryData.vacancy_fit.score}/100` : '—'}</div>
                              <div className={`cd-ai-fit__badge cd-ai-fit__badge--${aiSummaryData.vacancy_fit.level || 'unknown'}`}>
                                {aiSummaryData.vacancy_fit.level === 'high' ? 'Высокая' : aiSummaryData.vacancy_fit.level === 'medium' ? 'Средняя' : aiSummaryData.vacancy_fit.level === 'low' ? 'Низкая' : 'Неизвестно'}
                              </div>
                              {aiSummaryData.vacancy_fit.criteria_source && aiSummaryData.vacancy_fit.criteria_source !== 'none' && (
                                <span className="cd-chip cd-chip--small">
                                  {aiSummaryData.vacancy_fit.criteria_source === 'both' ? 'критерии + регламент' : aiSummaryData.vacancy_fit.criteria_source === 'city_criteria' ? 'критерии города' : 'регламент'}
                                </span>
                              )}
                            </div>
                            {aiSummaryData.vacancy_fit.summary && <div className="cd-ai__text cd-ai__text--spaced">{aiSummaryData.vacancy_fit.summary}</div>}
                            {(aiSummaryData.vacancy_fit.evidence || []).length > 0 && (
                              <ul className="cd-ai__list">
                                {(aiSummaryData.vacancy_fit.evidence || []).map((item, index) => (
                                  <li key={index} className={`cd-ai__point cd-ai__point--${item.assessment === 'positive' ? 'strength' : item.assessment === 'negative' ? 'weakness' : 'neutral'}`}>
                                    <div className="cd-ai__point-title">{item.factor}</div>
                                    <div className="cd-ai__point-text">{item.detail}</div>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                        )}

                        {aiCriteriaChecklist.length > 0 && (
                          <div className="cd-ai__card cd-ai__card--span">
                            <div className="cd-ai__label">Чек-лист критериев</div>
                            <ul className="cd-ai__list">
                              {aiCriteriaChecklist.map((criterion) => (
                                <li key={criterion.key} className={`cd-ai-crit cd-ai-crit--${criterion.status || 'unknown'}`}>
                                  <div className="cd-ai-crit__top">
                                    <span className={`cd-ai-crit__badge cd-ai-crit__badge--${criterion.status || 'unknown'}`}>
                                      {criterion.status === 'met' ? 'ОК' : criterion.status === 'not_met' ? 'Не ок' : 'Неясно'}
                                    </span>
                                    <div className="cd-ai-crit__title">{criterion.label}</div>
                                  </div>
                                  <div className="cd-ai-crit__text">{criterion.evidence}</div>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {aiScorecardMetrics.length > 0 && (
                          <div className="cd-ai__card cd-ai__card--span">
                            <div className="cd-ai__label">Scorecard по метрикам</div>
                            <ul className="cd-ai__list">
                              {aiScorecardMetrics.map((metric) => (
                                <li key={metric.key} className={`cd-ai-crit cd-ai-crit--${metric.status || 'unknown'}`}>
                                  <div className="cd-ai-crit__top">
                                    <span className={`cd-ai-crit__badge cd-ai-crit__badge--${metric.status || 'unknown'}`}>
                                      {scorecardMetricStatusLabel(metric.status)}
                                    </span>
                                    <div className="cd-ai-crit__title">
                                      {metric.label}
                                      {metric.weight != null ? ` · ${metric.score ?? 0}/${metric.weight}` : ''}
                                    </div>
                                  </div>
                                  <div className="cd-ai-crit__text">{metric.evidence}</div>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {(aiScorecardBlockers.length > 0 || aiScorecardMissingData.length > 0) && (
                          <div className="cd-ai__card cd-ai__card--span">
                            <div className="cd-ai__label">Блокеры и что уточнить</div>
                            <ul className="cd-ai__list">
                              {aiScorecardBlockers.map((item) => (
                                <li key={`blocker-${item.key}`} className="cd-ai__risk cd-ai__risk--high">
                                  <div className="cd-ai__risk-title">{item.label}</div>
                                  <div className="cd-ai__risk-text">{item.evidence}</div>
                                </li>
                              ))}
                              {aiScorecardMissingData.map((item) => (
                                <li key={`missing-${item.key}`} className="cd-ai__point">
                                  <div className="cd-ai__point-title">{item.label}</div>
                                  <div className="cd-ai__point-text">{item.evidence}</div>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        <div className="cd-ai__card">
                          <div className="cd-ai__label">Сильные стороны</div>
                          {aiStrengths.length === 0 ? (
                            <div className="subtitle">Нет явных сильных сторон по текущим данным.</div>
                          ) : (
                            <ul className="cd-ai__list">
                              {aiStrengths.map((strength) => (
                                <li key={strength.key} className="cd-ai__point cd-ai__point--strength">
                                  <div className="cd-ai__point-title">{strength.label}</div>
                                  <div className="cd-ai__point-text">{strength.evidence}</div>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>

                        <div className="cd-ai__card">
                          <div className="cd-ai__label">Зоны роста</div>
                          {aiWeaknesses.length === 0 ? (
                            <div className="subtitle">Критичных зон роста не выявлено.</div>
                          ) : (
                            <ul className="cd-ai__list">
                              {aiWeaknesses.map((weakness) => (
                                <li key={weakness.key} className="cd-ai__point cd-ai__point--weakness">
                                  <div className="cd-ai__point-title">{weakness.label}</div>
                                  <div className="cd-ai__point-text">{weakness.evidence}</div>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>

                        <div className="cd-ai__card">
                          <div className="cd-ai__label">Риски</div>
                          {aiRisks.length === 0 ? (
                            <div className="subtitle">Явных рисков не найдено.</div>
                          ) : (
                            <ul className="cd-ai__list">
                              {aiRisks.map((risk) => (
                                <li key={risk.key} className={`cd-ai__risk cd-ai__risk--${risk.severity}`}>
                                  <div className="cd-ai__risk-title">{risk.label}</div>
                                  <div className="cd-ai__risk-text">{risk.explanation}</div>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>

                        <div className="cd-ai__card">
                          <div className="cd-ai__label">Следующие шаги</div>
                          {aiNextActions.length === 0 ? (
                            <div className="subtitle">Нет рекомендаций.</div>
                          ) : (
                            <ol className="cd-ai__list cd-ai__list--ordered">
                              {aiNextActions.map((action) => (
                                <li key={action.key} className="cd-ai__action">
                                  <div className="cd-ai__action-title">{action.label}</div>
                                  <div className="cd-ai__action-text">{action.rationale}</div>
                                </li>
                              ))}
                            </ol>
                          )}
                        </div>

                        {aiTestInsights && (
                          <div className="cd-ai__card cd-ai__card--span">
                            <div className="cd-ai__label">Анализ тестов</div>
                            <div className="cd-ai__text">{aiTestInsights}</div>
                          </div>
                        )}

                        {aiSummaryData.notes && (
                          <div className="cd-ai__card cd-ai__card--span">
                            <div className="cd-ai__label">Заметки</div>
                            <div className="cd-ai__text">{aiSummaryData.notes}</div>
                          </div>
                        )}
                      </div>
                    </div>
                  </details>
                </>
              )}
            </section>

            <CohortComparison
              data={cohortComparisonQuery.data}
              isLoading={cohortComparisonQuery.isPending}
            />
          </div>
            </motion.aside>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </ModalPortal>
  )
}
