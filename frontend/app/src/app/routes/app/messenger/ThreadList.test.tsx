import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { CandidateChatThread } from './messenger.types'
import { ThreadList } from './ThreadList'

const baseThread: CandidateChatThread = {
  id: 1,
  candidate_id: 101,
  type: 'candidate',
  title: 'Иван Петров',
  city: 'Москва',
  status_label: 'Лид',
  created_at: '2031-03-01T10:00:00Z',
  last_message_at: '2031-03-01T10:15:00Z',
  last_message_preview: 'Последнее сообщение',
  last_message_kind: 'candidate',
  priority_bucket: 'needs_reply',
  relevance_level: 'medium',
  unread_count: 1,
}

describe('ThreadList swipe archive', () => {
  it('archives thread from swipe action button', async () => {
    const onArchive = vi.fn()
    const onSelect = vi.fn()

    render(
      <ThreadList
        threads={[baseThread]}
        activeCandidateId={101}
        isLoading={false}
        isError={false}
        archivePendingCandidateId={null}
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
})
