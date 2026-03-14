/*
Layout decision: desktop uses a persistent resizable split-panel docked to the right of the candidate page.
Rationale:
1. Recruiter sees the script during the whole 15–30 minute interview without modal blocking.
2. Action rail, pipeline, tests and candidate card stay visible in the left column.
3. The panel does not replace the existing details drawer pattern; it acts as a working surface for the interview itself.
4. Mobile falls back to a sheet because split-view loses value on narrow screens.
*/
import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'

import type { TestSection } from '@/api/services/candidates'

import ScriptBriefing from './ScriptBriefing'
import ScriptQuestion from './ScriptQuestion'
import ScriptScorecard from './ScriptScorecard'
import ScriptStepper from './ScriptStepper'
import ScriptTimer from './ScriptTimer'
import { scriptPanelVariants, scriptStepVariants } from './script.variants'
import { useInterviewScript } from './useInterviewScript'
import './interview-script.css'

type InterviewScriptProps = {
  candidateId: number
  candidateName: string
  statusLabel: string
  test1Section?: TestSection | null
  isOpen: boolean
  isMobile: boolean
  onClose: () => void
  onSaved?: () => void
}

const PANEL_WIDTH_KEY = 'candidate-interview-script-width'

export default function InterviewScript({
  candidateId,
  candidateName,
  statusLabel,
  test1Section,
  isOpen,
  isMobile,
  onClose,
  onSaved,
}: InterviewScriptProps) {
  const reduceMotion = useReducedMotion()
  const panelRef = useRef<HTMLDivElement | null>(null)
  const [panelWidth, setPanelWidth] = useState(460)

  const {
    phase,
    errorMessage,
    viewModel,
    questionState,
    activeStep,
    steps,
    currentStep,
    elapsedSec,
    lastSavedAt,
    overallRecommendation,
    finalComment,
    prepare,
    goToStep,
    nextStep,
    prevStep,
    setQuestionNotes,
    setQuestionRating,
    toggleQuestionSkipped,
    setOverallRecommendation,
    setFinalComment,
    save,
    isPreparing,
    isSaving,
  } = useInterviewScript({
    candidateId,
    candidateName,
    statusLabel,
    test1Section,
    onSaved,
  })

  useEffect(() => {
    if (typeof window === 'undefined') return
    const stored = Number(window.localStorage.getItem(PANEL_WIDTH_KEY) || 460)
    if (Number.isFinite(stored)) {
      setPanelWidth(Math.min(560, Math.max(380, stored)))
    }
  }, [])

  useEffect(() => {
    if (!isOpen || typeof window === 'undefined') return
    window.localStorage.setItem(PANEL_WIDTH_KEY, String(panelWidth))
  }, [isOpen, panelWidth])

  useEffect(() => {
    if (!isOpen) return
    panelRef.current?.focus()
  }, [isOpen, currentStep])

  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
        return
      }
      if (event.key === 'Enter') {
        const target = event.target as HTMLElement | null
        if (target?.tagName === 'TEXTAREA') return
        if (activeStep?.kind === 'scorecard') return
        event.preventDefault()
        nextStep()
        return
      }
      if (activeStep?.kind === 'question' && ['1', '2', '3', '4', '5'].includes(event.key)) {
        event.preventDefault()
        setQuestionRating(activeStep.questionId, Number(event.key))
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [activeStep, isOpen, nextStep, onClose, setQuestionRating])

  const completedQuestions = useMemo(() => {
    if (!viewModel) return 0
    return viewModel.questions.filter((question) => {
      const state = questionState[question.id]
      return Boolean(state?.skipped || state?.rating != null || state?.notes?.trim())
    }).length
  }, [questionState, viewModel])

  const totalQuestions = viewModel?.questions.length || 0
  const progressPercent = totalQuestions > 0 ? Math.round((completedQuestions / totalQuestions) * 100) : 0

  const startResize = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.preventDefault()
    const startX = event.clientX
    const initialWidth = panelWidth
    const move = (nextEvent: MouseEvent) => {
      const delta = startX - nextEvent.clientX
      setPanelWidth(Math.max(380, Math.min(560, initialWidth + delta)))
    }
    const stop = () => {
      document.removeEventListener('mousemove', move)
      document.removeEventListener('mouseup', stop)
    }
    document.addEventListener('mousemove', move)
    document.addEventListener('mouseup', stop)
  }

  const renderStepContent = () => {
    if (!viewModel || !activeStep) return null
    if (activeStep.kind === 'briefing') {
      return (
        <ScriptBriefing
          candidateName={candidateName}
          statusLabel={statusLabel}
          test1Score={test1Section?.details?.stats?.final_score}
          goal={viewModel.goal}
          focusAreas={viewModel.briefingFocusAreas}
          flags={viewModel.briefingFlags}
        />
      )
    }
    if (activeStep.kind === 'opening') {
      return (
        <div className="interview-script__surface">
          <div className="interview-script__eyebrow">Старт разговора</div>
          <h3 className="interview-script__section-title">Открытие</h3>
          <div className="interview-script__callout">
            <div className="interview-script__callout-label">Готовая фраза</div>
            <p>{viewModel.greeting}</p>
          </div>
          <div className="interview-script__stack">
            <div className="interview-script__stack-title">Ice-breaker вопросы</div>
            <ul className="interview-script__bullet-list">
              {viewModel.icebreakers.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
      )
    }
    if (activeStep.kind === 'question') {
      const question = viewModel.questions.find((item) => item.id === activeStep.questionId)
      if (!question) return null
      const questionIndex = viewModel.questions.findIndex((item) => item.id === question.id)
      const state = questionState[question.id] || { notes: '', rating: null, skipped: false }
      return (
        <ScriptQuestion
          question={question}
          index={questionIndex}
          total={viewModel.questions.length}
          notes={state.notes}
          rating={state.rating}
          skipped={state.skipped}
          onNotesChange={(value) => setQuestionNotes(question.id, value)}
          onRatingChange={(value) => setQuestionRating(question.id, value)}
          onSkip={() => toggleQuestionSkipped(question.id)}
          onNext={nextStep}
        />
      )
    }
    if (activeStep.kind === 'closing') {
      return (
        <div className="interview-script__surface">
          <div className="interview-script__eyebrow">Финал разговора</div>
          <h3 className="interview-script__section-title">Завершение</h3>
          <div className="interview-script__callout">
            <div className="interview-script__callout-label">Фраза для закрытия</div>
            <p>{viewModel.closingPhrase}</p>
          </div>
          <div className="interview-script__stack">
            <div className="interview-script__stack-title">Не забыть спросить</div>
            <ul className="interview-script__bullet-list">
              {viewModel.closingChecklist.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
      )
    }
    return (
      <ScriptScorecard
        viewModel={viewModel}
        questionState={questionState}
        overallRecommendation={overallRecommendation}
        finalComment={finalComment}
        onRecommendationChange={setOverallRecommendation}
        onCommentChange={setFinalComment}
        onSave={save}
        isSaving={isSaving}
      />
    )
  }

  if (!isOpen) {
    return null
  }

  const panelContent = (
    <motion.aside
      ref={panelRef}
      className={`interview-script ${isMobile ? 'interview-script--sheet' : 'interview-script--desktop'} glass`}
      style={!isMobile ? { width: panelWidth } : undefined}
      variants={reduceMotion ? undefined : scriptPanelVariants}
      initial={reduceMotion ? undefined : 'hidden'}
      animate={reduceMotion ? undefined : 'visible'}
      exit={reduceMotion ? undefined : 'exit'}
      tabIndex={-1}
      data-testid="interview-script-panel"
    >
      {!isMobile && (
        <button
          type="button"
          className="interview-script__resize-handle"
          aria-label="Изменить ширину панели скрипта"
          onMouseDown={startResize}
        />
      )}
      <div className="interview-script__header">
        <div>
          <div className="interview-script__eyebrow">Скрипт интервью 2.0</div>
          <h2 className="interview-script__title">Пошаговый сценарий</h2>
          <p className="interview-script__subtitle">
            Скрипт остаётся рядом с карточкой кандидата и не блокирует воронку, тесты и действия.
          </p>
        </div>
        <div className="interview-script__header-actions">
          <ScriptTimer seconds={elapsedSec} />
          <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={onClose}>
            Закрыть
          </button>
        </div>
      </div>

      <div className="interview-script__progress">
        <div className="interview-script__progress-meta">
          <span>Прогресс</span>
          <span>{completedQuestions}/{totalQuestions || 0} вопросов</span>
        </div>
        <div className="interview-script__progress-rail" aria-hidden="true">
          <motion.div
            className="interview-script__progress-fill"
            animate={{ width: `${progressPercent}%` }}
            transition={reduceMotion ? { duration: 0 } : { duration: 0.4, ease: [0.25, 0.1, 0.25, 1] }}
          />
        </div>
      </div>

      {lastSavedAt && phase !== 'saved' && (
        <div className="interview-script__autosave">Черновик сохранён {new Date(lastSavedAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}</div>
      )}

      {(phase === 'idle' || phase === 'loading') && (
        <div className="interview-script__empty">
          <div className="interview-script__empty-title">Подготовить скрипт интервью</div>
          <p className="interview-script__empty-text">
            Сгенерируем вопросы под конкретного кандидата на основе результатов Теста 1 и текущего этапа воронки.
          </p>
          <button type="button" className="ui-btn ui-btn--primary" onClick={prepare} disabled={isPreparing}>
            {isPreparing || phase === 'loading' ? 'Готовим…' : 'Подготовить скрипт интервью'}
          </button>
        </div>
      )}

      {phase !== 'idle' && phase !== 'loading' && viewModel && (
        <>
          <ScriptStepper steps={steps} currentStep={currentStep} onSelect={goToStep} />

          {errorMessage && (
            <div className="interview-script__alert">
              {phase === 'error' ? 'AI недоступен, открыт резервный сценарий. ' : ''}
              {errorMessage}
            </div>
          )}

          <div className="interview-script__body">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeStep?.id || 'empty'}
                variants={reduceMotion ? undefined : scriptStepVariants}
                initial={reduceMotion ? undefined : 'hidden'}
                animate={reduceMotion ? undefined : 'visible'}
                exit={reduceMotion ? undefined : 'exit'}
              >
                {renderStepContent()}
              </motion.div>
            </AnimatePresence>
          </div>

          {activeStep?.kind !== 'question' && activeStep?.kind !== 'scorecard' && (
            <div className="interview-script__footer">
              <button type="button" className="ui-btn ui-btn--ghost" onClick={prevStep} disabled={currentStep === 0}>
                Назад
              </button>
              <button type="button" className="ui-btn ui-btn--primary" onClick={nextStep}>
                Далее
              </button>
            </div>
          )}
          {activeStep?.kind === 'scorecard' && phase === 'saved' && (
            <div className="interview-script__footer">
              <div className="interview-script__success">Результат интервью сохранён.</div>
            </div>
          )}
        </>
      )}
    </motion.aside>
  )

  if (isMobile) {
    return createPortal(
      <div className="drawer-overlay" onClick={(event) => event.target === event.currentTarget && onClose()}>
        {panelContent}
      </div>,
      document.body,
    )
  }

  return panelContent
}
