import { useNavigate, useParams } from '@tanstack/react-router'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import '@/theme/pages/candidate-detail.css'
import type { CandidateAction, CandidateActionResponse } from '@/api/services/candidates'
import { RecruiterRiskBanner } from '@/app/components/RecruiterState'
import { ApiErrorBanner } from '@/app/components/ApiErrorBanner'
import CandidatePipeline from '@/app/components/CandidatePipeline/CandidatePipeline'
import CandidateTimeline from '@/app/components/CandidateTimeline/CandidateTimeline'
import InterviewScript from '@/app/components/InterviewScript/InterviewScript'
import { RecruitmentScript, ScriptFab } from '@/app/components/RecruitmentScript/RecruitmentScript'
import { RoleGuard } from '@/app/components/RoleGuard'
import { useIsMobile } from '@/app/hooks/useIsMobile'
import { formatDateTime, formatSlotTime } from '@/shared/utils/formatters'
import { useCandidateAi, useCandidateActions, useCandidateChannelHealth, useCandidateDetail } from './candidate-detail.api'
import { CandidateActions } from './CandidateActions'
import { CandidateChatDrawer } from './CandidateChatDrawer'
import { CandidateDrawer } from './CandidateDrawer'
import { CandidateHeader } from './CandidateHeader'
import { CandidateModals } from './CandidateModals'
import { CandidateTests } from './CandidateTests'
import { buildCandidateSurfaceState } from '../candidate-state.adapter'
import { fitLevelFromScore, getStatusDisplay } from './candidate-detail.constants'
import type { RejectState, ReportPreviewState, TestAttemptPreview } from './candidate-detail.types'
import {
  buildCandidateTimeline,
  buildCandidatePipelineData,
  buildTestSections,
  getInterviewSlot,
  getIntroDaySlot,
  resolveFinalOutcomeDisplay,
} from './candidate-detail.utils'
import { formatRescheduleRequest } from '@/shared/utils/labels'

