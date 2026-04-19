import { useNavigate, useParams } from '@tanstack/react-router'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import '@/theme/pages/candidate-detail.css'
import type { CandidateAction, CandidateActionResponse } from '@/api/services/candidates'
import { ApiErrorBanner } from '@/app/components/ApiErrorBanner'
import CandidatePipeline from '@/app/components/CandidatePipeline/CandidatePipeline'
import InterviewScript from '@/app/components/InterviewScript/InterviewScript'
import { RecruitmentScript, ScriptFab } from '@/app/components/RecruitmentScript/RecruitmentScript'
import { RoleGuard } from '@/app/components/RoleGuard'
import { useIsMobile } from '@/app/hooks/useIsMobile'
import { useCandidateAi, useCandidateActions, useCandidateChannelHealth, useCandidateDetail } from './candidate-detail.api'
import { CandidateActions } from './CandidateActions'
import { CandidateChatDrawer } from './CandidateChatDrawer'
import { CandidateDrawer } from './CandidateDrawer'
import { CandidateHeader } from './CandidateHeader'
import { CandidateModals } from './CandidateModals'
import { fitLevelFromScore, getStatusDisplay } from './candidate-detail.constants'
import type {
  RejectState,
  ReportPreviewState,
  TestAttemptPreview,
} from './candidate-detail.types'
import {
  buildCandidatePipelineData,
  buildTestSections,
  resolveFinalOutcomeDisplay,
} from './candidate-detail.utils'

export function CandidateDetailPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const params = useParams({ from: '/app/candidates/$candidateId' })
  const isMobile = useIsMobile()
  const candidateId = Number(params.candidateId)

  const [mobileTab, setMobileTab] = useState<'profile' | 'chat'>('profile')
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [lastActionResponse, setLastActionResponse] = useState<CandidateActionResponse | null>(null)
  const [showScheduleSlotModal, setShowScheduleSlotModal] = useState(false)
  const [showScheduleIntroDayModal, setShowScheduleIntroDayModal] = useState(false)
  const [showRejectModal, setShowRejectModal] = useState<RejectState | null>(null)
  const [showTestsModal, setShowTestsModal] = useState(false)
  const [showHhModal, setShowHhModal] = useState(false)
  const [reportPreview, setReportPreview] = useState<ReportPreviewState | null>(null)
  const [attemptPreview, setAttemptPreview] = useState<TestAttemptPreview | null>(null)
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [isInsightsOpen, setIsInsightsOpen] = useState(false)
  const [isInterviewScriptOpen, setIsInterviewScriptOpen] = useState(false)
  const [chatDraftSeed, setChatDraftSeed] = useState<{ text: string; nonce: number } | null>(null)
  const [isRecruitmentScriptOpen, setIsRecruitmentScriptOpen] = useState(false)

  const pipelineActionsRef = useRef<HTMLDivElement | null>(null)

  const detailQuery = useCandidateDetail(candidateId)
  const { actionMutation } = useCandidateActions(candidateId)
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
  const finalOutcomeDisplay = resolveFinalOutcomeDisplay(candidateJourney, detail?.final_outcome)
  const finalOutcomeReason = detail?.final_outcome_reason || candidateJourney?.final_outcome_reason || null
  const preferredChannel = channelHealth?.preferred_channel || detail?.messenger_platform
  const chatChannelLabel = preferredChannel === 'max' ? 'MAX' : preferredChannel === 'telegram' ? 'Telegram' : 'CRM'

  const pipelineData = useMemo(() => {
    if (!detail) return null
    return buildCandidatePipelineData({
      detail,
      statusSlug,
      statusLabel,
      candidateJourney,
      archiveInfo,
      pendingSlotRequest: null,
      rescheduleRequest: null,
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
    setLastActionResponse(null)
    setShowTestsModal(false)
    setShowHhModal(false)
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
    setShowTestsModal(true)
  }, [candidateId])

  const handleDetailChanged = (message = 'Действие выполнено') => {
    setActionMessage(message)
    setLastActionResponse(null)
    void queryClient.invalidateQueries({ queryKey: ['candidate-detail', candidateId] })
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

  const showProfileSection = !isMobile || mobileTab === 'profile'

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
                    className={`ui-btn ui-btn--sm ${showTestsModal ? 'ui-btn--primary' : 'ui-btn--ghost'}`}
                    onClick={() => setShowTestsModal(true)}
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
                    showInsightsAction
                    actionsRef={pipelineActionsRef}
                    onOpenChat={handleOpenChat}
                    onOpenTests={() => setShowTestsModal(true)}
                    onOpenInsights={() => {
                      setIsChatOpen(false)
                      setIsInsightsOpen(true)
                    }}
                    onOpenHh={() => setShowHhModal(true)}
                    onScheduleSlot={() => setShowScheduleSlotModal(true)}
                    onScheduleIntroDay={() => setShowScheduleIntroDayModal(true)}
                    onActionClick={handleActionClick}
                  />

                  <div className="cd-detail-grid" data-testid="candidate-detail-sections">
                    <section className="cd-profile__section cd-detail-section cd-detail-section--journey" data-testid="candidate-detail-lifecycle">
                      <div className="cd-section-header">
                        <h2 className="cd-section-title">Путь кандидата</h2>
                      </div>
                      {pipelineData && (
                        <CandidatePipeline
                          currentStateLabel={candidateJourney?.state_label || statusLabel}
                          stages={pipelineData.stages}
                          isMobile={isMobile}
                        />
                      )}
                    </section>
                  </div>

                  {actionMessage && <p className="subtitle subtitle--center cd-action-message">{actionMessage}</p>}
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
              onClick={() => setShowTestsModal(true)}
            >
              Тесты
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--ghost ui-btn--sm"
              onClick={() => {
                setIsChatOpen(false)
                setIsInsightsOpen(true)
              }}
            >
              Инсайты
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
          testsOpen={showTestsModal}
          testSections={testSections}
          hhProfileOpen={showHhModal}
          reportPreview={reportPreview}
          attemptPreview={attemptPreview}
          onCloseScheduleSlot={() => setShowScheduleSlotModal(false)}
          onCloseScheduleIntroDay={() => setShowScheduleIntroDayModal(false)}
          onCloseReject={() => setShowRejectModal(null)}
          onCloseTests={() => setShowTestsModal(false)}
          onCloseHhProfile={() => setShowHhModal(false)}
          onCloseReportPreview={() => setReportPreview(null)}
          onCloseAttemptPreview={() => setAttemptPreview(null)}
          onOpenReportPreview={(title, url) => setReportPreview({ title, url })}
          onOpenAttemptPreview={(testTitle, attempt) => setAttemptPreview({ testTitle, attempt })}
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
