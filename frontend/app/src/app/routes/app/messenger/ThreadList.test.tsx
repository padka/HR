import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { CandidateChatThread } from './messenger.types'
import { ThreadList } from './ThreadList'
import { buildFolderCounts, classifyThreadToFolder, matchesThreadSearch } from './messenger.utils'

const baseThread: CandidateChatThread = {
  id: 1,
  candidate_id: 101,
  type: 'candidate',
  title: 'Иван Петров',
  city: 'Москва',
  status_label: 'Лид',
  status_slug: 'lead',
  created_at: '2031-03-01T10:00:00Z',
  last_message_at: '2031-03-01T10:15:00Z',
  last_message_preview: 'Последнее сообщение',
  last_message_kind: 'candidate',
  priority_bucket: 'needs_reply',
  relevance_level: 'medium',
  unread_count: 1,
}

describe('ThreadList inbox workspace', () => {
  beforeEach(() => {
    vi.stubGlobal('confirm', vi.fn(() => true))
  })

  it('archives thread from swipe action button', async () => {
    const onArchive = vi.fn()
    const onSelect = vi.fn()
    const threads = [baseThread]

    render(
      <ThreadList
        threads={threads}
        allThreads={threads}
        folderScopedThreads={threads}
        folderCounts={buildFolderCounts(threads)}
        activeCandidateId={101}
        activeFolder="all"
        quickFilter="all"
        channelFilter="all"
        searchValue=""
        isLoading={false}
        isError={false}
        archivePendingCandidateId={null}
        onFolderChange={vi.fn()}
        onQuickFilterChange={vi.fn()}
        onChannelFilterChange={vi.fn()}
        onSearchChange={vi.fn()}
        onRefresh={vi.fn()}
        onArchive={onArchive}
        onSelect={onSelect}
      />,
    )

    expect(screen.getByTestId('messenger-thread-row-101')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Удалить диалог Иван Петров' }))

    await waitFor(() => {
      expect(onArchive).toHaveBeenCalledWith(101)
    })
    expect(onSelect).not.toHaveBeenCalled()
  })

  it('classifies threads into stage folders and renders counts', () => {
    const waitingSlotThread: CandidateChatThread = {
      ...baseThread,
      id: 2,
      candidate_id: 102,
      title: 'Мария Серова',
      status_label: 'Ждёт назначения слота',
      status_slug: 'waiting_slot',
      unread_count: 0,
      priority_bucket: 'waiting_candidate',
    }
    const interviewThread: CandidateChatThread = {
      ...baseThread,
      id: 3,
      candidate_id: 103,
      title: 'Павел Ильин',
      status_label: 'Собеседование',
      status_slug: 'interview_scheduled',
      unread_count: 2,
      priority_bucket: 'overdue',
    }
    const threads = [baseThread, waitingSlotThread, interviewThread]

    expect(classifyThreadToFolder(baseThread)).toBe('lead')
    expect(classifyThreadToFolder(waitingSlotThread)).toBe('waiting_slot')
    expect(classifyThreadToFolder(interviewThread)).toBe('interview')

    render(
      <ThreadList
        threads={threads}
        allThreads={threads}
        folderScopedThreads={threads}
        folderCounts={buildFolderCounts(threads)}
        activeCandidateId={101}
        activeFolder="all"
        quickFilter="all"
        channelFilter="all"
        searchValue=""
        isLoading={false}
        isError={false}
        archivePendingCandidateId={null}
        onFolderChange={vi.fn()}
        onQuickFilterChange={vi.fn()}
        onChannelFilterChange={vi.fn()}
        onSearchChange={vi.fn()}
        onRefresh={vi.fn()}
        onArchive={vi.fn()}
        onSelect={vi.fn()}
      />,
    )

    const folderRail = screen.getByTestId('messenger-folder-rail')
    expect(within(folderRail).getByText('Лиды')).toBeInTheDocument()
    expect(within(folderRail).getByText('Ожидают слот')).toBeInTheDocument()
    expect(within(folderRail).getByText('Собеседование')).toBeInTheDocument()
  })

  it('emits folder and quick filter changes', () => {
    const onFolderChange = vi.fn()
    const onQuickFilterChange = vi.fn()
    const onChannelFilterChange = vi.fn()
    const onSearchChange = vi.fn()
    const threads = [baseThread]

    render(
      <ThreadList
        threads={threads}
        allThreads={threads}
        folderScopedThreads={threads}
        folderCounts={buildFolderCounts(threads)}
        activeCandidateId={101}
        activeFolder="all"
        quickFilter="all"
        channelFilter="all"
        searchValue=""
        isLoading={false}
        isError={false}
        archivePendingCandidateId={null}
        onFolderChange={onFolderChange}
        onQuickFilterChange={onQuickFilterChange}
        onChannelFilterChange={onChannelFilterChange}
        onSearchChange={onSearchChange}
        onRefresh={vi.fn()}
        onArchive={vi.fn()}
        onSelect={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /папки/i }))
    fireEvent.click(within(screen.getByTestId('messenger-folder-rail')).getByRole('button', { name: /Ожидают слот/i }))
    fireEvent.click(within(screen.getByTestId('messenger-quick-filters')).getByRole('button', { name: /Нужен ответ/i }))
    fireEvent.click(screen.getByRole('button', { name: 'MAX' }))
    fireEvent.change(screen.getByRole('searchbox', { name: 'Поиск по чатам' }), {
      target: { value: 'Иван Петров' },
    })

    expect(onFolderChange).toHaveBeenCalledWith('waiting_slot')
    expect(onQuickFilterChange).toHaveBeenCalledWith('needs_reply')
    expect(onChannelFilterChange).toHaveBeenCalledWith('max')
    expect(onSearchChange).toHaveBeenCalledWith('Иван Петров')
  })

  it('matches fio tokens regardless of order', () => {
    expect(matchesThreadSearch(baseThread, 'Иван Петров')).toBe(true)
    expect(matchesThreadSearch(baseThread, 'Петров Иван')).toBe(true)
    expect(matchesThreadSearch(baseThread, 'Петров Москва')).toBe(true)
    expect(matchesThreadSearch(baseThread, 'Сидоров Иван')).toBe(false)
  })
})
