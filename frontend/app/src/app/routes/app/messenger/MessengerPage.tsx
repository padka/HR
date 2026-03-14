import { useEffect, useMemo, useRef, useState } from 'react'

import { ModalPortal } from '@/shared/components/ModalPortal'
import { useIsMobile } from '@/app/hooks/useIsMobile'

import {
  useMessengerAiSummary,
  useMessengerArchiveThread,
  useMessengerDetail,
  useMessengerMarkRead,
  useMessengerMessages,
  useMessengerSendMessage,
  useMessengerTemplates,
  useMessengerThreads,
  useMessengerWorkspace,
} from './messenger.api'
import { groupedMessagesWithUnread } from './messenger.utils'
import { ThreadList } from './ThreadList'
import { ThreadView } from './ThreadView'
import { ThreadDetail } from './ThreadDetail'
import { ScheduleIntroDayModal } from './ScheduleIntroDayModal'
import { useMessageDraft } from './useMessageDraft'
import type { ToastState } from './messenger.types'

export function MessengerPage() {
  const isMobile = useIsMobile()
  const toastTimeoutRef = useRef<number | null>(null)
  const messagesRef = useRef<HTMLDivElement | null>(null)
  const shouldStickToBottomRef = useRef(true)

  const [activeCandidateId, setActiveCandidateId] = useState<number | null>(null)
  const [isDetailsOpen, setIsDetailsOpen] = useState(false)
  const [isIntroDayModalOpen, setIsIntroDayModalOpen] = useState(false)
  const [showTemplateTray, setShowTemplateTray] = useState(false)
  const [selectedTemplateKey, setSelectedTemplateKey] = useState('')
  const [sendError, setSendError] = useState<string | null>(null)
  const [toast, setToast] = useState<ToastState | null>(null)
  const { draft: messageText, setDraft: setMessageText } = useMessageDraft(activeCandidateId)

  const showToast = (message: string, tone: 'success' | 'error' = 'success') => {
    setToast({ tone, message })
    if (toastTimeoutRef.current != null) {
      window.clearTimeout(toastTimeoutRef.current)
    }
    toastTimeoutRef.current = window.setTimeout(() => setToast(null), 2600)
  }

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
    if (activeCandidateId || !allThreads.length || isMobile) return
    setActiveCandidateId(allThreads[0].candidate_id)
  }, [activeCandidateId, allThreads, isMobile])

  useEffect(() => {
    if (!activeCandidateId) return
    if (allThreads.some((thread) => thread.candidate_id === activeCandidateId)) return
    setActiveCandidateId(isMobile ? null : (allThreads[0]?.candidate_id ?? null))
  }, [activeCandidateId, allThreads, isMobile])

  useEffect(() => {
    setIsDetailsOpen(false)
    setSelectedTemplateKey('')
    setShowTemplateTray(false)
    setSendError(null)
  }, [activeCandidateId])

  const activeThread = useMemo(
    () => allThreads.find((thread) => thread.candidate_id === activeCandidateId) || null,
    [activeCandidateId, allThreads],
  )

  const messagesQuery = useMessengerMessages(activeCandidateId, async () => {
    await threadsQuery.refetch()
  })
  const detailQuery = useMessengerDetail(activeCandidateId)
  const aiSummaryQuery = useMessengerAiSummary(activeCandidateId, isDetailsOpen)
  const templatesQuery = useMessengerTemplates()
  const workspaceQuery = useMessengerWorkspace(activeCandidateId)
  const markReadMutation = useMessengerMarkRead(threadQueryKey)

  const chatMessages = useMemo(
    () => (messagesQuery.data?.messages || []).slice().reverse(),
    [messagesQuery.data?.messages],
  )
  const groupedMessages = useMemo(
    () => groupedMessagesWithUnread(chatMessages, activeThread?.unread_count || 0),
    [activeThread?.unread_count, chatMessages],
  )

  useEffect(() => {
    if (!activeCandidateId || !activeThread?.unread_count) return
    markReadMutation.mutate(activeCandidateId)
  }, [activeCandidateId, activeThread?.unread_count, markReadMutation])

  useEffect(() => {
    const container = messagesRef.current
    if (!container) return
    requestAnimationFrame(() => {
      const unreadAnchor = container.querySelector('[data-unread-anchor="true"]')
      if (unreadAnchor instanceof HTMLElement && typeof unreadAnchor.scrollIntoView === 'function') {
        unreadAnchor.scrollIntoView({ block: 'center' })
        return
      }
      if (shouldStickToBottomRef.current) {
        container.scrollTop = container.scrollHeight
      }
    })
  }, [activeCandidateId, groupedMessages.length])

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

  const archiveMutation = useMessengerArchiveThread({
    activeCandidateId,
    isArchived: Boolean(activeThread?.is_archived),
    onSuccess: async (archived) => {
      showToast(archived ? 'Чат отправлен в архив' : 'Чат возвращён из архива')
      await threadsQuery.refetch()
    },
    onError: (message) => {
      showToast(message, 'error')
    },
  })

  const applyTemplateToDraft = (templateKey: string, templateText: string) => {
    setSelectedTemplateKey(templateKey)
    setMessageText(templateText)
  }

  return (
    <div className={`page app-page app-page--ops messenger-page ${isMobile && activeCandidateId ? 'is-mobile-chat-open' : ''}`}>
      <div className="messenger-layout messenger-layout--workspace">
        <ThreadList
          threads={allThreads}
          activeCandidateId={activeCandidateId}
          isLoading={threadsQuery.isLoading}
          isError={threadsQuery.isError}
          onRefresh={() => {
            void threadsQuery.refetch()
          }}
          onSelect={setActiveCandidateId}
        />

        <ThreadView
          activeThread={activeThread}
          cityLabel={detailQuery.data?.city || activeThread?.city}
          isMobile={isMobile}
          isLoading={messagesQuery.isLoading}
          isError={messagesQuery.isError}
          groupedMessages={groupedMessages}
          messagesRef={messagesRef}
          onMessagesScroll={(gap) => {
            shouldStickToBottomRef.current = gap < 80
          }}
          onBack={() => setActiveCandidateId(null)}
          onOpenDetails={() => setIsDetailsOpen(true)}
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

      {activeThread && isDetailsOpen ? (
        <ModalPortal>
          <ThreadDetail
            activeThread={activeThread}
            detail={detailQuery.data}
            aiSummary={aiSummaryQuery.data?.summary}
            workspace={workspaceQuery.data}
            onScheduleIntroDay={() => {
              setIsDetailsOpen(false)
              setIsIntroDayModalOpen(true)
            }}
            onArchiveToggle={() => archiveMutation.mutate()}
            archivePending={archiveMutation.isPending}
            onClose={() => setIsDetailsOpen(false)}
          />
        </ModalPortal>
      ) : null}

      {activeCandidateId && isIntroDayModalOpen && detailQuery.data ? (
        <ScheduleIntroDayModal
          candidateId={activeCandidateId}
          candidateFio={detailQuery.data.fio || activeThread?.title || 'Кандидат'}
          candidateCity={detailQuery.data.city || activeThread?.city}
          introDayTemplate={detailQuery.data.intro_day_template}
          introDayTemplateContext={detailQuery.data.intro_day_template_context}
          onClose={() => setIsIntroDayModalOpen(false)}
          onSuccess={() => {
            setIsIntroDayModalOpen(false)
            showToast('Ознакомительный день назначен')
            void Promise.all([detailQuery.refetch(), messagesQuery.refetch(), threadsQuery.refetch()])
          }}
        />
      ) : null}

      {toast ? (
        <div className="toast" data-tone={toast.tone}>
          {toast.message}
        </div>
      ) : null}
    </div>
  )
}
