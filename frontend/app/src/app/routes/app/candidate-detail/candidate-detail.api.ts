import { useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  applyCandidateAction,
  createCandidateMaxLink,
  fetchCandidateAiCoach,
  fetchCandidateAiSummary,
  fetchCandidateChat,
  fetchCandidateChatDrafts,
  fetchCandidateCoachDrafts,
  fetchCandidateCohortComparison,
  fetchCandidateDetail,
  fetchCandidateHHSummary,
  fetchCities,
  markCandidateChatRead,
  refreshCandidateAiCoach,
  refreshCandidateAiSummary,
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

  const draftsMutation = useMutation({
    mutationFn: (mode: 'short' | 'neutral' | 'supportive') => fetchCandidateChatDrafts(candidateId, mode),
  })

  const coachDraftsMutation = useMutation({
    mutationFn: (mode: 'short' | 'neutral' | 'supportive') => fetchCandidateCoachDrafts(candidateId, mode),
  })

  const resumeMutation = useMutation({
    mutationFn: (resumeText: string) => upsertCandidateAiResume(candidateId, { format: 'raw_text', resume_text: resumeText }),
  })

  return {
    summaryQuery,
    coachQuery,
    refreshSummaryMutation,
    refreshCoachMutation,
    draftsMutation,
    coachDraftsMutation,
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

  const createMaxLinkMutation = useMutation({
    mutationFn: () => createCandidateMaxLink(candidateId),
  })

  return {
    actionMutation,
    scheduleInterviewMutation,
    scheduleIntroDayMutation,
    createMaxLinkMutation,
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
