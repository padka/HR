import { useCallback, useEffect, useState, type CSSProperties } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '../../../api/client'
import { RoleGuard } from '@/app/components/RoleGuard'
import {
  ScheduleCalendar,
  type SlotExtendedProps,
  type TaskExtendedProps,
} from '../../components/Calendar/ScheduleCalendar'
import { useCalendarWebSocket } from '../../hooks/useCalendarWebSocket'
import { useIsMobile } from '../../hooks/useIsMobile'
import { useProfile } from '../../hooks/useProfile'

type City = {
  id: number
  name: string
}

type RecruiterOption = {
  id: number
  name: string
}

type TaskModalState =
  | { mode: 'create' }
  | { mode: 'edit'; taskId: number }

type TaskDraft = {
  title: string
  description: string
  start: string
  end: string
  recruiter_id?: number
  is_done: boolean
}

type TaskPayload = {
  title: string
  description?: string | null
  start: string
  end: string
  recruiter_id?: number
  is_done: boolean
}

function toLocalInputValue(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function isoToLocalInput(value?: string | null): string {
  if (!value) return ''
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return ''
  return toLocalInputValue(parsed)
}

function localInputToIso(value: string): string | null {
  if (!value) return null
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return parsed.toISOString()
}

function buildTaskDraft(start: Date, end: Date, recruiterId?: number): TaskDraft {
  return {
    title: '',
    description: '',
    start: toLocalInputValue(start),
    end: toLocalInputValue(end),
    recruiter_id: recruiterId,
    is_done: false,
  }
}

export function CalendarPage() {
  const profile = useProfile()
  const isMobile = useIsMobile()
  const queryClient = useQueryClient()

  const isAdmin = profile.data?.principal.type === 'admin'
  const recruiterSelfId = profile.data?.recruiter?.id

  const { data: cities = [] } = useQuery<City[]>({
    queryKey: ['calendar-cities'],
    queryFn: () => apiFetch('/cities'),
    enabled: Boolean(isAdmin),
  })

  const { data: recruiters = [] } = useQuery<RecruiterOption[]>({
    queryKey: ['calendar-recruiters'],
    queryFn: () => apiFetch('/recruiters'),
    enabled: Boolean(isAdmin),
    staleTime: 60_000,
  })

  const [selectedCity, setSelectedCity] = useState<number | undefined>()
  const [selectedRecruiter, setSelectedRecruiter] = useState<number | undefined>()
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>([])
  const [mobileViewMode, setMobileViewMode] = useState<'timeGridDay' | 'timeGridThreeDay'>('timeGridDay')

  const [selectedSlot, setSelectedSlot] = useState<SlotExtendedProps | null>(null)

  const [taskModal, setTaskModal] = useState<TaskModalState | null>(null)
  const [taskDraft, setTaskDraft] = useState<TaskDraft | null>(null)
  const [taskError, setTaskError] = useState<string | null>(null)

  useEffect(() => {
    if (!isAdmin) return
    if (selectedRecruiter) return
    if (recruiters.length === 1) {
      setSelectedRecruiter(recruiters[0].id)
    }
  }, [isAdmin, recruiters, selectedRecruiter])

  useCalendarWebSocket({
    enabled: true,
    onSlotChange: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar-events'] })
    },
  })

  const openCreateTaskModal = useCallback(
    (start: Date, end: Date) => {
      const recruiterId = isAdmin ? selectedRecruiter : recruiterSelfId
      if (!recruiterId) {
        setTaskError('Выберите рекрутера, чтобы создать задачу.')
        return
      }
      setTaskError(null)
      setTaskDraft(buildTaskDraft(start, end, recruiterId))
      setTaskModal({ mode: 'create' })
    },
    [isAdmin, recruiterSelfId, selectedRecruiter]
  )

  const handleTaskClick = useCallback((taskId: number, task: TaskExtendedProps) => {
    setTaskError(null)
    setTaskDraft({
      title: task.task_title,
      description: task.task_description || '',
      start: isoToLocalInput(task.start_utc),
      end: isoToLocalInput(task.end_utc),
      recruiter_id: task.recruiter_id,
      is_done: Boolean(task.is_done),
    })
    setTaskModal({ mode: 'edit', taskId })
  }, [])

  const createTaskMutation = useMutation({
    mutationFn: (payload: TaskPayload) =>
      apiFetch('/calendar/tasks', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      setTaskModal(null)
      setTaskDraft(null)
      setTaskError(null)
      queryClient.invalidateQueries({ queryKey: ['calendar-events'] })
    },
    onError: (err: unknown) => {
      setTaskError((err as Error).message)
    },
  })

  const updateTaskMutation = useMutation({
    mutationFn: ({ taskId, payload }: { taskId: number; payload: Partial<TaskPayload> }) =>
      apiFetch(`/calendar/tasks/${taskId}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      setTaskModal(null)
      setTaskDraft(null)
      setTaskError(null)
      queryClient.invalidateQueries({ queryKey: ['calendar-events'] })
    },
    onError: (err: unknown) => {
      setTaskError((err as Error).message)
    },
  })

  const deleteTaskMutation = useMutation({
    mutationFn: (taskId: number) =>
      apiFetch(`/calendar/tasks/${taskId}`, {
        method: 'DELETE',
      }),
    onSuccess: () => {
      setTaskModal(null)
      setTaskDraft(null)
      setTaskError(null)
      queryClient.invalidateQueries({ queryKey: ['calendar-events'] })
    },
    onError: (err: unknown) => {
      setTaskError((err as Error).message)
    },
  })

  const handleSlotClick = useCallback((_slotId: number, slot: SlotExtendedProps) => {
    setSelectedSlot(slot)
  }, [])

  const handleSlotCreate = useCallback(
    (start: Date, end: Date) => {
      openCreateTaskModal(start, end)
    },
    [openCreateTaskModal]
  )

  const toggleStatus = useCallback((status: string) => {
    setSelectedStatuses((prev) =>
      prev.includes(status) ? prev.filter((s) => s !== status) : [...prev, status]
    )
  }, [])

  const handleTaskSubmit = useCallback(() => {
    if (!taskDraft || !taskModal) return

    const title = taskDraft.title.trim()
    if (!title) {
      setTaskError('Укажите название задачи.')
      return
    }

    const startIso = localInputToIso(taskDraft.start)
    const endIso = localInputToIso(taskDraft.end)
    if (!startIso || !endIso) {
      setTaskError('Укажите корректные дату и время задачи.')
      return
    }

    if (new Date(endIso).getTime() <= new Date(startIso).getTime()) {
      setTaskError('Время окончания должно быть позже времени начала.')
      return
    }

    if (isAdmin && !taskDraft.recruiter_id) {
      setTaskError('Выберите рекрутера.')
      return
    }

    const payload: TaskPayload = {
      title,
      description: taskDraft.description.trim() || null,
      start: startIso,
      end: endIso,
      recruiter_id: isAdmin ? taskDraft.recruiter_id : undefined,
      is_done: taskDraft.is_done,
    }

    if (taskModal.mode === 'create') {
      createTaskMutation.mutate(payload)
      return
    }

    updateTaskMutation.mutate({ taskId: taskModal.taskId, payload })
  }, [
    createTaskMutation,
    isAdmin,
    taskDraft,
    taskModal,
    updateTaskMutation,
  ])

  const handleTaskDelete = useCallback(() => {
    if (!taskModal || taskModal.mode !== 'edit') return
    deleteTaskMutation.mutate(taskModal.taskId)
  }, [deleteTaskMutation, taskModal])

  const statusOptions = [
    { value: 'free', label: 'Свободные', color: '#5BE1A5' },
    { value: 'pending', label: 'Ожидают ответ', color: '#F6C16B' },
    { value: 'booked', label: 'Записаны', color: '#6aa5ff' },
    { value: 'confirmed_by_candidate', label: 'Предв. подтверждены', color: '#8b5cf6' },
    { value: 'confirmed', label: 'Подтверждены', color: '#a78bfa' },
  ] as const

  const activeRecruiterId = isAdmin ? selectedRecruiter : recruiterSelfId
  const taskBusy = createTaskMutation.isPending || updateTaskMutation.isPending || deleteTaskMutation.isPending

  return (
    <RoleGuard allow={['recruiter', 'admin']}>
      <div className="calendar-page">
      <div className="page-header">
        <div>
          <h1>Календарь</h1>
          <p className="subtitle">Слоты кандидатов и ваши задачи в одном графике.</p>
        </div>
        <div className="header-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              const now = new Date()
              const end = new Date(now.getTime() + 30 * 60 * 1000)
              openCreateTaskModal(now, end)
            }}
          >
            + Добавить задачу
          </button>
          <a href="/app/slots/create" className="btn btn-primary">
            + Создать слот
          </a>
        </div>
      </div>

      <div className="calendar-filters">
        <div className="filter-group">
          <span className="filter-label">Статусы:</span>
          <div className="status-toggles">
            {statusOptions.map((opt) => (
              <button
                key={opt.value}
                className={`status-toggle ${selectedStatuses.includes(opt.value) ? 'active' : ''}`}
                onClick={() => toggleStatus(opt.value)}
                style={{ '--status-color': opt.color } as CSSProperties}
              >
                <span className="status-dot" />
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {isAdmin && recruiters.length > 0 && (
          <div className="filter-group">
            <span className="filter-label">Рекрутер:</span>
            <select
              value={selectedRecruiter || ''}
              onChange={(e) => setSelectedRecruiter(e.target.value ? Number(e.target.value) : undefined)}
              className="filter-select"
            >
              <option value="">Все рекрутеры</option>
              {recruiters.map((rec) => (
                <option key={rec.id} value={rec.id}>
                  {rec.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {isAdmin && cities.length > 0 && (
          <div className="filter-group">
            <span className="filter-label">Город:</span>
            <select
              value={selectedCity || ''}
              onChange={(e) => setSelectedCity(e.target.value ? Number(e.target.value) : undefined)}
              className="filter-select"
            >
              <option value="">Все города</option>
              {cities.map((city) => (
                <option key={city.id} value={city.id}>
                  {city.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {isMobile && (
        <div className="calendar-mobile-view-switch" role="group" aria-label="Режим календаря">
          <button
            type="button"
            className={`ui-btn ui-btn--sm ${mobileViewMode === 'timeGridDay' ? 'ui-btn--primary' : 'ui-btn--ghost'}`}
            onClick={() => setMobileViewMode('timeGridDay')}
          >
            День
          </button>
          <button
            type="button"
            className={`ui-btn ui-btn--sm ${mobileViewMode === 'timeGridThreeDay' ? 'ui-btn--primary' : 'ui-btn--ghost'}`}
            onClick={() => setMobileViewMode('timeGridThreeDay')}
          >
            3 дня
          </button>
        </div>
      )}

      {(taskError && !taskModal) && <div className="calendar-alert">{taskError}</div>}

      <ScheduleCalendar
        recruiterId={activeRecruiterId}
        cityId={selectedCity}
        statuses={selectedStatuses.length > 0 ? selectedStatuses : undefined}
        onSlotClick={handleSlotClick}
        onTaskClick={handleTaskClick}
        onSlotCreate={handleSlotCreate}
        includeTasks={true}
        editable={true}
        isMobile={isMobile}
        viewMode={isMobile ? mobileViewMode : undefined}
      />

      {selectedSlot && (
        <div className="modal-overlay" onClick={() => setSelectedSlot(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Собеседование</h2>
              <button className="modal-close" onClick={() => setSelectedSlot(null)}>
                &times;
              </button>
            </div>
            <div className="modal-body">
              <div className="slot-info">
                <div className="info-row">
                  <span className="info-label">Статус:</span>
                  <span className={`status-badge status-${selectedSlot.status}`}>
                    {selectedSlot.status_label}
                  </span>
                </div>
                <div className="info-row">
                  <span className="info-label">Время:</span>
                  <span>{selectedSlot.local_start} - {selectedSlot.local_end}</span>
                </div>
                {selectedSlot.recruiter_name && (
                  <div className="info-row">
                    <span className="info-label">Рекрутер:</span>
                    <span>{selectedSlot.recruiter_name}</span>
                  </div>
                )}
                {selectedSlot.city_name && (
                  <div className="info-row">
                    <span className="info-label">Город:</span>
                    <span>{selectedSlot.city_name}</span>
                  </div>
                )}
                {selectedSlot.candidate_name && (
                  <div className="info-row">
                    <span className="info-label">Кандидат:</span>
                    <span>{selectedSlot.candidate_name}</span>
                  </div>
                )}
              </div>
            </div>
            <div className="modal-footer">
              {selectedSlot.status === 'free' && (
                <a href={`/app/slots?book=${selectedSlot.slot_id}`} className="btn btn-primary">
                  Назначить кандидата
                </a>
              )}
              <button className="btn btn-secondary" onClick={() => setSelectedSlot(null)}>
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}

      {taskModal && taskDraft && (
        <div className="modal-overlay" onClick={() => !taskBusy && setTaskModal(null)}>
          <div className="modal-content modal-content--task" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{taskModal.mode === 'create' ? 'Новая задача' : 'Задача'}</h2>
              <button className="modal-close" onClick={() => setTaskModal(null)} disabled={taskBusy}>
                &times;
              </button>
            </div>
            <div className="modal-body">
              <div className="task-form">
                <label className="task-field">
                  <span>Название</span>
                  <input
                    type="text"
                    value={taskDraft.title}
                    onChange={(e) => setTaskDraft((prev) => (prev ? { ...prev, title: e.target.value } : prev))}
                    maxLength={180}
                    placeholder="Например: Подготовить вопросы к собеседованию"
                  />
                </label>

                <label className="task-field">
                  <span>Описание</span>
                  <textarea
                    value={taskDraft.description}
                    onChange={(e) => setTaskDraft((prev) => (prev ? { ...prev, description: e.target.value } : prev))}
                    rows={3}
                    placeholder="Детали задачи"
                  />
                </label>

                <div className="task-grid">
                  <label className="task-field">
                    <span>Начало</span>
                    <input
                      type="datetime-local"
                      value={taskDraft.start}
                      onChange={(e) => setTaskDraft((prev) => (prev ? { ...prev, start: e.target.value } : prev))}
                    />
                  </label>
                  <label className="task-field">
                    <span>Окончание</span>
                    <input
                      type="datetime-local"
                      value={taskDraft.end}
                      onChange={(e) => setTaskDraft((prev) => (prev ? { ...prev, end: e.target.value } : prev))}
                    />
                  </label>
                </div>

                {isAdmin && (
                  <label className="task-field">
                    <span>Рекрутер</span>
                    <select
                      value={taskDraft.recruiter_id || ''}
                      onChange={(e) =>
                        setTaskDraft((prev) =>
                          prev
                            ? {
                                ...prev,
                                recruiter_id: e.target.value ? Number(e.target.value) : undefined,
                              }
                            : prev
                        )
                      }
                    >
                      <option value="">Выберите рекрутера</option>
                      {recruiters.map((rec) => (
                        <option key={rec.id} value={rec.id}>
                          {rec.name}
                        </option>
                      ))}
                    </select>
                  </label>
                )}

                <label className="task-check">
                  <input
                    type="checkbox"
                    checked={taskDraft.is_done}
                    onChange={(e) =>
                      setTaskDraft((prev) =>
                        prev
                          ? {
                              ...prev,
                              is_done: e.target.checked,
                            }
                          : prev
                      )
                    }
                  />
                  <span>Отметить как выполненную</span>
                </label>

                {taskError && <p className="task-error">{taskError}</p>}
              </div>
            </div>
            <div className="modal-footer modal-footer--task">
              {taskModal.mode === 'edit' && (
                <button className="btn btn-danger" onClick={handleTaskDelete} disabled={taskBusy}>
                  Удалить
                </button>
              )}
              <button className="btn btn-secondary" onClick={() => setTaskModal(null)} disabled={taskBusy}>
                Отмена
              </button>
              <button className="btn btn-primary" onClick={handleTaskSubmit} disabled={taskBusy}>
                {taskBusy ? 'Сохраняем…' : 'Сохранить'}
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .calendar-page {
          padding: 24px;
          max-width: 1400px;
          margin: 0 auto;
        }

        .page-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 24px;
          gap: 12px;
        }

        .page-header h1 {
          font-size: 24px;
          font-weight: 600;
          color: var(--text, #e8ecf5);
          margin: 0;
        }

        .subtitle {
          margin: 6px 0 0;
          color: rgba(232, 236, 245, 0.62);
          font-size: 13px;
        }

        .header-actions {
          display: flex;
          gap: 10px;
          flex-wrap: wrap;
          justify-content: flex-end;
        }

        .btn {
          padding: 10px 18px;
          border-radius: 10px;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
          text-decoration: none;
          display: inline-flex;
          align-items: center;
          gap: 6px;
        }

        .btn-primary {
          background: rgba(106, 165, 255, 0.22);
          border: 1px solid rgba(106, 165, 255, 0.4);
          color: #6aa5ff;
        }

        .btn-primary:hover {
          background: rgba(106, 165, 255, 0.32);
          transform: translateY(-1px);
        }

        .btn-secondary {
          background: rgba(255, 255, 255, 0.08);
          border: 1px solid rgba(255, 255, 255, 0.18);
          color: #e8ecf5;
        }

        .btn-secondary:hover {
          background: rgba(255, 255, 255, 0.14);
        }

        .btn-danger {
          background: rgba(240, 115, 115, 0.16);
          border: 1px solid rgba(240, 115, 115, 0.38);
          color: #f07373;
        }

        .btn-danger:hover {
          background: rgba(240, 115, 115, 0.24);
        }

        .calendar-filters {
          display: flex;
          flex-wrap: wrap;
          gap: 14px 20px;
          margin-bottom: 20px;
          padding: 16px;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 14px;
        }

        .calendar-mobile-view-switch {
          display: inline-flex;
          gap: 8px;
          margin-bottom: 12px;
        }

        .filter-group {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .filter-label {
          font-size: 13px;
          color: rgba(232, 236, 245, 0.72);
          font-weight: 500;
        }

        .status-toggles {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }

        .status-toggle {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 6px 12px;
          background: rgba(255, 255, 255, 0.06);
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 8px;
          color: rgba(232, 236, 245, 0.72);
          font-size: 12px;
          cursor: pointer;
          transition: all 0.18s ease;
        }

        .status-toggle:hover {
          background: rgba(255, 255, 255, 0.1);
          border-color: rgba(255, 255, 255, 0.2);
        }

        .status-toggle.active {
          border-color: var(--status-color);
          color: var(--status-color);
          box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--status-color) 45%, transparent);
        }

        .status-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: var(--status-color);
        }

        .filter-select {
          padding: 8px 12px;
          background: rgba(255, 255, 255, 0.06);
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 8px;
          color: #e8ecf5;
          font-size: 13px;
          cursor: pointer;
          min-width: 220px;
        }

        .filter-select:focus {
          outline: none;
          border-color: rgba(106, 165, 255, 0.4);
        }

        .calendar-alert {
          margin-bottom: 12px;
          padding: 10px 12px;
          border-radius: 10px;
          border: 1px solid rgba(240, 115, 115, 0.35);
          background: rgba(240, 115, 115, 0.12);
          color: #ffb0b0;
          font-size: 13px;
        }

        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.72);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          backdrop-filter: blur(4px);
        }

        .modal-content {
          background: #101828;
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 18px;
          width: 90%;
          max-width: 520px;
          box-shadow: 0 24px 56px rgba(0, 0, 0, 0.36);
        }

        .modal-content--task {
          max-width: 640px;
        }

        .modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 20px 24px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }

        .modal-header h2 {
          margin: 0;
          font-size: 18px;
          font-weight: 600;
          color: #e8ecf5;
        }

        .modal-close {
          background: none;
          border: none;
          font-size: 24px;
          color: rgba(232, 236, 245, 0.55);
          cursor: pointer;
          padding: 0;
          line-height: 1;
        }

        .modal-close:hover {
          color: #e8ecf5;
        }

        .modal-body {
          padding: 24px;
        }

        .slot-info {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .info-row {
          display: flex;
          gap: 12px;
        }

        .info-label {
          min-width: 100px;
          color: rgba(232, 236, 245, 0.55);
          font-size: 13px;
        }

        .status-badge {
          padding: 4px 10px;
          border-radius: 6px;
          font-size: 12px;
          font-weight: 500;
        }

        .status-free {
          background: rgba(91, 225, 165, 0.18);
          color: #5BE1A5;
        }

        .status-pending {
          background: rgba(246, 193, 107, 0.18);
          color: #F6C16B;
        }

        .status-booked {
          background: rgba(106, 165, 255, 0.18);
          color: #6aa5ff;
        }

        .status-confirmed {
          background: rgba(167, 139, 250, 0.18);
          color: #a78bfa;
        }

        .status-confirmed_by_candidate {
          background: rgba(139, 92, 246, 0.2);
          color: #bf9aff;
        }

        .modal-footer {
          display: flex;
          justify-content: flex-end;
          gap: 12px;
          padding: 16px 24px;
          border-top: 1px solid rgba(255, 255, 255, 0.08);
        }

        .modal-footer--task {
          justify-content: space-between;
        }

        .task-form {
          display: grid;
          gap: 12px;
        }

        .task-field {
          display: grid;
          gap: 6px;
        }

        .task-field span {
          font-size: 12px;
          color: rgba(232, 236, 245, 0.72);
        }

        .task-field input,
        .task-field textarea,
        .task-field select {
          width: 100%;
          border-radius: 10px;
          border: 1px solid rgba(255, 255, 255, 0.14);
          background: rgba(16, 24, 40, 0.6);
          color: #e8ecf5;
          font-size: 13px;
          padding: 10px 12px;
        }

        .task-field textarea {
          resize: vertical;
          min-height: 84px;
        }

        .task-grid {
          display: grid;
          gap: 12px;
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .task-check {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          font-size: 13px;
          color: rgba(232, 236, 245, 0.85);
        }

        .task-error {
          margin: 0;
          color: #f7a3a3;
          font-size: 12px;
        }

        @media (max-width: 860px) {
          .calendar-page {
            padding: 16px;
          }

          .page-header {
            flex-direction: column;
            align-items: flex-start;
          }

          .header-actions {
            width: 100%;
            justify-content: stretch;
          }

          .header-actions .btn {
            flex: 1;
            justify-content: center;
          }

          .calendar-filters {
            flex-direction: column;
          }

          .calendar-mobile-view-switch {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }

          .calendar-mobile-view-switch .ui-btn {
            width: 100%;
          }

          .task-grid {
            grid-template-columns: minmax(0, 1fr);
          }

          .modal-content {
            width: 94%;
          }

          .modal-footer--task {
            flex-wrap: wrap;
            justify-content: flex-end;
          }
        }
      `}</style>
      </div>
    </RoleGuard>
  )
}

export default CalendarPage
