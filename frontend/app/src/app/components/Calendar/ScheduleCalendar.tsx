import { useCallback, useMemo, useRef, useState } from 'react'
import FullCalendar from '@fullcalendar/react'
import dayGridPlugin from '@fullcalendar/daygrid'
import timeGridPlugin from '@fullcalendar/timegrid'
import interactionPlugin from '@fullcalendar/interaction'
import type { EventResizeDoneArg } from '@fullcalendar/interaction'
import type { EventClickArg, EventDropArg, DateSelectArg, DatesSetArg } from '@fullcalendar/core'
import type { EventInput } from '@fullcalendar/core'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../../api/client'
import './calendar.css'

// Types for API response
export interface SlotExtendedProps {
  event_type?: 'slot'
  slot_id: number
  status: string
  status_label: string
  recruiter_id: number | null
  recruiter_name: string
  recruiter_tz: string
  city_id: number | null
  city_name: string
  city_tz: string | null
  candidate_id: number | null
  candidate_name: string | null
  candidate_tg_id: number | null
  candidate_tz: string | null
  duration_min: number
  local_start: string
  local_end: string
  local_date: string
}

export interface TaskExtendedProps {
  event_type: 'task'
  task_id: number
  task_title: string
  task_description: string
  is_done: boolean
  start_utc: string
  end_utc: string
  recruiter_id: number
  recruiter_name: string
  recruiter_tz: string
  local_start: string
  local_end: string
  local_date: string
}

type CalendarExtendedProps = SlotExtendedProps | TaskExtendedProps

interface CalendarEvent extends EventInput {
  extendedProps: CalendarExtendedProps
}

interface CalendarResource {
  id: string
  title: string
  extendedProps: {
    recruiter_id: number
    tz: string
  }
}

interface CalendarApiResponse {
  ok: boolean
  events: CalendarEvent[]
  resources: CalendarResource[]
  meta: {
    start_date: string
    end_date: string
    timezone: string
    total_events: number
    generated_at: string
  }
}

interface ScheduleCalendarProps {
  recruiterId?: number
  cityId?: number
  statuses?: string[]
  onSlotClick?: (slotId: number, slot: SlotExtendedProps) => void
  onTaskClick?: (taskId: number, task: TaskExtendedProps) => void
  onSlotCreate?: (start: Date, end: Date) => void
  onSlotMove?: (slotId: number, newStart: Date) => void
  editable?: boolean
  embedded?: boolean
  includeTasks?: boolean
}

function isTaskEvent(props: CalendarExtendedProps): props is TaskExtendedProps {
  return (props as TaskExtendedProps).event_type === 'task'
}

