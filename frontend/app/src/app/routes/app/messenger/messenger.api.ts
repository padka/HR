import { useEffect, useMemo, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  archiveCandidateChatThread,
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
import { readThreadCache, removeThreadFromCache } from './messenger.utils'

type MessengerThreadQueryKey = readonly ['candidate-chat-threads', 'inbox']

export function useMessengerThreads() {
  const queryClient = useQueryClient()
  const threadQueryKey = useMemo(() => ['candidate-chat-threads', 'inbox'] as const, [])
  const sinceRef = useRef<string | null>(null)
  const query = useQuery<CandidateChatThreadsPayload>({
    queryKey: threadQueryKey,
    queryFn: () => fetchCandidateChatThreads({ folder: 'inbox', limit: THREAD_LIMIT }),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  useEffect(() => {
    sinceRef.current = query.data?.latest_event_at || null
  }, [query.data?.latest_event_at])

  useEffect(() => {
    let active = true
    const controller = new AbortController()

    const loop = async () => {
      while (active) {
        try {
          const payload = await waitForCandidateChatThreads({
            since: sinceRef.current,
            timeout: 25,
            folder: 'inbox',
            limit: THREAD_LIMIT,
            signal: controller.signal,
          })
          if (!active) return
          if (payload.latest_event_at) sinceRef.current = payload.latest_event_at
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
  }, [queryClient, threadQueryKey])

  return { query, threadQueryKey }
}

export function useMessengerMessages(activeCandidateId: number | null, onThreadsRefresh: () => Promise<unknown>) {
  const queryClient = useQueryClient()
  const sinceRef = useRef<string | null>(null)
  const onThreadsRefreshRef = useRef(onThreadsRefresh)
  const query = useQuery<CandidateChatPayload>({
    queryKey: ['candidate-chat', activeCandidateId],
    queryFn: () => fetchCandidateChatMessages(activeCandidateId as number, MESSAGE_LIMIT),
    enabled: Boolean(activeCandidateId),
    staleTime: 15_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  useEffect(() => {
    sinceRef.current = query.data?.latest_message_at || null
  }, [query.data?.latest_message_at])

  useEffect(() => {
    onThreadsRefreshRef.current = onThreadsRefresh
  }, [onThreadsRefresh])

  useEffect(() => {
    if (!activeCandidateId) return
    let active = true
    const controller = new AbortController()

    const loop = async () => {
      while (active) {
        try {
          const payload = await waitForCandidateChatMessages(activeCandidateId, {
            since: sinceRef.current,
            timeout: 25,
            limit: MESSAGE_LIMIT,
            signal: controller.signal,
          })
          if (!active) return
          if (payload.latest_message_at) sinceRef.current = payload.latest_message_at
          if (payload.updated) {
            queryClient.setQueryData(['candidate-chat', activeCandidateId], payload)
            await onThreadsRefreshRef.current()
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
  }, [activeCandidateId, queryClient])

  return query
}

export function useMessengerTemplates() {
  return useQuery<{ items: CandidateChatTemplate[] }>({
    queryKey: ['candidate-chat-templates'],
    queryFn: fetchCandidateChatTemplates,
    staleTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
}

export function useMessengerMarkRead(threadQueryKey: MessengerThreadQueryKey) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: markCandidateChatThreadRead,
    onSuccess: (_data, candidateId) => {
      queryClient.setQueryData<CandidateChatThreadsPayload>(threadQueryKey, (prev) => readThreadCache(prev, candidateId))
    },
  })
}

export function useMessengerArchiveThread(args: {
  threadQueryKey: MessengerThreadQueryKey
  onSuccess: (candidateId: number) => void
  onError: (message: string) => void
  refetchThreads: () => Promise<unknown>
}) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: archiveCandidateChatThread,
    onMutate: async (candidateId) => {
      const previousThreads = queryClient.getQueryData<CandidateChatThreadsPayload>(args.threadQueryKey)
      queryClient.setQueryData<CandidateChatThreadsPayload>(
        args.threadQueryKey,
        (prev) => removeThreadFromCache(prev, candidateId),
      )
      return { previousThreads, candidateId }
    },
    onError: (error: unknown, _candidateId, context) => {
      if (context?.previousThreads) {
        queryClient.setQueryData(args.threadQueryKey, context.previousThreads)
      }
      args.onError((error as Error).message || 'Не удалось удалить диалог')
    },
    onSuccess: async (_data, candidateId) => {
      args.onSuccess(candidateId)
      await args.refetchThreads()
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
