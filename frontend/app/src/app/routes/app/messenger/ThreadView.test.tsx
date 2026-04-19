import { render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { CandidateChatThread, GroupedMessageRow } from './messenger.types'
import { ThreadView } from './ThreadView'

const activeThread: CandidateChatThread = {
  id: 1,
  candidate_id: 101,
  type: 'candidate',
  title: 'Иван Петров',
  city: 'Москва',
  status_label: 'Скрининг',
  profile_url: '/app/candidates/101',
  created_at: '2031-03-01T10:00:00Z',
  unread_count: 0,
}

const baseProps = {
  activeThread,
  isMobile: false,
  isLoading: false,
  isError: false,
  messagesRef: { current: null as HTMLDivElement | null },
  shouldStickToBottomRef: { current: true },
  onMessagesScroll: vi.fn(),
  onBack: vi.fn(),
  showContextPanel: false,
  onToggleContextPanel: vi.fn(),
  onCloseContextPanel: vi.fn(),
  showTemplateTray: false,
  selectedTemplateKey: '',
  templates: [],
  onToggleTemplateTray: vi.fn(),
  onApplyTemplate: vi.fn(),
  messageText: '',
  onMessageTextChange: vi.fn(),
  onSend: vi.fn(),
  sendPending: false,
  sendError: null,
}

describe('ThreadView layout behavior', () => {
  const scrollIntoViewMock = vi.fn()

  beforeEach(() => {
    scrollIntoViewMock.mockReset()
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: scrollIntoViewMock,
    })
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      callback(0)
      return 1
    })
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders bottom-aligned message container and scroll anchor', async () => {
    const groupedMessages: GroupedMessageRow[] = [
      { type: 'divider', key: 'today', label: 'Сегодня' },
      {
        type: 'message',
        unreadAnchor: false,
        message: {
          id: 501,
          direction: 'outbound',
          kind: 'recruiter',
          text: 'Добрый день',
          created_at: '2031-03-01T10:15:00Z',
          author: 'Рекрутер',
        },
      },
    ]

    render(<ThreadView {...baseProps} groupedMessages={groupedMessages} />)

    expect(screen.getByTestId('messenger-messages').querySelector('.messenger-messages-inner')).not.toBeNull()
    expect(screen.getByTestId('messenger-messages').querySelector('.messenger-messages-anchor')).not.toBeNull()
    expect(screen.getByTestId('messenger-composer')).toHaveClass('messenger-input-area')

    await waitFor(() => {
      expect(scrollIntoViewMock).toHaveBeenCalledWith({ block: 'end', behavior: 'smooth' })
    })
  })

  it('keeps unread anchor scroll behavior when unread marker exists', async () => {
    const groupedMessages: GroupedMessageRow[] = [
      { type: 'divider', key: 'today', label: 'Сегодня' },
      {
        type: 'message',
        unreadAnchor: true,
        message: {
          id: 502,
          direction: 'inbound',
          kind: 'candidate',
          text: 'Я готов поговорить',
          created_at: '2031-03-01T10:16:00Z',
          author: 'Кандидат',
        },
      },
    ]

    render(
      <ThreadView
        {...baseProps}
        groupedMessages={groupedMessages}
        shouldStickToBottomRef={{ current: false }}
      />,
    )

    await waitFor(() => {
      expect(scrollIntoViewMock).toHaveBeenCalledWith({ block: 'center', behavior: 'smooth' })
    })
  })

  it('opens candidate context panel with quiet advisory details', async () => {
    render(
      <ThreadView
        {...baseProps}
        groupedMessages={[]}
        showContextPanel
        channelHealth={{
          candidate_id: 101,
          preferred_channel: 'max',
          max_linked: true,
          telegram_linked: true,
          last_outbound_delivery: {
            status: 'dead_letter',
            delivery_stage: 'dead_letter',
            error: 'max:invalid_token',
          },
        }}
      />,
    )

    const contextPanel = screen.getByTestId('messenger-context-panel')
    expect(screen.getAllByText('MAX').length).toBeGreaterThan(0)
    expect(contextPanel).toBeInTheDocument()
    expect(within(contextPanel).getByText('Контекст кандидата')).toBeInTheDocument()
    expect(within(contextPanel).getByText('Статус: dead_letter. max:invalid_token')).toBeInTheDocument()
    expect(within(contextPanel).getByRole('link', { name: 'Открыть карточку' })).toHaveAttribute('href', '/app/candidates/101')
  })

  it('renders context toggle action in header', () => {
    render(<ThreadView {...baseProps} groupedMessages={[]} />)

    expect(screen.getByRole('button', { name: 'Контекст' })).toBeInTheDocument()
    expect(screen.queryByTestId('messenger-context-panel')).not.toBeInTheDocument()
  })
})