export function ScheduleCalendar({
  recruiterId,
  cityId,
  statuses,
  onSlotClick,
  onTaskClick,
  onSlotCreate,
  onSlotMove,
  editable = true,
  embedded = false,
  includeTasks = false,
}: ScheduleCalendarProps) {
  const calendarRef = useRef<FullCalendar>(null)
  const queryClient = useQueryClient()

  // Track current date range for query
  const [dateRange, setDateRange] = useState(() => {
    const today = new Date()
    const start = new Date(today)
    start.setDate(start.getDate() - 7)
    const end = new Date(today)
    end.setDate(end.getDate() + 30)
    return {
      start: start.toISOString().split('T')[0],
      end: end.toISOString().split('T')[0],
    }
  })

  // Build query params
  const queryParams = useMemo(() => {
    const params = new URLSearchParams({
      start: dateRange.start,
      end: dateRange.end,
    })
    if (recruiterId) params.set('recruiter_id', String(recruiterId))
    if (cityId) params.set('city_id', String(cityId))
    if (statuses?.length) {
      statuses.forEach((s) => params.append('status', s))
    }
    if (includeTasks) params.set('include_tasks', 'true')
    return params.toString()
  }, [dateRange, recruiterId, cityId, statuses, includeTasks])

  // Fetch calendar events
  const { data, isLoading, error } = useQuery<CalendarApiResponse>({
    queryKey: ['calendar-events', queryParams],
    queryFn: () => apiFetch(`/calendar/events?${queryParams}`),
    staleTime: 20_000,
    refetchOnWindowFocus: true,
  })

  // Move slot mutation
  const moveSlotMutation = useMutation({
    mutationFn: async ({ slotId, newStart }: { slotId: number; newStart: string }) => {
      return apiFetch(`/slots/${slotId}/move`, {
        method: 'POST',
        body: JSON.stringify({ new_start: newStart }),
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar-events'] })
    },
  })

  const moveTaskMutation = useMutation({
    mutationFn: async ({
      taskId,
      patch,
    }: {
      taskId: number
      patch: { start?: string; end?: string }
    }) => {
      return apiFetch(`/calendar/tasks/${taskId}`, {
        method: 'PATCH',
        body: JSON.stringify(patch),
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar-events'] })
    },
  })

  // Handle date range change
  const handleDatesSet = useCallback((arg: DatesSetArg) => {
    const start = arg.start.toISOString().split('T')[0]
    const end = arg.end.toISOString().split('T')[0]
    setDateRange({ start, end })
  }, [])

  // Handle event click
  const handleEventClick = useCallback(
    (arg: EventClickArg) => {
      const props = arg.event.extendedProps as CalendarExtendedProps
      if (isTaskEvent(props)) {
        if (onTaskClick) onTaskClick(props.task_id, props)
        return
      }
      if (onSlotClick) onSlotClick(props.slot_id, props)
    },
    [onSlotClick, onTaskClick]
  )

  // Handle date selection (create new slot)
  const handleDateSelect = useCallback(
    (arg: DateSelectArg) => {
      if (onSlotCreate) {
        onSlotCreate(arg.start, arg.end)
      }
      // Unselect after handling
      const calendarApi = calendarRef.current?.getApi()
      calendarApi?.unselect()
    },
    [onSlotCreate]
  )

  // Handle event drop (move slot)
  const handleEventDrop = useCallback(
    (arg: EventDropArg) => {
      const props = arg.event.extendedProps as CalendarExtendedProps

      if (isTaskEvent(props)) {
        const newStart = arg.event.start?.toISOString()
        const newEnd = (arg.event.end || arg.event.start)?.toISOString()
        if (!newStart || !newEnd) {
          arg.revert()
          return
        }
        moveTaskMutation.mutate(
          {
            taskId: props.task_id,
            patch: { start: newStart, end: newEnd },
          },
          {
            onError: () => arg.revert(),
          }
        )
        return
      }

      // Only allow moving FREE slots directly
      if (props.status !== 'free') {
        // Revert the change for non-free slots
        arg.revert()
        // Let parent handle confirmation
        if (onSlotMove) {
          onSlotMove(props.slot_id, arg.event.start!)
        }
        return
      }

      // Move FREE slot directly
      const newStart = arg.event.start?.toISOString()
      if (newStart) {
        moveSlotMutation.mutate(
          { slotId: props.slot_id, newStart },
          {
            onError: () => {
              arg.revert()
            },
          }
        )
      }
    },
    [moveSlotMutation, moveTaskMutation, onSlotMove]
  )

  const handleEventResize = useCallback(
    (arg: EventResizeDoneArg) => {
      const props = arg.event.extendedProps as CalendarExtendedProps
      if (!isTaskEvent(props)) {
        arg.revert()
        return
      }
      const newStart = arg.event.start?.toISOString()
      const newEnd = arg.event.end?.toISOString()
      if (!newStart || !newEnd) {
        arg.revert()
        return
      }
      moveTaskMutation.mutate(
        {
          taskId: props.task_id,
          patch: { start: newStart, end: newEnd },
        },
        {
          onError: () => arg.revert(),
        }
      )
    },
    [moveTaskMutation]
  )

  // Custom event content renderer
  const renderEventContent = useCallback((eventInfo: { event: { title: string; extendedProps: CalendarExtendedProps } }) => {
    const props = eventInfo.event.extendedProps
    if (isTaskEvent(props)) {
      return (
        <div className="fc-event-content-custom fc-event-content-custom--task">
          <div className="fc-event-title">{eventInfo.event.title}</div>
          <div className="fc-event-meta">
            <span className="fc-event-time">
              {props.local_start} - {props.local_end}
            </span>
            <span className="fc-event-city">
              {props.is_done ? 'Готово' : 'Задача'}
            </span>
          </div>
        </div>
      )
    }
    return (
      <div className="fc-event-content-custom">
        <div className="fc-event-title">{eventInfo.event.title}</div>
        <div className="fc-event-meta">
          <span className="fc-event-time">
            {props.local_start} - {props.local_end}
          </span>
          {props.city_name && <span className="fc-event-city">{props.city_name}</span>}
        </div>
      </div>
    )
  }, [])

  // Calendar events
  const events = useMemo(() => data?.events || [], [data])

  if (error) {
    return (
      <div className="calendar-error">
        <p>Ошибка загрузки календаря</p>
        <button onClick={() => queryClient.invalidateQueries({ queryKey: ['calendar-events'] })}>
          Повторить
        </button>
      </div>
    )
  }

  return (
    <div className={`schedule-calendar${embedded ? ' schedule-calendar--embedded' : ''}`}>
      {isLoading && <div className="calendar-loading">Загрузка...</div>}
      <FullCalendar
        ref={calendarRef}
        plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
        initialView="timeGridWeek"
        headerToolbar={{
          left: 'prev,next today',
          center: 'title',
          right: 'dayGridMonth,timeGridWeek,timeGridDay',
        }}
        buttonText={{
          today: 'Сегодня',
          month: 'Месяц',
          week: 'Неделя',
          day: 'День',
        }}
        locale="ru"
        firstDay={1}
        slotMinTime="08:00:00"
        slotMaxTime="20:00:00"
        slotDuration="00:30:00"
        slotLabelInterval="01:00:00"
        slotLabelFormat={{
          hour: '2-digit',
          minute: '2-digit',
          hour12: false,
        }}
        eventTimeFormat={{
          hour: '2-digit',
          minute: '2-digit',
          hour12: false,
        }}
        allDaySlot={false}
        nowIndicator={true}
        height="auto"
        contentHeight="auto"
        expandRows={true}
        stickyHeaderDates={true}
        // Events
        events={events}
        eventContent={renderEventContent}
        // Interactivity
        editable={editable}
        selectable={editable}
        selectMirror={true}
        eventStartEditable={editable}
        eventDurationEditable={editable}
        // Handlers
        datesSet={handleDatesSet}
        eventClick={handleEventClick}
        select={handleDateSelect}
        eventDrop={handleEventDrop}
        eventResize={handleEventResize}
        // Styling
        eventDisplay="block"
        dayMaxEvents={true}
      />
      {data?.meta && (
        <div className="calendar-footer">
          <span className="calendar-total">Всего событий: {data.meta.total_events}</span>
          <span className="calendar-updated">
            Обновлено: {new Date(data.meta.generated_at).toLocaleTimeString('ru-RU')}
          </span>
        </div>
      )}
    </div>
  )
}

export default ScheduleCalendar
