import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'

import {
  refreshCandidateInterviewScript,
  submitCandidateInterviewScriptFeedback,
  type InterviewScriptFeedbackPayload,
  type InterviewScriptPayload,
} from '@/api/services/candidates'

import { buildInterviewScriptViewModel } from './script.prompts'
import type {
  InterviewScriptBaseContext,
  InterviewScriptDraft,
  InterviewScriptQuestionState,
  InterviewScriptStep,
  InterviewScriptViewModel,
} from './script.types'

const STORAGE_VERSION = 1

function storageKey(candidateId: number) {
  return `candidate-interview-script:${candidateId}:v${STORAGE_VERSION}`
}

function parseStoredDraft(candidateId: number): InterviewScriptDraft | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(storageKey(candidateId))
    if (!raw) return null
    return JSON.parse(raw) as InterviewScriptDraft
  } catch {
    return null
  }
}

function saveStoredDraft(candidateId: number, draft: InterviewScriptDraft | null) {
  if (typeof window === 'undefined') return
  const key = storageKey(candidateId)
  if (!draft) {
    window.localStorage.removeItem(key)
    return
  }
  window.localStorage.setItem(key, JSON.stringify(draft))
}

function defaultQuestionState(viewModel: InterviewScriptViewModel): Record<string, InterviewScriptQuestionState> {
  return Object.fromEntries(
    viewModel.questions.map((question) => [
      question.id,
      {
        notes: '',
        rating: null,
        skipped: false,
      },
    ]),
  )
}

function buildSteps(viewModel: InterviewScriptViewModel): InterviewScriptStep[] {
  return [
    { id: 'briefing', label: 'Брифинг', kind: 'briefing' },
    { id: 'opening', label: 'Открытие', kind: 'opening' },
    ...viewModel.questions.map((question, index) => ({
      id: `question-${question.id}`,
      label: `Вопрос ${index + 1}`,
      kind: 'question' as const,
      questionId: question.id,
    })),
    { id: 'closing', label: 'Завершение', kind: 'closing' },
    { id: 'scorecard', label: 'Итог', kind: 'scorecard' },
  ]
}

function clampStep(step: number, total: number) {
  return Math.max(0, Math.min(step, Math.max(0, total - 1)))
}

