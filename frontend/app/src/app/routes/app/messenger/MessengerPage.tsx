import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import '@/theme/pages/messenger.css'

import { RoleGuard } from '@/app/components/RoleGuard'
import { useIsMobile } from '@/app/hooks/useIsMobile'

import {
  useMessengerArchiveThread,
  useMessengerMarkRead,
  useMessengerMessages,
  useMessengerSendMessage,
  useMessengerTemplates,
  useMessengerThreads,
} from './messenger.api'
import { groupedMessagesWithUnread } from './messenger.utils'
import { ThreadList } from './ThreadList'
import { ThreadView } from './ThreadView'
import { useMessageDraft } from './useMessageDraft'

export function MessengerPage() {
  const isMobile = useIsMobile()
  const messagesRef = useRef<HTMLDivElement | null>(null)
  const shouldStickToBottomRef = useRef(true)

  const [activeCandidateId, setActiveCandidateId] = useState<number | null>(null)
  const [showTemplateTray, setShowTemplateTray] = useState(false)
  const [selectedTemplateKey, setSelectedTemplateKey] = useState('')
  const [sendError, setSendError] = useState<string | null>(null)
  const { draft: messageText, setDraft: setMessageText } = useMessageDraft(activeCandidateId)

  const { query: threadsQuery, threadQueryKey } = useMessengerThreads()
  const allThreads = useMemo(
    () =>
      (threadsQuery.data?.threads || [])
        .slice()
        .sort((left, right) => {
          const leftTs = new Date(left.last_message_at || left.created_at).getTime()
          const rightTs = new Date(right.last_message_at || right.created_at).getTime()
          return rightTs - leftTs
        }),
    [threadsQuery.data?.threads],
  )

  useEffect(() => {
    if (typeof document === 'undefined') return
    document.body.classList.add('messenger-route-active')
    return () => {
      document.body.classList.remove('messenger-route-active')
    }
  }, [])

  useEffect(() => {
    if (activeCandidateId || !allThreads.length || isMobile) return
    setActiveCandidateId(allThreads[0].candidate_id)
  }, [activeCandidateId, allThreads, isMobile])

  useEffect(() => {
    if (!activeCandidateId) return
    if (allThreads.some((thread) => thread.candidate_id === activeCandidateId)) return
    setActiveCandidateId(isMobile ? null : (allThreads[0]?.candidate_id ?? null))
  }, [activeCandidateId, allThreads, isMobile])

  useEffect(() => {
    setSelectedTemplateKey('')
    setShowTemplateTray(false)
    setSendError(null)
  }, [activeCandidateId])

  const activeThread = useMemo(
    () => allThreads.find((thread) => thread.candidate_id === activeCandidateId) || null,
    [activeCandidateId, allThreads],
  )

  const refreshThreads = useCallback(() => threadsQuery.refetch(), [threadsQuery])
  const messagesQuery = useMessengerMessages(activeCandidateId, refreshThreads)
  const templatesQuery = useMessengerTemplates()
  const markReadMutation = useMessengerMarkRead(threadQueryKey)
  const archiveMutation = useMessengerArchiveThread({
    threadQueryKey,
    onSuccess: (candidateId) => {
      if (candidateId !== activeCandidateId) return
      const nextThread = allThreads.find((thread) => thread.candidate_id !== candidateId) || null
      setActiveCandidateId(isMobile ? null : nextThread?.candidate_id ?? null)
    },
    onError: (message) => setSendError(message),
    refetchThreads: () => threadsQuery.refetch(),
  })

  const chatMessages = useMemo(
    () => (messagesQuery.data?.messages || []).slice().reverse(),
    [messagesQuery.data?.messages],
  )
  const groupedMessages = useMemo(
    () => groupedMessagesWithUnread(chatMessages, activeThread?.unread_count || 0),
    [activeThread?.unread_count, chatMessages],
  )

  const markThreadReadRef = useRef(markReadMutation.mutate)

  useEffect(() => {
    markThreadReadRef.current = markReadMutation.mutate
  }, [markReadMutation.mutate])

  useEffect(() => {
    if (!activeCandidateId || !activeThread?.unread_count) return
    markThreadReadRef.current(activeCandidateId)
  }, [activeCandidateId, activeThread?.unread_count])

  useEffect(() => {
    shouldStickToBottomRef.current = true
  }, [activeCandidateId])

  const sendMutation = useMessengerSendMessage({
    activeCandidateId,
    onSuccess: async () => {
      setMessageText('')
      setSendError(null)
      shouldStickToBottomRef.current = true
      await Promise.all([messagesQuery.refetch(), threadsQuery.refetch()])
    },
    onError: (message) => setSendError(message),
  })

  const applyTemplateToDraft = (templateKey: string, templateText: string) => {
    setSelectedTemplateKey(templateKey)
    setMessageText(templateText)
  }

  return (
    <RoleGuard allow={['recruiter', 'admin']}>
      <div className={`page app-page app-page--ops messenger-page ${isMobile && activeCandidateId ? 'is-mobile-chat-open' : ''}`}>
        <div className="messenger-layout messenger-layout--workspace">
          <ThreadList
            threads={allThreads}
            activeCandidateId={activeCandidateId}
            isLoading={threadsQuery.isLoading}
            isError={threadsQuery.isError}
            archivePendingCandidateId={archiveMutation.isPending ? (archiveMutation.variables ?? null) : null}
            onRefresh={() => {
              void refreshThreads()
            }}
            onArchive={(candidateId) => {
              setSendError(null)
              archiveMutation.mutate(candidateId)
            }}
            onSelect={setActiveCandidateId}
          />

          <ThreadView
            activeThread={activeThread}
            isMobile={isMobile}
            isLoading={messagesQuery.isLoading}
            isError={messagesQuery.isError}
            groupedMessages={groupedMessages}
            messagesRef={messagesRef}
            shouldStickToBottomRef={shouldStickToBottomRef}
            onMessagesScroll={(gap) => {
              shouldStickToBottomRef.current = gap < 80
            }}
            onBack={() => setActiveCandidateId(null)}
            showTemplateTray={showTemplateTray}
            selectedTemplateKey={selectedTemplateKey}
            templates={templatesQuery.data?.items || []}
            onToggleTemplateTray={() => setShowTemplateTray((prev) => !prev)}
            onApplyTemplate={(template) => applyTemplateToDraft(template.key, template.text)}
            messageText={messageText}
            onMessageTextChange={setMessageText}
            onSend={() => {
              const payload = messageText.trim()
              if (payload) sendMutation.mutate(payload)
            }}
            sendPending={sendMutation.isPending}
            sendError={sendError}
          />
        </div>
      </div>
    </RoleGuard>
  )
}
