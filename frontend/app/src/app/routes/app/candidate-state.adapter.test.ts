import { describe, expect, it } from 'vitest'

import {
  buildCandidateSurfaceState,
  compareIncomingCandidates,
  describeKanbanColumnTreatment,
  matchesIncomingStatusFilter,
  summarizeIncomingCandidates,
} from './candidate-state.adapter'

describe('candidate-state.adapter', () => {
  it('prefers backend lifecycle and next action over legacy incoming labels', () => {
    const state = buildCandidateSurfaceState({
      status_slug: 'waiting_slot',
      status_display: 'Ожидает слот',
      waiting_hours: 30,
      lifecycle_summary: {
        stage: 'waiting_interview_slot' as const,
        stage_label: 'Ожидает слот на интервью',
        record_state: 'active' as const,
      },
      candidate_next_action: {
        worklist_bucket: 'incoming',
        urgency: 'attention',
        primary_action: {
          type: 'offer_interview_slot',
          label: 'Предложить время',
          enabled: true,
        },
      },
      state_reconciliation: {
        issues: [{ code: 'workflow_status_drift', message: 'workflow_status расходится.' }],
        has_blockers: true,
      },
    })

    expect(state.statusLabel).toBe('Ожидает слот на интервью')
    expect(state.nextActionLabel).toBe('Предложить время')
    expect(state.nextActionExplanation).toBeNull()
    expect(state.stalled).toBe(true)
    expect(state.hasReconciliationIssues).toBe(true)
    expect(state.riskLevel).toBe('warning')
    expect(state.triageLane).toBe('review')
  })

  it('maps contract-driven interview confirmation to kanban column even when legacy status lags behind', () => {
    const state = buildCandidateSurfaceState({
      status: { slug: 'waiting_slot', label: 'Ожидает слот', tone: 'warning' },
      lifecycle_summary: {
        stage: 'interview' as const,
        stage_label: 'Интервью',
        record_state: 'active' as const,
      },
      scheduling_summary: {
        status: 'confirmed' as const,
        status_label: 'Участие подтверждено',
        active: true,
      },
    })

    expect(state.kanbanColumnSlug).toBe('interview_confirmed')
    expect(state.statusLabel).toBe('Интервью')
    expect(state.schedulingLabel).toBe('Участие подтверждено')
  })

  it('prefers backend operational summary when queue and kanban semantics are available', () => {
    const state = buildCandidateSurfaceState({
      status: { slug: 'waiting_slot', label: 'Ждет слот', tone: 'warning' },
      lifecycle_summary: {
        stage: 'waiting_interview_slot' as const,
        stage_label: 'Ожидает слот на интервью',
        record_state: 'active' as const,
      },
      operational_summary: {
        kanban_column: 'slot_pending',
        queue_state: 'awaiting_candidate_confirmation',
        queue_state_label: 'Ожидает подтверждения кандидата',
        pending_approval: true,
        stalled: false,
        requested_reschedule: false,
        worklist_bucket: 'awaiting_recruiter',
        worklist_bucket_label: 'Ждет рекрутера',
      },
    })

    expect(state.kanbanColumnSlug).toBe('slot_pending')
    expect(state.pendingApproval).toBe(true)
    expect(state.worklistBucket).toBe('awaiting_recruiter')
    expect(state.queueState).toBe('awaiting_candidate_confirmation')
    expect(state.triageLane).toBe('action_now')
  })

  it('uses contract-driven queue signals for filtering, sorting, and stats', () => {
    const requested = {
      id: 1,
      name: 'Запрос переноса',
      waiting_hours: 2,
      lifecycle_summary: {
        stage: 'interview' as const,
        stage_label: 'Интервью',
        record_state: 'active' as const,
      },
      scheduling_summary: {
        status: 'reschedule_requested' as const,
        status_label: 'Запрошен перенос',
        requested_reschedule: true,
        active: true,
      },
      candidate_next_action: {
        urgency: 'attention',
        primary_action: { type: 'resolve_reschedule', label: 'Обработать перенос', enabled: true },
      },
    }
    const pending = {
      id: 2,
      name: 'Ждет рекрутера',
      waiting_hours: 4,
      lifecycle_summary: {
        stage: 'interview' as const,
        stage_label: 'Интервью',
        record_state: 'active' as const,
      },
      scheduling_summary: {
        status: 'selected' as const,
        status_label: 'Слот выбран',
        active: true,
      },
      candidate_next_action: {
        urgency: 'attention',
        primary_action: { type: 'approve_selected_slot', label: 'Подтвердить слот', enabled: true },
      },
    }

    expect(matchesIncomingStatusFilter(requested, 'requested_other_time')).toBe(true)
    expect(matchesIncomingStatusFilter(pending, 'waiting_slot')).toBe(false)
    expect(compareIncomingCandidates(requested, pending, 'waiting')).toBeLessThan(0)

    const summary = summarizeIncomingCandidates([requested, pending])
    expect(summary.requested).toBe(1)
    expect(summary.pending).toBe(1)
  })

  it('maps blocking_state into repair risk copy for recruiter surfaces', () => {
    const state = buildCandidateSurfaceState({
      lifecycle_summary: {
        stage: 'interview' as const,
        stage_label: 'Интервью',
        record_state: 'active' as const,
      },
      candidate_next_action: {
        urgency: 'attention',
        primary_action: { type: 'offer_interview_slot', label: 'Предложить время', enabled: true },
      },
      blocking_state: {
        code: 'scheduling_conflict',
        category: 'scheduling',
        severity: 'warning',
        retryable: false,
        recoverable: true,
        manual_resolution_required: true,
        issue_codes: ['scheduling_split_brain'],
      },
      state_reconciliation: {
        issues: [{ code: 'scheduling_split_brain', message: 'Слот и назначение расходятся.' }],
        has_blockers: true,
      },
    })

    expect(state.riskLevel).toBe('repair')
    expect(state.riskTitle).toBe('Нужен ручной разбор расписания')
    expect(state.riskRecoveryHint).toMatch(/карточку кандидата/i)
    expect(state.riskIssueCodes).toEqual(['scheduling_split_brain'])
    expect(state.triageLane).toBe('review')
  })

  it('distinguishes interactive and guided kanban columns without inventing new backend states', () => {
    expect(describeKanbanColumnTreatment({ slug: 'test2_completed', droppable: true })).toEqual({
      mode: 'interactive',
      helperText: 'Ручное перемещение доступно только для безопасных переходов.',
    })

    expect(describeKanbanColumnTreatment({ slug: 'incoming', droppable: false })).toEqual({
      mode: 'guided',
      helperText: 'Колонка меняется через действие рекрутера или scheduling flow, а не прямым drag-and-drop.',
    })
  })
})