export function useInterviewScript({
  candidateId,
  candidateName,
  statusLabel,
  test1Section,
  onSaved,
}: InterviewScriptBaseContext & {
  candidateId: number
  onSaved?: () => void
}) {
  const queryClient = useQueryClient()
  const [phase, setPhase] = useState<'idle' | 'loading' | 'error' | 'ready' | 'saving' | 'saved'>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [viewModel, setViewModel] = useState<InterviewScriptViewModel | null>(null)
  const [rawScript, setRawScript] = useState<InterviewScriptPayload | null>(null)
  const [questionState, setQuestionState] = useState<Record<string, InterviewScriptQuestionState>>({})
  const [currentStep, setCurrentStep] = useState(0)
  const [startedAt, setStartedAt] = useState<number | null>(null)
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null)
  const [overallRecommendation, setOverallRecommendation] = useState<'recommend' | 'doubt' | 'not_recommend'>('doubt')
  const [finalComment, setFinalComment] = useState('')
  const [elapsedSec, setElapsedSec] = useState(0)

  const prepareMutation = useMutation({
    mutationFn: () => refreshCandidateInterviewScript(candidateId),
    onSuccess: (data) => {
      const nextViewModel = buildInterviewScriptViewModel(data.script, { candidateName, statusLabel, test1Section })
      const now = Date.now()
      setRawScript(data.script)
      setViewModel(nextViewModel)
      setQuestionState(defaultQuestionState(nextViewModel))
      setCurrentStep(0)
      setStartedAt(now)
      setElapsedSec(0)
      setLastSavedAt(null)
      setOverallRecommendation('doubt')
      setFinalComment('')
      setErrorMessage(null)
      setPhase('ready')
      queryClient.setQueryData(['ai-interview-script', candidateId], data)
    },
    onError: (error: unknown) => {
      const nextViewModel = buildInterviewScriptViewModel(
        {
          stage_label: 'Шаблонный сценарий',
          call_goal: `Понять реальную релевантность кандидата и принять решение по следующему шагу.`,
          conversation_script: '',
          risk_flags: [],
          highlights: [],
          checks: [],
          objections: [],
          script_blocks: [],
          cta_templates: [],
        },
        { candidateName, statusLabel, test1Section },
      )
      const now = Date.now()
      setRawScript(nextViewModel.rawScript)
      setViewModel(nextViewModel)
      setQuestionState(defaultQuestionState(nextViewModel))
      setCurrentStep(0)
      setStartedAt(now)
      setElapsedSec(0)
      setLastSavedAt(null)
      setOverallRecommendation('doubt')
      setFinalComment('')
      setErrorMessage((error as Error).message || 'Не удалось подготовить скрипт интервью.')
      setPhase('error')
    },
  })

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!rawScript || !viewModel) {
        throw new Error('Скрипт ещё не подготовлен')
      }
      const questionItems = viewModel.questions.map((question) => ({
        question_id: question.id,
        rating: questionState[question.id]?.rating ?? null,
        skipped: Boolean(questionState[question.id]?.skipped),
        notes: questionState[question.id]?.notes?.trim() || null,
      }))
      const rated = questionItems.filter((item) => !item.skipped && item.rating != null)
      const averageRating = rated.length > 0
        ? rated.reduce((sum, item) => sum + Number(item.rating || 0), 0) / rated.length
        : null
      const payload: InterviewScriptFeedbackPayload = {
        helped: true,
        edited: false,
        quick_reasons: [],
        final_script: rawScript,
        outcome: 'unknown',
        outcome_reason: null,
        scorecard: {
          completed_questions: questionItems.filter((item) => item.skipped || item.rating != null || item.notes).length,
          total_questions: viewModel.questions.length,
          average_rating: averageRating,
          overall_recommendation: overallRecommendation,
          final_comment: finalComment.trim() || null,
          timer_elapsed_sec: elapsedSec,
          items: questionItems,
        },
        idempotency_key: `isf-${candidateId}-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`,
      }
      return submitCandidateInterviewScriptFeedback(candidateId, payload)
    },
    onMutate: () => {
      setPhase('saving')
    },
    onSuccess: () => {
      setPhase('saved')
      saveStoredDraft(candidateId, null)
      queryClient.invalidateQueries({ queryKey: ['candidate-detail', candidateId] })
      onSaved?.()
    },
    onError: (error: unknown) => {
      setErrorMessage((error as Error).message || 'Не удалось сохранить результат интервью.')
      setPhase('ready')
    },
  })

  const steps = useMemo(() => (viewModel ? buildSteps(viewModel) : []), [viewModel])
  const activeStep = steps[clampStep(currentStep, steps.length)] || null

  useEffect(() => {
    const draft = parseStoredDraft(candidateId)
    if (!draft) {
      setPhase('idle')
      setViewModel(null)
      setRawScript(null)
      setQuestionState({})
      setCurrentStep(0)
      setStartedAt(null)
      setElapsedSec(0)
      setLastSavedAt(null)
      setOverallRecommendation('doubt')
      setFinalComment('')
      setErrorMessage(null)
      return
    }
    setRawScript(draft.script)
    setViewModel(draft.viewModel)
    setQuestionState(draft.questionState || defaultQuestionState(draft.viewModel))
    setCurrentStep(clampStep(draft.currentStep || 0, buildSteps(draft.viewModel).length))
    setStartedAt(draft.startedAt || Date.now())
    setOverallRecommendation(draft.overallRecommendation || 'doubt')
    setFinalComment(draft.finalComment || '')
    setLastSavedAt(draft.savedAt || null)
    setErrorMessage(null)
    setPhase('ready')
  }, [candidateId])

  useEffect(() => {
    if (phase === 'idle' || !viewModel || !rawScript || !startedAt) return
    const timeout = window.setTimeout(() => {
      saveStoredDraft(candidateId, {
        script: rawScript,
        viewModel,
        currentStep,
        startedAt,
        savedAt: new Date().toISOString(),
        questionState,
        overallRecommendation,
        finalComment,
      })
      setLastSavedAt(new Date().toISOString())
    }, 1000)
    return () => window.clearTimeout(timeout)
  }, [candidateId, currentStep, finalComment, overallRecommendation, phase, questionState, rawScript, startedAt, viewModel])

  useEffect(() => {
    if (!startedAt || (phase !== 'ready' && phase !== 'error' && phase !== 'saving')) return
    const update = () => setElapsedSec(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)))
    update()
    const timer = window.setInterval(update, 1000)
    return () => window.clearInterval(timer)
  }, [phase, startedAt])

  const prepare = () => {
    setPhase('loading')
    setErrorMessage(null)
    prepareMutation.mutate()
  }

  const goToStep = (step: number) => {
    setCurrentStep(clampStep(step, steps.length))
  }

  const nextStep = () => {
    setCurrentStep((prev) => clampStep(prev + 1, steps.length))
  }

  const prevStep = () => {
    setCurrentStep((prev) => clampStep(prev - 1, steps.length))
  }

  const setQuestionNotes = (questionId: string, notes: string) => {
    setQuestionState((prev) => ({
      ...prev,
      [questionId]: {
        notes,
        rating: prev[questionId]?.rating ?? null,
        skipped: prev[questionId]?.skipped ?? false,
      },
    }))
  }

  const setQuestionRating = (questionId: string, rating: number) => {
    setQuestionState((prev) => ({
      ...prev,
      [questionId]: {
        notes: prev[questionId]?.notes ?? '',
        rating,
        skipped: false,
      },
    }))
  }

  const toggleQuestionSkipped = (questionId: string) => {
    setQuestionState((prev) => ({
      ...prev,
      [questionId]: {
        notes: prev[questionId]?.notes ?? '',
        rating: prev[questionId]?.rating ?? null,
        skipped: !prev[questionId]?.skipped,
      },
    }))
  }

  return {
    phase,
    errorMessage,
    viewModel,
    rawScript,
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
    save: () => saveMutation.mutate(),
    isPreparing: prepareMutation.isPending,
    isSaving: saveMutation.isPending,
  }
}
