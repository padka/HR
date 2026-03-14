import { useEffect, useMemo } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  fetchCandidateChatMessages,
  fetchCandidateChatTemplates,
  fetchCandidateChatThreads,
  markCandidateChatThreadRead,
  sendCandidateThreadMessage,
  waitForCandidateChatMessages,
  waitForCandidateChatThreads,
  type CandidateChatPayload,
  type CandidateChatTemplate,
  type CandidateChatThreadsPayload,
} from '@/api/services/messenger'

import { MESSAGE_LIMIT, THREAD_LIMIT } from './messenger.constants'
import { readThreadCache } from './messenger.utils'

export function useMessengerThreads() {
  const queryClient = useQueryClient()
  const threadQueryKey = useMemo(() => ['candidate-chat-threads', 'all'] as const, [])
  const query = useQuery<CandidateChatThreadsPayload>({
    queryKey: threadQueryKey,
    queryFn: () => fetchCandidateChatThreads({ folder: 'all', limit: THREAD_LIMIT }),
    refetchOnWindowFocus: true,
  })

  useEffect(() => {
    let active = true
    const controller = new AbortController()
    let since = query.data?.latest_event_at || null

    const loop = async () => {
      while (active) {
        try {
          const payload = await waitForCandidateChatThreads({
            since,
            timeout: 25,
            folder: 'all',
            limit: THREAD_LIMIT,
            signal: controller.signal,
          })
          if (!active) return
          if (payload.latest_event_at) since = payload.latest_event_at
          if (payload.updated) {
            queryClient.setQueryData<CandidateChatThreadsPayload>(threadQueryKey, payload)
          }
        } catch (error) {
          if (!active || (error as Error).name === 'AbortError') return
          await new Promise((resolve) => window.setTimeout(resolve, 1000))
        }
      }
    }

    void loop()
    return () => {
      active = false
      controller.abort()
    }
  }, [query.data?.latest_event_at, queryClient, threadQueryKey])

  return { query, threadQueryKey }
}

export function useMessengerMessages(activeCandidateId: number | null, onThreadsRefresh: () => Promise<unknown>) {
  const queryClient = useQueryClient()
  const query = useQuery<CandidateChatPayload>({
    queryKey: ['candidate-chat', activeCandidateId],
    queryFn: () => fetchCandidateChatMessages(activeCandidateId as number, MESSAGE_LIMIT),
    enabled: Boolean(activeCandidateId),
    refetchOnWindowFocus: Boolean(activeCandidateId),
  })

  useEffect(() => {
    if (!activeCandidateId) return
    let active = true
    const controller = new AbortController()
    let since = query.data?.latest_message_at || null

    const loop = async () => {
      while (active) {
        try {
          const payload = await waitForCandidateChatMessages(activeCandidateId, {
            since,
            timeout: 25,
            limit: MESSAGE_LIMIT,
            signal: controller.signal,
          })
          if (!active) return
          if (payload.latest_message_at) since = payload.latest_message_at
          if (payload.updated) {
            queryClient.setQueryData(['candidate-chat', activeCandidateId], payload)
            await onThreadsRefresh()
          }
        } catch (error) {
          if (!active || (error as Error).name === 'AbortError') return
          await new Promise((resolve) => window.setTimeout(resolve, 1000))
        }
      }
    }

    void loop()
    return () => {
      active = false
      controller.abort()
    }
  }, [activeCandidateId, onThreadsRefresh, query.data?.latest_message_at, queryClient])

  return query
}

export function useMessengerTemplates() {
  return useQuery<{ items: CandidateChatTemplate[] }>({
    queryKey: ['candidate-chat-templates'],
    queryFn: fetchCandidateChatTemplates,
  })
}

export function useMessengerMarkRead(threadQueryKey: readonly ['candidate-chat-threads', 'all']) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: markCandidateChatThreadRead,
    onSuccess: (_data, candidateId) => {
      queryClient.setQueryData<CandidateChatThreadsPayload>(threadQueryKey, (prev) => readThreadCache(prev, candidateId))
    },
  })
}

export function useMessengerSendMessage(args: {
  activeCandidateId: number | null
  onSuccess: () => Promise<unknown>
  onError: (message: string) => void
}) {
  return useMutation({
    mutationFn: async (text: string) => {
      if (!args.activeCandidateId) throw new Error('Выберите чат')
      return sendCandidateThreadMessage(args.activeCandidateId, {
        text,
        client_request_id: String(Date.now()),
      })
    },
    onSuccess: async () => {
      await args.onSuccess()
    },
    onError: (error: unknown) => {
      args.onError((error as Error).message || 'Не удалось отправить сообщение')
    },
  })
}
