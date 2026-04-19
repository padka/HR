import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import '@/theme/pages/messenger.css'

import { RoleGuard } from '@/app/components/RoleGuard'
import { useIsMobile } from '@/app/hooks/useIsMobile'
import { useCandidateChannelHealth } from '../candidate-detail/candidate-detail.api'

import {
  useMessengerArchiveThread,
  useMessengerMarkRead,
  useMessengerMessages,
  useMessengerSendMessage,
  useMessengerTemplates,
  useMessengerThreads,
} from './messenger.api'
import type { MessengerChannelFilter, MessengerQuickFilter, MessengerStageFolder } from './messenger.types'
import {
  buildFolderCounts,
  classifyThreadToFolder,
  groupedMessagesWithUnread,
  matchesChannelFilter,
  matchesQuickFilter,
  sortThreadsForInbox,
} from './messenger.utils'
import { ThreadList } from './ThreadList'
import { ThreadView } from './ThreadView'
import { useMessageDraft } from './useMessageDraft'

export function MessengerPage() {
  const isMobile = useIsMobile()
  const messagesRef = useRef<HTMLDivElement | null>(null)
  const shouldStickToBottomRef = useRef(true)

  const [activeCandidateId, setActiveCandidateId] = useState<number | null>(null)
  const [activeFolder, setActiveFolder] = useState<MessengerStageFolder>('all')
  const [quickFilter, setQuickFilter] = useState<MessengerQuickFilter>('all')
  const [channelFilter, setChannelFilter] = useState<MessengerChannelFilter>('all')
  const [showContextPanel, setShowContextPanel] = useState(false)
  const [showTemplateTray, setShowTemplateTray] = useState(false)
  const [selectedTemplateKey, setSelectedTemplateKey] = useState('')
  const [sendError, setSendError] = useState<string | null>(null)
  const { draft: messageText, setDraft: setMessageText } = useMessageDraft(activeCandidateId)

  const { query: threadsQuery, threadQueryKey } = useMessengerThreads()
  const allThreads = useMemo(
    () => sortThreadsForInbox(threadsQuery.data?.threads || []),
    [threadsQuery.data?.threads],
  )
  const channelScopedThreads = useMemo(
    () => sortThreadsForInbox(allThreads.filter((thread) => matchesChannelFilter(thread, channelFilter))),
    [allThreads, channelFilter],
  )
  const folderCounts = useMemo(
    () => buildFolderCounts(channelScopedThreads),
    [channelScopedThreads],
  )
  const folderScopedThreads = useMemo(
    () =>
      sortThreadsForInbox(
        channelScopedThreads.filter((thread) => {
          if (activeFolder === 'all') return true
          return classifyThreadToFolder(thread) === activeFolder
        }),
      ),
    [activeFolder, channelScopedThreads],
  )
  const visibleThreads = useMemo(
    () =>
      sortThreadsForInbox(
        folderScopedThreads.filter((thread) => matchesQuickFilter(thread, quickFilter)),
      ),
    [folderScopedThreads, quickFilter],
  )

  useEffect(() => {
    if (typeof document === 'undefined') return
    document.body.classList.add('messenger-route-active')
    return () => {
      document.body.classList.remove('messenger-route-active')
    }
  }, [])

  useEffect(() => {
    if (activeCandidateId || !visibleThreads.length || isMobile) return
    setActiveCandidateId(visibleThreads[0].candidate_id)
  }, [activeCandidateId, isMobile, visibleThreads])

  useEffect(() => {
    if (!activeCandidateId) return
    if (visibleThreads.some((thread) => thread.candidate_id === activeCandidateId)) return
    setActiveCandidateId(isMobile ? null : (visibleThreads[0]?.candidate_id ?? null))
  }, [activeCandidateId, isMobile, visibleThreads])

  useEffect(() => {
    setSelectedTemplateKey('')
    setShowTemplateTray(false)
    setSendError(null)
    setShowContextPanel(false)
  }, [activeCandidateId])

  const activeThread = useMemo(
    () => visibleThreads.find((thread) => thread.candidate_id === activeCandidateId) || null,
    [activeCandidateId, visibleThreads],
  )
  const channelHealthQuery = useCandidateChannelHealth(activeCandidateId || 0, Boolean(activeCandidateId))

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
            threads={visibleThreads}
            allThreads={allThreads}
            folderScopedThreads={folderScopedThreads}
            folderCounts={folderCounts}
            activeCandidateId={activeCandidateId}
            activeFolder={activeFolder}
            quickFilter={quickFilter}
            channelFilter={channelFilter}
            isLoading={threadsQuery.isLoading}
            isError={threadsQuery.isError}
            archivePendingCandidateId={archiveMutation.isPending ? (archiveMutation.variables ?? null) : null}
            onFolderChange={setActiveFolder}
            onQuickFilterChange={setQuickFilter}
            onChannelFilterChange={setChannelFilter}
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
            channelHealth={channelHealthQuery.data || null}
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
            showContextPanel={showContextPanel}
            onToggleContextPanel={() => setShowContextPanel((prev) => !prev)}
            onCloseContextPanel={() => setShowContextPanel(false)}
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
