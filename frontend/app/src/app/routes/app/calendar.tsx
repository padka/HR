import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../../api/client'
import { ScheduleCalendar } from '../../components/Calendar/ScheduleCalendar'
import { useCalendarWebSocket } from '../../hooks/useCalendarWebSocket'

interface ProfileData {
  ok: boolean
  user: {
    id: number
    name: string
    type: 'admin' | 'recruiter'
  }
}

interface City {
  id: number
  name: string
}

interface CitiesResponse {
  ok: boolean
  cities: City[]
}

interface SlotExtendedProps {
  slot_id: number
  status: string
  status_label: string
  recruiter_id: number | null
  recruiter_name: string
  city_name: string
  candidate_name: string | null
  local_start: string
  local_end: string
}

export function CalendarPage() {
  // Get user profile to determine role
  const { data: profile } = useQuery<ProfileData>({
    queryKey: ['profile'],
    queryFn: () => apiFetch('/profile'),
  })

  // Get cities for filter
  const { data: citiesData } = useQuery<CitiesResponse>({
    queryKey: ['cities'],
    queryFn: () => apiFetch('/cities'),
    enabled: profile?.user.type === 'admin',
  })

  const isAdmin = profile?.user.type === 'admin'

  // Filter state
  const [selectedCity, setSelectedCity] = useState<number | undefined>()
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>([])

  // Modal state for slot details
  const [selectedSlot, setSelectedSlot] = useState<SlotExtendedProps | null>(null)

  // Connect to WebSocket for real-time updates
  useCalendarWebSocket({
    enabled: true,
    onSlotChange: (event) => {
      console.log('Slot changed:', event.change_type, event.slot_id)
    },
  })

  // Handle slot click
  const handleSlotClick = useCallback((_slotId: number, slot: SlotExtendedProps) => {
    setSelectedSlot(slot)
  }, [])

  // Handle create slot
  const handleSlotCreate = useCallback((start: Date, _end: Date) => {
    // Navigate to slot creation form with pre-filled date/time
    const dateStr = start.toISOString().split('T')[0]
    const timeStr = start.toTimeString().slice(0, 5)
    window.location.href = `/app/slots/create?date=${dateStr}&time=${timeStr}`
  }, [])

  // Toggle status filter
  const toggleStatus = useCallback((status: string) => {
    setSelectedStatuses((prev) =>
      prev.includes(status) ? prev.filter((s) => s !== status) : [...prev, status]
    )
  }, [])

  const statusOptions = [
    { value: 'free', label: 'Свободные', color: '#5BE1A5' },
    { value: 'pending', label: 'Ожидающие', color: '#F6C16B' },
    { value: 'booked', label: 'Забронированные', color: '#6aa5ff' },
    { value: 'confirmed', label: 'Подтверждённые', color: '#a78bfa' },
  ]

  return (
    <div className="calendar-page">
      <div className="page-header">
        <h1>Календарь</h1>
        <a href="/app/slots/create" className="btn btn-primary">
          + Создать слот
        </a>
      </div>

      {/* Filters */}
      <div className="calendar-filters">
        {/* Status filter */}
        <div className="filter-group">
          <span className="filter-label">Статусы:</span>
          <div className="status-toggles">
            {statusOptions.map((opt) => (
              <button
                key={opt.value}
                className={`status-toggle ${selectedStatuses.includes(opt.value) ? 'active' : ''}`}
                onClick={() => toggleStatus(opt.value)}
                style={{
                  '--status-color': opt.color,
                } as React.CSSProperties}
              >
                <span className="status-dot" />
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* City filter (admin only) */}
        {isAdmin && citiesData?.cities && (
          <div className="filter-group">
            <span className="filter-label">Город:</span>
            <select
              value={selectedCity || ''}
              onChange={(e) => setSelectedCity(e.target.value ? Number(e.target.value) : undefined)}
              className="filter-select"
            >
              <option value="">Все города</option>
              {citiesData.cities.map((city) => (
                <option key={city.id} value={city.id}>
                  {city.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Calendar */}
      <ScheduleCalendar
        cityId={selectedCity}
        statuses={selectedStatuses.length > 0 ? selectedStatuses : undefined}
        onSlotClick={handleSlotClick}
        onSlotCreate={handleSlotCreate}
        editable={true}
      />

      {/* Slot detail modal */}
      {selectedSlot && (
        <div className="modal-overlay" onClick={() => setSelectedSlot(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Информация о слоте</h2>
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
                <a
                  href={`/app/slots?book=${selectedSlot.slot_id}`}
                  className="btn btn-primary"
                >
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

      <style>{`
        .calendar-page {
          padding: 24px;
          max-width: 1400px;
          margin: 0 auto;
        }

        .page-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 24px;
        }

        .page-header h1 {
          font-size: 24px;
          font-weight: 600;
          color: var(--text, #e8ecf5);
          margin: 0;
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

        .calendar-filters {
          display: flex;
          flex-wrap: wrap;
          gap: 20px;
          margin-bottom: 20px;
          padding: 16px;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 14px;
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
          background: rgba(var(--status-color-rgb, 255, 255, 255), 0.15);
          border-color: var(--status-color);
          color: var(--status-color);
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
        }

        .filter-select:focus {
          outline: none;
          border-color: rgba(106, 165, 255, 0.4);
        }

        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.7);
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
          max-width: 480px;
          box-shadow: 0 24px 56px rgba(0, 0, 0, 0.36);
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

        .modal-footer {
          display: flex;
          justify-content: flex-end;
          gap: 12px;
          padding: 16px 24px;
          border-top: 1px solid rgba(255, 255, 255, 0.08);
        }

        @media (max-width: 768px) {
          .calendar-page {
            padding: 16px;
          }

          .page-header {
            flex-direction: column;
            gap: 12px;
            align-items: flex-start;
          }

          .calendar-filters {
            flex-direction: column;
            gap: 12px;
          }

          .status-toggles {
            flex-wrap: wrap;
          }
        }
      `}</style>
    </div>
  )
}

export default CalendarPage
