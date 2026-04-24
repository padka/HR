import { useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  applyCandidateAction,
  fetchCandidateChannelHealth,
  fetchCandidateAiCoach,
  fetchCandidateAiFacts,
  fetchCandidateAiNextBestAction,
  fetchCandidateAiSummary,
  fetchCandidateChat,
  fetchCandidateContactDrafts,
  fetchCandidateChatDrafts,
  fetchCandidateCoachDrafts,
  fetchCandidateCohortComparison,
  fetchCandidateDetail,
  fetchCandidateHHSummary,
  fetchCities,
  issueCandidateMaxLaunchInvite,
  markCandidateChatRead,
  refreshCandidateAiCoach,
  refreshCandidateAiFacts,
  refreshCandidateAiNextBestAction,
  refreshCandidateAiSummary,
  saveCandidateAiNextBestActionFeedback,
  revokeCandidateMaxLaunchInvite,
  scheduleCandidateInterview,
  scheduleCandidateIntroDay,
  sendCandidateChatMessage,
  upsertCandidateAiResume,
  waitForCandidateChat,
} from '@/api/services/candidates'

export function useCandidateDetail(candidateId: number) {
  return useQuery({
    queryKey: ['candidate-detail', candidateId],
    queryFn: () => fetchCandidateDetail(candidateId),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
}

export function useCandidateChannelHealth(candidateId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['candidate-channel-health', candidateId],
    queryFn: () => fetchCandidateChannelHealth(candidateId),
    enabled: enabled && Boolean(candidateId),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
}

export function useCandidateHh(candidateId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['candidate-hh-summary', candidateId],
    queryFn: () => fetchCandidateHHSummary(candidateId),
    enabled,
    retry: false,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
}

export function useCandidateCohort(candidateId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['candidate-cohort-comparison', candidateId],
    queryFn: () => fetchCandidateCohortComparison(candidateId),
    enabled,
    retry: false,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
}

export function useCandidateChat(candidateId: number, enabled: boolean) {
  const queryClient = useQueryClient()
  const threadQueryKey = ['candidate-chat-threads', 'inbox'] as const
  const chatQuery = useQuery({
    queryKey: ['candidate-chat', candidateId],
    queryFn: () => fetchCandidateChat(candidateId, 50),
    enabled,
    staleTime: 15_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  const markReadMutation = useMutation({
    mutationFn: markCandidateChatRead,
    onSuccess: (_data, readCandidateId) => {
      const applyReadState = (queryKey: readonly unknown[]) => {
        queryClient.setQueryData<{ threads?: Array<{ candidate_id: number; unread_count?: number }> }>(
          queryKey,
          (prev) => {
            if (!prev?.threads) return prev
            return {
              ...prev,
              threads: prev.threads.map((thread) =>
                thread.candidate_id === readCandidateId ? { ...thread, unread_count: 0 } : thread,
              ),
            }
          },
        )
      }
      applyReadState(['candidate-chat-threads'])
      applyReadState(threadQueryKey)
    },
  })

  const sendMutation = useMutation({
    mutationFn: async (text: string) => sendCandidateChatMessage(candidateId, text, String(Date.now())),
  })

  const waitForUpdates = useCallback(
    (params?: { since?: string | null; timeout?: number; limit?: number; signal?: AbortSignal }) =>
      waitForCandidateChat(candidateId, params),
    [candidateId],
  )

  return {
    query: chatQuery,
    data: chatQuery.data,
    isLoading: chatQuery.isLoading,
    error: chatQuery.error,
    refetch: chatQuery.refetch,
    markReadMutation,
    sendMutation,
    waitForUpdates,
  }
}

export function useCandidateAi(candidateId: number) {
  const queryClient = useQueryClient()

  const summaryQuery = useQuery({
    queryKey: ['ai-summary', candidateId],
    queryFn: () => fetchCandidateAiSummary(candidateId),
    enabled: Boolean(candidateId),
    retry: false,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  const coachQuery = useQuery({
    queryKey: ['ai-coach', candidateId],
    queryFn: () => fetchCandidateAiCoach(candidateId),
    enabled: false,
    retry: false,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  const factsQuery = useQuery({
    queryKey: ['ai-facts', candidateId],
    queryFn: () => fetchCandidateAiFacts(candidateId),
    enabled: false,
    retry: false,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  const nextBestActionQuery = useQuery({
    queryKey: ['ai-next-best-action', candidateId],
    queryFn: () => fetchCandidateAiNextBestAction(candidateId),
    enabled: false,
    retry: false,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  const refreshSummaryMutation = useMutation({
    mutationFn: () => refreshCandidateAiSummary(candidateId),
    onSuccess: (data) => {
      queryClient.setQueryData(['ai-summary', candidateId], data)
    },
  })

  const refreshCoachMutation = useMutation({
    mutationFn: () => refreshCandidateAiCoach(candidateId),
    onSuccess: (data) => {
      queryClient.setQueryData(['ai-coach', candidateId], data)
    },
  })

  const refreshFactsMutation = useMutation({
    mutationFn: () => refreshCandidateAiFacts(candidateId),
    onSuccess: (data) => {
      queryClient.setQueryData(['ai-facts', candidateId], data)
    },
  })

  const refreshNextBestActionMutation = useMutation({
    mutationFn: () => refreshCandidateAiNextBestAction(candidateId),
    onSuccess: (data) => {
      queryClient.setQueryData(['ai-next-best-action', candidateId], data)
    },
  })

  const draftsMutation = useMutation({
    mutationFn: (mode: 'short' | 'neutral' | 'supportive') => fetchCandidateChatDrafts(candidateId, mode),
  })

  const coachDraftsMutation = useMutation({
    mutationFn: (mode: 'short' | 'neutral' | 'supportive') => fetchCandidateCoachDrafts(candidateId, mode),
  })

  const contactDraftsMutation = useMutation({
    mutationFn: (mode: 'short' | 'neutral' | 'supportive') => fetchCandidateContactDrafts(candidateId, mode),
  })

  const nextBestActionFeedbackMutation = useMutation({
    mutationFn: (payload: { action: 'accept' | 'dismiss' | 'edit_and_send'; note?: string | null }) =>
      saveCandidateAiNextBestActionFeedback(candidateId, payload),
    onSuccess: (data) => {
      queryClient.setQueryData(['ai-next-best-action-feedback', candidateId], data)
      queryClient.setQueryData(['ai-next-best-action', candidateId], (prev: any) => {
        if (!prev?.recommendation || !data?.feedback_state) return prev
        return {
          ...prev,
          recommendation: {
            ...prev.recommendation,
            feedback_state: data.feedback_state,
          },
        }
      })
    },
  })

  const resumeMutation = useMutation({
    mutationFn: (resumeText: string) => upsertCandidateAiResume(candidateId, { format: 'raw_text', resume_text: resumeText }),
  })

  return {
    summaryQuery,
    coachQuery,
    factsQuery,
    nextBestActionQuery,
    refreshSummaryMutation,
    refreshCoachMutation,
    refreshFactsMutation,
    refreshNextBestActionMutation,
    draftsMutation,
    coachDraftsMutation,
    contactDraftsMutation,
    nextBestActionFeedbackMutation,
    resumeMutation,
  }
}

export type CandidateAiController = ReturnType<typeof useCandidateAi>

export function useCandidateActions(candidateId: number) {
  const actionMutation = useMutation({
    mutationFn: ({ actionKey, payload }: { actionKey: string; payload?: unknown }) =>
      applyCandidateAction(candidateId, actionKey, payload),
  })

  const scheduleInterviewMutation = useMutation({
    mutationFn: (payload: { city_id?: number | null; date: string; time: string; custom_message?: string | null; mode?: 'bot' | 'manual_silent' }) =>
      scheduleCandidateInterview(candidateId, payload),
  })

  const scheduleIntroDayMutation = useMutation({
    mutationFn: (payload: { date: string; time: string; city_id?: number | null; custom_message?: string | null }) =>
      scheduleCandidateIntroDay(candidateId, payload),
  })
  return {
    actionMutation,
    scheduleInterviewMutation,
    scheduleIntroDayMutation,
  }
}

export function useCandidateMaxRollout(candidateId: number) {
  const queryClient = useQueryClient()

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['candidate-detail', candidateId] })
    void queryClient.invalidateQueries({ queryKey: ['candidates'] })
  }

  const issueMutation = useMutation({
    mutationFn: (payload: Parameters<typeof issueCandidateMaxLaunchInvite>[1]) =>
      issueCandidateMaxLaunchInvite(candidateId, payload),
    onSuccess: invalidate,
  })

  const revokeMutation = useMutation({
    mutationFn: (applicationId?: number | null) =>
      revokeCandidateMaxLaunchInvite(candidateId, applicationId),
    onSuccess: invalidate,
  })

  return {
    issueMutation,
    revokeMutation,
  }
}

export function useCitiesOptions() {
  return useQuery({
    queryKey: ['cities'],
    queryFn: fetchCities,
    staleTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
}
