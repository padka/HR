import { useNavigate, useParams } from '@tanstack/react-router'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { CandidateAction } from '@/api/services/candidates'
import { ApiErrorBanner } from '@/app/components/ApiErrorBanner'
import CandidatePipeline from '@/app/components/CandidatePipeline/CandidatePipeline'
import InterviewScript from '@/app/components/InterviewScript/InterviewScript'
import { RoleGuard } from '@/app/components/RoleGuard'
import { useIsMobile } from '@/app/hooks/useIsMobile'
import { useCandidateAi, useCandidateActions, useCandidateDetail } from './candidate-detail.api'
import { CandidateActions } from './CandidateActions'
import { CandidateChatDrawer } from './CandidateChatDrawer'
import { CandidateDrawer } from './CandidateDrawer'
import { CandidateHeader } from './CandidateHeader'
import { CandidateModals } from './CandidateModals'
import { CandidateTests } from './CandidateTests'
import { fitLevelFromScore, getStatusDisplay } from './candidate-detail.constants'
import type { RejectState, ReportPreviewState, TestAttemptPreview } from './candidate-detail.types'
import {
  buildCandidatePipelineData,
  buildTestSections,
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
  const [showScheduleSlotModal, setShowScheduleSlotModal] = useState(false)
  const [showScheduleIntroDayModal, setShowScheduleIntroDayModal] = useState(false)
  const [showRejectModal, setShowRejectModal] = useState<RejectState | null>(null)
  const [reportPreview, setReportPreview] = useState<ReportPreviewState | null>(null)
  const [attemptPreview, setAttemptPreview] = useState<TestAttemptPreview | null>(null)
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [isInsightsOpen, setIsInsightsOpen] = useState(false)
  const [isInterviewScriptOpen, setIsInterviewScriptOpen] = useState(false)
  const [chatDraftSeed, setChatDraftSeed] = useState<{ text: string; nonce: number } | null>(null)

  const pipelineActionsRef = useRef<HTMLDivElement | null>(null)
  const testsSectionRef = useRef<HTMLDivElement | null>(null)

  const detailQuery = useCandidateDetail(candidateId)
  const { actionMutation } = useCandidateActions(candidateId)
  const ai = useCandidateAi(candidateId)

  const detail = detailQuery.data
  const testSections = useMemo(() => buildTestSections(detail), [detail])
  const test1Section = testSections.find((section) => section.key === 'test1')
  const test2Section = testSections.find((section) => section.key === 'test2')

  const candidateJourney = detail?.journey || null
  const archiveInfo = detail?.archive || candidateJourney?.archive || null
  const statusSlug = detail?.candidate_status_slug || null
  const statusDisplay = detail ? getStatusDisplay(statusSlug) : null
  const statusTone = detail?.candidate_status_color || statusDisplay?.tone || 'muted'
  const statusLabel = detail?.candidate_status_display || statusDisplay?.label || 'Нет статуса'
  const rescheduleRequest = formatRescheduleRequest(detail?.reschedule_request)
  const pendingSlotRequest = formatRescheduleRequest(detail?.pending_slot_request || candidateJourney?.pending_slot_request)
  const finalOutcomeDisplay = resolveFinalOutcomeDisplay(candidateJourney, detail?.final_outcome)
  const finalOutcomeReason = detail?.final_outcome_reason || candidateJourney?.final_outcome_reason || null

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

  useEffect(() => {
    setMobileTab('profile')
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
    if (!isMobile) return
    if (!isChatOpen && mobileTab === 'chat') {
      setMobileTab('profile')
    }
  }, [isChatOpen, isMobile, mobileTab])

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
    void detailQuery.refetch()
    void queryClient.invalidateQueries({ queryKey: ['candidates'] })
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
        onSuccess: () => {
          handleDetailChanged()
        },
        onError: (error) => {
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
                    onClick={() => setMobileTab('chat')}
                  >
                    Чат
                  </button>
                </div>
              )}

              {showProfileSection && (
                <>
                  <div className="glass panel cd-header app-page__hero" data-testid="candidate-header">
                    <CandidateHeader
                      candidate={detail}
                      candidateId={candidateId}
                      statusLabel={statusLabel}
                      statusTone={statusTone}
                      showStatus={Boolean(statusDisplay)}
                      headerAiScore={headerAiScore}
                      headerAiLevel={headerAiLevel}
                      headerAiRecommendation={headerAiRecommendation}
                      isAiFetching={ai.summaryQuery.isFetching}
                      onBack={() => navigate({ to: '/app/candidates' })}
                    />
                    <CandidateActions
                      candidate={detail}
                      statusSlug={statusSlug}
                      test2Section={test2Section}
                      isInsightsOpen={isInsightsOpen}
                      isInterviewScriptOpen={isInterviewScriptOpen}
                      actionPending={actionMutation.isPending}
                      actionsRef={pipelineActionsRef}
                      onOpenDetails={() => {
                        setIsChatOpen(false)
                        setIsInsightsOpen(true)
                      }}
                      onOpenChat={handleOpenChat}
                      onToggleScript={() => {
                        setIsInsightsOpen(false)
                        setIsChatOpen(false)
                        setIsInterviewScriptOpen((prev) => !prev)
                      }}
                      onScheduleSlot={() => setShowScheduleSlotModal(true)}
                      onScheduleIntroDay={() => setShowScheduleIntroDayModal(true)}
                      onActionClick={handleActionClick}
                    />
                  </div>

                  {pipelineData && (
                    <CandidatePipeline
                      currentStateLabel={candidateJourney?.state_label || statusLabel}
                      stages={pipelineData.stages}
                      initialStageId={pipelineData.currentStage}
                      isMobile={isMobile}
                    />
                  )}

                  {actionMessage && <p className="subtitle subtitle--center cd-action-message">{actionMessage}</p>}
                </>
              )}

              {showTestsSection && (
                <CandidateTests
                  testSections={testSections}
                  sectionRef={testsSectionRef}
                  onOpenReportPreview={(title, url) => setReportPreview({ title, url })}
                  onOpenAttemptPreview={(testTitle, attempt) => setAttemptPreview({ testTitle, attempt })}
                />
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
            isOpen={isChatOpen}
            onClose={() => setIsChatOpen(false)}
            initialDraftText={chatDraftSeed}
          />
        )}
      </div>
    </RoleGuard>
  )
}