export function CandidateDetailPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const params = useParams({ from: '/app/candidates/$candidateId' })
  const isMobile = useIsMobile()
  const candidateId = Number(params.candidateId)

  const [mobileTab, setMobileTab] = useState<'profile' | 'tests' | 'chat'>('profile')
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [lastActionResponse, setLastActionResponse] = useState<CandidateActionResponse | null>(null)
  const [showScheduleSlotModal, setShowScheduleSlotModal] = useState(false)
  const [showScheduleIntroDayModal, setShowScheduleIntroDayModal] = useState(false)
  const [showRejectModal, setShowRejectModal] = useState<RejectState | null>(null)
  const [reportPreview, setReportPreview] = useState<ReportPreviewState | null>(null)
  const [attemptPreview, setAttemptPreview] = useState<TestAttemptPreview | null>(null)
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [isInsightsOpen, setIsInsightsOpen] = useState(false)
  const [isInterviewScriptOpen, setIsInterviewScriptOpen] = useState(false)
  const [chatDraftSeed, setChatDraftSeed] = useState<{ text: string; nonce: number } | null>(null)
  const [isRecruitmentScriptOpen, setIsRecruitmentScriptOpen] = useState(false)

  const pipelineActionsRef = useRef<HTMLDivElement | null>(null)
  const testsSectionRef = useRef<HTMLDivElement | null>(null)

  const detailQuery = useCandidateDetail(candidateId)
  const { actionMutation, createMaxLinkMutation } = useCandidateActions(candidateId)
  const channelHealthQuery = useCandidateChannelHealth(candidateId, detailQuery.isSuccess)
  const ai = useCandidateAi(candidateId)

  const detail = detailQuery.data
  const testSections = useMemo(() => buildTestSections(detail), [detail])
  const test1Section = testSections.find((section) => section.key === 'test1')
  const test2Section = testSections.find((section) => section.key === 'test2')

  const candidateJourney = detail?.journey || null
  const channelHealth = channelHealthQuery.data || null
  const archiveInfo = detail?.archive || candidateJourney?.archive || null
  const statusSlug = detail?.candidate_status_slug || null
  const statusDisplay = detail ? getStatusDisplay(statusSlug) : null
  const statusLabel = detail?.candidate_status_display || statusDisplay?.label || 'Нет статуса'
  const rescheduleRequest = formatRescheduleRequest(detail?.reschedule_request)
  const pendingSlotRequest = formatRescheduleRequest(detail?.pending_slot_request || candidateJourney?.pending_slot_request)
  const rescheduleRequestLabel = rescheduleRequest?.summary || null
  const pendingSlotRequestLabel = pendingSlotRequest?.summary || null
  const finalOutcomeDisplay = resolveFinalOutcomeDisplay(candidateJourney, detail?.final_outcome)
  const finalOutcomeReason = detail?.final_outcome_reason || candidateJourney?.final_outcome_reason || null
  const preferredChannel = channelHealth?.preferred_channel || detail?.messenger_platform
  const chatChannelLabel = preferredChannel === 'max' && detail?.max_user_id ? 'MAX' : 'Telegram'

  const pipelineData = useMemo(() => {
    if (!detail) return null
    return buildCandidatePipelineData({
      detail,
      statusSlug,
      statusLabel,
      candidateJourney,
      archiveInfo,
      pendingSlotRequest,
      rescheduleRequest,
      finalOutcomeDisplay,
      finalOutcomeReason,
      test1Section,
      test2Section,
    })
  }, [
    archiveInfo,
    candidateJourney,
    detail,
    finalOutcomeDisplay,
    finalOutcomeReason,
    pendingSlotRequest,
    rescheduleRequest,
    statusLabel,
    statusSlug,
    test1Section,
    test2Section,
  ])

  const aiSummaryData = ai.summaryQuery.data?.summary || null
  const aiScorecard = aiSummaryData?.scorecard || null
  const aiFit = aiSummaryData?.fit || null
  const aiDisplayScore = aiScorecard?.final_score ?? aiFit?.score ?? null
  const aiDisplayLevel = aiScorecard?.final_score != null ? fitLevelFromScore(aiScorecard.final_score) : (aiFit?.level || 'unknown')
  const headerAiScore = aiDisplayScore ?? ai.coachQuery.data?.coach?.relevance_score ?? null
  const headerAiLevel = aiDisplayLevel !== 'unknown' ? aiDisplayLevel : (ai.coachQuery.data?.coach?.relevance_level || 'unknown')
  const headerAiRecommendation = aiScorecard?.recommendation || null
  const surfaceState = useMemo(() => {
    if (!detail) return null
    return buildCandidateSurfaceState({
      status_slug: detail.candidate_status_slug,
      status_display: detail.candidate_status_display,
      lifecycle_summary: detail.lifecycle_summary,
      scheduling_summary: detail.scheduling_summary,
      candidate_next_action: detail.candidate_next_action,
      operational_summary: detail.operational_summary,
      state_reconciliation: detail.state_reconciliation,
      blocking_state: lastActionResponse?.blocking_state || null,
    })
  }, [detail, lastActionResponse?.blocking_state])
  const interviewSlot = useMemo(() => getInterviewSlot(detail?.slots), [detail?.slots])
  const introDaySlot = useMemo(() => getIntroDaySlot(detail?.slots), [detail?.slots])
  const detailTimeline = useMemo(
    () => buildCandidateTimeline(detail?.timeline || [], null).slice(0, 5),
    [detail?.timeline],
  )
  const riskIssues = detail?.state_reconciliation?.issues || []

  useEffect(() => {
    setMobileTab('profile')
    setLastActionResponse(null)
    setIsInterviewScriptOpen(false)
    setIsChatOpen(false)
    setIsInsightsOpen(false)
  }, [candidateId])

  useEffect(() => {
    if (!isMobile) return
    if (mobileTab === 'chat') {
      setIsChatOpen(true)
      return
    }
    setIsChatOpen(false)
  }, [isMobile, mobileTab])

  useEffect(() => {
    if (typeof window === 'undefined') return
    if (window.location.hash !== '#tests') return
    if (isMobile && mobileTab !== 'tests') {
      setMobileTab('tests')
    }
  }, [candidateId, isMobile, mobileTab])

  useEffect(() => {
    if (typeof window === 'undefined') return
    if (window.location.hash !== '#tests') return
    const frame = window.requestAnimationFrame(() => {
      if (testsSectionRef.current && typeof testsSectionRef.current.scrollIntoView === 'function') {
        testsSectionRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    })
    return () => window.cancelAnimationFrame(frame)
  }, [candidateId, detail?.id, mobileTab, testSections.length])

  const handleDetailChanged = (message = 'Действие выполнено') => {
    setActionMessage(message)
    setLastActionResponse(null)
    void detailQuery.refetch()
    void queryClient.invalidateQueries({ queryKey: ['candidates'] })
  }

  const refreshCandidateSurfaces = async () => {
    await Promise.all([
      detailQuery.refetch(),
      channelHealthQuery.refetch(),
      queryClient.invalidateQueries({ queryKey: ['candidate-channel-health', candidateId] }),
      queryClient.invalidateQueries({ queryKey: ['candidate-detail', candidateId] }),
      queryClient.invalidateQueries({ queryKey: ['candidates'] }),
    ])
  }

  const describeMessengerDelivery = (
    payload: {
      delivery_block_reason?: string | null
      delivery?: {
        sent?: boolean
        status?: string | null
        attempted?: boolean
        error?: string | null
        skipped_reason?: string | null
      } | null
    } | null | undefined,
    actionLabel: string,
  ) => {
    const delivery = payload?.delivery || null
    if (delivery?.sent) return `${actionLabel}: ссылка MAX отправлена кандидату`
    if (delivery?.status === 'skipped_by_preflight') return `${actionLabel}: MAX сейчас недоступен`
    if (delivery?.status === 'not_linked') return `${actionLabel}: кандидат ещё не привязан к MAX`
    if (delivery?.status === 'skipped_no_entry') return `${actionLabel}: MAX ещё не настроен`
    if (delivery?.error) return `${actionLabel}: ${delivery.error}`
    if (payload?.delivery_block_reason) return `${actionLabel}: ${payload.delivery_block_reason}`
    return `${actionLabel}: доступ обновлён`
  }

  const handleActionClick = (action: CandidateAction) => {
    const isRejection =
      action.key === 'reject'
      || action.key === 'interview_outcome_failed'
      || action.key === 'interview_declined'
      || action.key === 'mark_not_hired'
      || action.key === 'decline_after_intro'
      || action.variant === 'danger'

    if (isRejection) {
      setShowRejectModal({ actionKey: action.key, title: action.label })
      return
    }

    if ((action.method || 'GET').toUpperCase() === 'GET') {
      if (!action.url) return
      try {
        const target = new URL(action.url, window.location.origin)
        if (target.origin !== window.location.origin) {
          setActionMessage('Внешний переход заблокирован')
          return
        }
        window.location.href = target.href
      } catch {
        window.location.href = action.url
      }
      return
    }

    if (action.confirmation && !window.confirm(action.confirmation)) {
      return
    }

    actionMutation.mutate(
      { actionKey: action.key },
      {
        onSuccess: (response) => {
          setLastActionResponse((response as CandidateActionResponse) || null)
          handleDetailChanged((response as CandidateActionResponse | undefined)?.message || 'Действие выполнено')
        },
        onError: (error) => {
          const response = (error as Error & { data?: CandidateActionResponse }).data || null
          setLastActionResponse(response)
          setActionMessage((error as Error).message)
        },
      },
    )
  }

  const handleOpenChat = () => {
    setIsInsightsOpen(false)
    if (isMobile) setMobileTab('chat')
    setIsChatOpen(true)
  }

  const handleInsertChatDraft = (text: string) => {
    setIsInsightsOpen(false)
    if (isMobile) setMobileTab('chat')
    setChatDraftSeed({ text, nonce: Date.now() })
    setIsChatOpen(true)
  }

  const handleCopyMaxLink = () => {
    createMaxLinkMutation.mutate(undefined, {
      onSuccess: async (payload) => {
        await refreshCandidateSurfaces()
        const maxLink = String(payload?.mini_app_link || payload?.deep_link || payload?.public_link || '').trim()
        if (!maxLink) {
          setActionMessage(describeMessengerDelivery(payload, 'MAX обновлён'))
          return
        }
        try {
          if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(maxLink)
            const deliveryError = String(payload?.delivery?.error || '').trim()
            setActionMessage(
              payload?.delivery?.sent
                ? (payload?.invite?.rotated
                  ? 'Ссылка MAX обновлена, скопирована и отправлена кандидату'
                  : 'Ссылка MAX скопирована и отправлена кандидату')
                : deliveryError
                  ? `Ссылка MAX скопирована. MAX ответил ошибкой: ${deliveryError}`
                  : 'Ссылка MAX подготовлена и скопирована.',
            )
            return
          }
        } catch {
          // Fall through to inline fallback.
        }
        setActionMessage(`Ссылка MAX: ${maxLink}`)
      },
      onError: (error) => {
        setActionMessage((error as Error).message)
      },
    })
  }

  const lifecycleFacts = useMemo(() => {
    if (!detail || !surfaceState) return []
    return [
      { label: 'Этап', value: surfaceState.lifecycle.stage_label || '—' },
      { label: 'Очередь', value: surfaceState.worklistBucketLabel },
      { label: 'Срочность', value: surfaceState.urgencyLabel },
      { label: 'Обновлено', value: formatDateTime(detail.last_activity_at || detail.created_at) },
    ]
  }, [detail, surfaceState])

  const schedulingFacts = useMemo(() => {
    if (!detail || !surfaceState) return []
    return [
      {
        label: 'Текущее scheduling-состояние',
        value: surfaceState.schedulingLabel || 'Нет активного назначения',
      },
      {
        label: 'Интервью',
        value: interviewSlot
          ? `${formatSlotTime(interviewSlot.start_utc, interviewSlot.candidate_tz)} · ${interviewSlot.city_name || 'без города'}`
          : 'Не назначено',
      },
      {
        label: 'Ознакомительный день',
        value: introDaySlot
          ? `${formatSlotTime(introDaySlot.start_utc, introDaySlot.candidate_tz)} · ${introDaySlot.city_name || 'без города'}`
          : 'Не назначен',
      },
      {
        label: 'Запрос/перенос',
        value: pendingSlotRequestLabel || rescheduleRequestLabel || 'Нет активного запроса',
      },
    ]
  }, [detail, introDaySlot, interviewSlot, pendingSlotRequestLabel, rescheduleRequestLabel, surfaceState])

  const contextFacts = useMemo(() => {
    if (!detail) return []
    return [
      { label: 'Рекрутер', value: detail.responsible_recruiter?.name || '—' },
      { label: 'Телефон', value: detail.phone || '—' },
      { label: 'Telegram', value: detail.telegram_username || (detail.telegram_id ? `ID ${detail.telegram_id}` : 'Не привязан') },
      { label: 'Канал', value: preferredChannel || 'Не определен' },
    ]
  }, [detail, preferredChannel])

  const showProfileSection = !isMobile || mobileTab === 'profile'
  const showTestsSection = !isMobile || mobileTab === 'tests'

  return (
    <RoleGuard allow={['recruiter', 'admin']}>
      <div className="page app-page app-page--ops candidate-detail-page">
        {detailQuery.isLoading && (
          <div className="glass panel cd-loading-panel app-page__section">
            <p className="subtitle">Загрузка...</p>
          </div>
        )}

        {detailQuery.isError && (
          <ApiErrorBanner
            error={detailQuery.error}
            title="Не удалось загрузить профиль кандидата"
            onRetry={() => detailQuery.refetch()}
          />
        )}

        {detail && (
          <div className={`candidate-detail__workspace ${isInterviewScriptOpen && !isMobile ? 'candidate-detail__workspace--script-open' : ''}`}>
            <div className="candidate-detail__content">
              {isMobile && (
                <div className="cd-mobile-tabs glass">
                  <button
                    type="button"
                    className={`ui-btn ui-btn--sm ${mobileTab === 'profile' ? 'ui-btn--primary' : 'ui-btn--ghost'}`}
                    onClick={() => setMobileTab('profile')}
                  >
                    Профиль
                  </button>
                  <button
                    type="button"
                    className={`ui-btn ui-btn--sm ${mobileTab === 'tests' ? 'ui-btn--primary' : 'ui-btn--ghost'}`}
                    onClick={() => setMobileTab('tests')}
                  >
                    Тесты
                  </button>
                  <button
                    type="button"
                    className={`ui-btn ui-btn--sm ${mobileTab === 'chat' ? 'ui-btn--primary' : 'ui-btn--ghost'}`}
                    onClick={handleOpenChat}
                  >
                    Чат
                  </button>
                </div>
              )}

              {showProfileSection && (
                <div className="cd-profile glass panel" data-testid="candidate-profile">
                  <div className="cd-profile__header" data-testid="candidate-header">
                    <CandidateHeader
                      candidate={detail}
                      candidateId={candidateId}
                      statusLabel={statusLabel}
                      showStatus={Boolean(statusDisplay)}
                      headerAiScore={headerAiScore}
                      headerAiLevel={headerAiLevel}
                      headerAiRecommendation={headerAiRecommendation}
                      isAiFetching={ai.summaryQuery.isFetching}
                      onBack={() => navigate({ to: '/app/candidates' })}
                    />
                  </div>

                  <CandidateActions
                    candidate={detail}
                    statusSlug={statusSlug}
                    blockingState={lastActionResponse?.blocking_state || null}
                    test2Section={test2Section}
                    actionPending={actionMutation.isPending}
                    maxLinkPending={createMaxLinkMutation.isPending}
                    showInsightsAction={!isMobile}
                    actionsRef={pipelineActionsRef}
                    onOpenChat={handleOpenChat}
                    onOpenInsights={() => {
                      setIsChatOpen(false)
                      setIsInsightsOpen(true)
                    }}
                    onCopyMaxLink={handleCopyMaxLink}
                    onScheduleSlot={() => setShowScheduleSlotModal(true)}
                    onScheduleIntroDay={() => setShowScheduleIntroDayModal(true)}
                    onActionClick={handleActionClick}
                  />

                  <div className="cd-detail-grid" data-testid="candidate-detail-sections">
                    <section className="cd-profile__section cd-detail-section" data-testid="candidate-detail-lifecycle">
                      <div className="cd-section-header">
                        <h2 className="cd-section-title">Lifecycle</h2>
                      </div>
                      {pipelineData && (
                        <CandidatePipeline
                          currentStateLabel={candidateJourney?.state_label || statusLabel}
                          stages={pipelineData.stages}
                          isMobile={isMobile}
                        />
                      )}
                      <div className="cd-hh-panel__grid">
                        {lifecycleFacts.map((item) => (
                          <div key={item.label} className="cd-hh-card">
                            <div className="cd-hh-card__label">{item.label}</div>
                            <div className="cd-hh-card__value">{item.value}</div>
                          </div>
                        ))}
                      </div>
                    </section>

                    <section className="cd-profile__section cd-detail-section" data-testid="candidate-detail-scheduling">
                      <div className="cd-section-header">
                        <h2 className="cd-section-title">Scheduling</h2>
                      </div>
                      <div className="cd-hh-panel__grid">
                        {schedulingFacts.map((item) => (
                          <div key={item.label} className="cd-hh-card">
                            <div className="cd-hh-card__label">{item.label}</div>
                            <div className="cd-hh-card__value">{item.value}</div>
                          </div>
                        ))}
                      </div>
                    </section>

                    <section className="cd-profile__section cd-detail-section" data-testid="candidate-detail-risks">
                      <div className="cd-section-header">
                        <h2 className="cd-section-title">Risks & blockers</h2>
                      </div>
                      {surfaceState?.riskLevel && surfaceState.riskTitle && surfaceState.riskMessage ? (
                        <RecruiterRiskBanner
                          level={surfaceState.riskLevel}
                          title={surfaceState.riskTitle}
                          message={surfaceState.riskMessage}
                          recoveryHint={surfaceState.riskRecoveryHint}
                          count={surfaceState.riskCount > 0 ? surfaceState.riskCount : undefined}
                        />
                      ) : (
                        <p className="subtitle">Критичных блокеров не surfaced. Следующий шаг можно вести по action center.</p>
                      )}
                      {riskIssues.length > 0 ? (
                        <div className="cd-hh-panel__grid">
                          {riskIssues.map((issue, index) => (
                            <div key={`${issue.code || 'risk'}-${index}`} className="cd-hh-card">
                              <div className="cd-hh-card__label">{issue.code || 'reconciliation'}</div>
                              <div className="cd-hh-card__value">{issue.message || 'Требуется ручной разбор состояния.'}</div>
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </section>

                    <section className="cd-profile__section cd-detail-section" data-testid="candidate-detail-context">
                      <div className="cd-section-header">
                        <h2 className="cd-section-title">Context & history</h2>
                        <button
                          type="button"
                          className="ui-btn ui-btn--ghost ui-btn--sm"
                          onClick={() => {
                            setIsChatOpen(false)
                            setIsInsightsOpen(true)
                          }}
                        >
                          Полные детали
                        </button>
                      </div>
                      <div className="cd-hh-panel__grid">
                        {contextFacts.map((item) => (
                          <div key={item.label} className="cd-hh-card">
                            <div className="cd-hh-card__label">{item.label}</div>
                            <div className="cd-hh-card__value">{item.value}</div>
                          </div>
                        ))}
                      </div>
                      {detailTimeline.length > 0 ? (
                        <div className="cd-detail-timeline">
                          <CandidateTimeline events={detailTimeline} />
                        </div>
                      ) : (
                        <p className="subtitle">История пока не собрана для этого кандидата.</p>
                      )}
                    </section>
                  </div>

                  {actionMessage && <p className="subtitle subtitle--center cd-action-message">{actionMessage}</p>}

                  {showTestsSection && testSections.length > 0 && (
                    <section className="cd-profile__section cd-detail-section cd-detail-section--secondary">
                      <div className="cd-section-header">
                        <h2 className="cd-section-title">Tests & tools</h2>
                      </div>
                      <CandidateTests
                        testSections={testSections}
                        sectionRef={testsSectionRef}
                        onOpenReportPreview={(title, url) => setReportPreview({ title, url })}
                        onOpenAttemptPreview={(testTitle, attempt) => setAttemptPreview({ testTitle, attempt })}
                      />
                    </section>
                  )}
                </div>
              )}

              {isMobile && showTestsSection && !showProfileSection && (
                <div className="cd-profile glass panel">
                  <CandidateTests
                    testSections={testSections}
                    sectionRef={testsSectionRef}
                    onOpenReportPreview={(title, url) => setReportPreview({ title, url })}
                    onOpenAttemptPreview={(testTitle, attempt) => setAttemptPreview({ testTitle, attempt })}
                  />
                </div>
              )}
            </div>

            <InterviewScript
              candidateId={candidateId}
              candidateName={detail.fio || `Кандидат #${candidateId}`}
              statusLabel={statusLabel}
              test1Section={test1Section || null}
              isOpen={isInterviewScriptOpen}
              isMobile={isMobile}
              onClose={() => setIsInterviewScriptOpen(false)}
              onSaved={() => {
                setIsInterviewScriptOpen(false)
                handleDetailChanged()
              }}
            />
          </div>
        )}

        {detail && isMobile && (
          <div className="cd-mobile-actions glass">
            <button
              type="button"
              className="ui-btn ui-btn--ghost ui-btn--sm"
              onClick={() => {
                setMobileTab('profile')
                requestAnimationFrame(() =>
                  pipelineActionsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }),
                )
              }}
            >
              Сменить статус
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--ghost ui-btn--sm"
              data-testid="candidate-insights-trigger"
              onClick={() => {
                setIsChatOpen(false)
                setIsInsightsOpen(true)
              }}
            >
              Детали
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--primary ui-btn--sm"
              onClick={handleOpenChat}
            >
              Написать
            </button>
          </div>
        )}

        <CandidateModals
          candidateId={candidateId}
          candidate={detail}
          scheduleSlotOpen={showScheduleSlotModal}
          scheduleIntroDayOpen={showScheduleIntroDayModal}
          rejectState={showRejectModal}
          reportPreview={reportPreview}
          attemptPreview={attemptPreview}
          onCloseScheduleSlot={() => setShowScheduleSlotModal(false)}
          onCloseScheduleIntroDay={() => setShowScheduleIntroDayModal(false)}
          onCloseReject={() => setShowRejectModal(null)}
          onCloseReportPreview={() => setReportPreview(null)}
          onCloseAttemptPreview={() => setAttemptPreview(null)}
          onDetailChanged={handleDetailChanged}
        />

        {detail && isInsightsOpen && (
          <CandidateDrawer
            candidateId={candidateId}
            candidate={detail}
            ai={ai}
            statusLabel={statusLabel}
            isOpen={isInsightsOpen}
            onClose={() => setIsInsightsOpen(false)}
            onOpenInterviewScript={() => {
              setIsInsightsOpen(false)
              setIsInterviewScriptOpen(true)
            }}
            onInsertChatDraft={handleInsertChatDraft}
          />
        )}

        {isChatOpen && (
          <CandidateChatDrawer
            candidateId={candidateId}
            channelLabel={chatChannelLabel}
            channelHealth={channelHealth}
            ai={ai}
            isOpen={isChatOpen}
            onClose={() => {
              setIsChatOpen(false)
              if (isMobile) setMobileTab('profile')
            }}
            initialDraftText={chatDraftSeed}
          />
        )}

        {detail && (
          <>
            <RecruitmentScript
              isOpen={isRecruitmentScriptOpen}
              candidateName={detail.fio || `Кандидат #${candidateId}`}
              aiData={{
                test1Section: test1Section || null,
                aiSummary: ai.summaryQuery.data?.summary || null,
              }}
              onClose={() => setIsRecruitmentScriptOpen(false)}
            />
            <ScriptFab
              isOpen={isRecruitmentScriptOpen}
              onClick={() => setIsRecruitmentScriptOpen((v) => !v)}
            />
          </>
        )}
      </div>
    </RoleGuard>
  )
}
