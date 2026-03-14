import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'

import {
  assignCandidateToSlot,
  assignCandidateToSlotSilently,
  createManualSlotBooking,
  rescheduleSlot,
  searchSlotCandidates,
  type CandidateSearchItem,
} from '@/api/services/slots'
import { ModalPortal } from '@/shared/components/ModalPortal'

import {
  getDateTimeParts,
  slotRecruiterTimeLabel,
  type SlotApiItem,
} from './slots.utils'

type CityOption = {
  id: number
  name: string
  tz?: string | null
  active?: boolean | null
}

type RecruiterOption = {
  id: number
  name: string
  active?: boolean | null
}

type BookingModalProps = {
  slot: SlotApiItem
  onClose: () => void
  onSuccess: () => void
  showToast: (msg: string) => void
}

export function BookingModal({ slot, onClose, onSuccess, showToast }: BookingModalProps) {
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateSearchItem | null>(null)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(timer)
  }, [search])

  const searchQuery = useQuery<{ items: CandidateSearchItem[] }>({
    queryKey: ['candidates-search', debouncedSearch],
    queryFn: () => searchSlotCandidates(debouncedSearch, 10),
    enabled: debouncedSearch.length >= 2,
  })

  const candidates = searchQuery.data?.items || []

  const proposeMutation = useMutation({
    mutationFn: async () => {
      if (!selectedCandidate?.id) throw new Error('У кандидата нет ID')
      return assignCandidateToSlot(selectedCandidate.id, slot.id)
    },
    onSuccess: () => {
      showToast('Предложение отправлено кандидату')
      onSuccess()
      onClose()
    },
    onError: (err: Error & { data?: { error?: string; message?: string } }) => {
      const errorCode = err?.data?.error || ''
      const mappedMessage =
        errorCode === 'slot_not_free'
          ? 'Слот уже занят'
          : errorCode === 'candidate_telegram_missing'
            ? 'У кандидата не привязан Telegram'
            : errorCode === 'candidate_has_active_assignment'
              ? 'У кандидата уже есть активное назначение'
              : errorCode === 'candidate_not_found'
                ? 'Кандидат не найден'
                : null
      showToast(mappedMessage || err?.data?.message || err.message || 'Не удалось отправить предложение')
    },
  })

  const silentMutation = useMutation({
    mutationFn: async () => {
      if (!selectedCandidate?.id) throw new Error('У кандидата нет ID')
      return assignCandidateToSlotSilently(selectedCandidate.id, slot.id)
    },
    onSuccess: () => {
      showToast('Кандидат записан вручную без бота')
      onSuccess()
      onClose()
    },
    onError: (err: Error & { data?: { error?: string; message?: string } }) => {
      showToast(err?.data?.message || err.message || 'Не удалось выполнить ручную запись')
    },
  })

  return (
    <ModalPortal>
      <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true" data-testid="slots-booking-modal">
        <div className="glass glass--elevated modal modal--md" onClick={(e) => e.stopPropagation()}>
          <div className="modal__header">
            <div>
              <h2 className="modal__title">Предложить слот</h2>
              <p className="modal__subtitle">{slotRecruiterTimeLabel(slot)}</p>
            </div>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
          </div>

          <div className="modal__body">
            <div className="form-group">
              <label className="form-group__label">Поиск кандидата (ФИО или Telegram)</label>
              <input
                type="text"
                placeholder="Введите минимум 2 символа..."
                value={search}
                onChange={(e) => { setSearch(e.target.value); setSelectedCandidate(null) }}
              />
            </div>

            {searchQuery.isLoading && <p className="text-muted">Поиск...</p>}

            {candidates.length > 0 && !selectedCandidate && (
              <div className="modal__list">
                {candidates.map((c) => (
                  <div
                    key={c.id}
                    className="glass glass--interactive list-item list-item--compact"
                    onClick={() => setSelectedCandidate(c)}
                  >
                    <div className="font-semibold">{c.fio || '—'}</div>
                    <div className="text-muted text-sm">
                      {c.city || '—'} · tg: {c.telegram_id || 'нет'} · {c.status?.label || '—'}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {search.length >= 2 && candidates.length === 0 && !searchQuery.isLoading && (
              <p className="text-muted">Кандидаты не найдены</p>
            )}

            {selectedCandidate && (
              <div className="glass glass--subtle list-item list-item--selected">
                <div className="font-semibold">{selectedCandidate.fio}</div>
                <div className="text-muted text-sm">
                  {selectedCandidate.city} · tg: {selectedCandidate.telegram_id}
                </div>
                <button
                  className="ui-btn ui-btn--ghost ui-btn--sm"
                  onClick={() => setSelectedCandidate(null)}
                >
                  Выбрать другого
                </button>
              </div>
            )}
          </div>

          <div className="modal__footer">
            <button
              className="ui-btn ui-btn--primary"
              disabled={!selectedCandidate || proposeMutation.isPending || silentMutation.isPending}
              onClick={() => proposeMutation.mutate()}
            >
              {proposeMutation.isPending ? 'Отправляем...' : 'Предложить'}
            </button>
            <button
              className="ui-btn ui-btn--secondary"
              disabled={!selectedCandidate || proposeMutation.isPending || silentMutation.isPending}
              onClick={() => silentMutation.mutate()}
            >
              {silentMutation.isPending ? 'Сохраняем…' : 'Записать вручную'}
            </button>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Отмена</button>
          </div>
        </div>
      </div>
    </ModalPortal>
  )
}

type ManualBookingModalProps = {
  slot?: SlotApiItem | null
  cities: CityOption[]
  recruiters: RecruiterOption[]
  isAdmin: boolean
  defaultRecruiterId?: number | null
  allowedCityIds?: number[]
  onClose: () => void
  onSuccess: () => void
  showToast: (msg: string) => void
}

export function ManualBookingModal({
  slot,
  cities,
  recruiters,
  isAdmin,
  defaultRecruiterId,
  allowedCityIds = [],
  onClose,
  onSuccess,
  showToast,
}: ManualBookingModalProps) {
  const slotTz = slot?.recruiter_tz || slot?.tz_name || 'Europe/Moscow'
  const baseIso = slot?.recruiter_local_time || slot?.start_utc || new Date().toISOString()
  const parts = getDateTimeParts(baseIso, slotTz)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateSearchItem | null>(null)
  const [fio, setFio] = useState(slot?.candidate_fio || '')
  const [phone, setPhone] = useState('')
  const [comment, setComment] = useState('')
  const [date, setDate] = useState(parts.date)
  const [time, setTime] = useState(parts.time)
  const [error, setError] = useState<string | null>(null)
  const [cityId, setCityId] = useState<string>('')
  const [recruiterId, setRecruiterId] = useState(defaultRecruiterId ? String(defaultRecruiterId) : '')

  const visibleCities = useMemo(() => {
    if (isAdmin) return cities.filter((city) => city.active !== false)
    return cities.filter((city) => city.active !== false && allowedCityIds.includes(city.id))
  }, [allowedCityIds, cities, isAdmin])

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search), 300)
    return () => window.clearTimeout(timer)
  }, [search])

  useEffect(() => {
    if (cityId || !slot?.city_name) return
    const match = visibleCities.find((city) => city.name === slot.city_name)
    if (match) setCityId(String(match.id))
  }, [cityId, slot?.city_name, visibleCities])

  useEffect(() => {
    if (!selectedCandidate?.city || cityId) return
    const match = visibleCities.find((city) => city.name.toLowerCase() === selectedCandidate.city?.toLowerCase())
    if (match) setCityId(String(match.id))
  }, [cityId, selectedCandidate?.city, visibleCities])

  const searchQuery = useQuery<{ items: CandidateSearchItem[] }>({
    queryKey: ['slots-manual-candidate-search', debouncedSearch],
    queryFn: () => searchSlotCandidates(debouncedSearch, 10),
    enabled: debouncedSearch.trim().length >= 2,
  })

  const mutation = useMutation({
    mutationFn: async () => {
      setError(null)
      if (!selectedCandidate && !fio.trim()) {
        throw new Error('Укажите ФИО или выберите существующего кандидата')
      }
      if (!cityId) {
        throw new Error('Выберите город')
      }
      if (!recruiterId) {
        throw new Error('Выберите рекрутера')
      }
      if (!date || !time) {
        throw new Error('Укажите дату и время')
      }
      return createManualSlotBooking({
        candidate_id: selectedCandidate?.id,
        slot_id: slot?.id,
        fio: selectedCandidate ? undefined : fio.trim(),
        phone: phone.trim() || null,
        city_id: Number(cityId),
        recruiter_id: Number(recruiterId),
        date,
        time,
        comment: comment.trim() || null,
      })
    },
    onSuccess: () => {
      showToast(slot ? 'Кандидат записан в слот вручную' : 'Ручная запись сохранена')
      onSuccess()
      onClose()
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  return (
    <ModalPortal>
      <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true" data-testid="slots-manual-booking-modal">
        <div className="glass glass--elevated modal modal--md" onClick={(event) => event.stopPropagation()}>
          <div className="modal__header">
            <div>
              <h2 className="modal__title">Ручная запись без бота</h2>
              <p className="modal__subtitle">
                {slot ? `Свободный слот #${slot.id}` : 'Создание интервью по результатам прозвона'}
              </p>
            </div>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
          </div>

          <div className="modal__body">
            <p className="text-muted text-sm">
              Кандидату не придут сообщения от бота. Запись попадёт в общий график встреч и карточку кандидата.
            </p>

            <div className="form-group">
              <label className="form-group__label">Найти существующего кандидата</label>
              <input
                type="text"
                placeholder="Поиск по ФИО или Telegram"
                value={selectedCandidate?.fio || search}
                onChange={(event) => {
                  setSelectedCandidate(null)
                  setSearch(event.target.value)
                }}
              />
            </div>

            {!selectedCandidate && searchQuery.data?.items?.length ? (
              <div className="modal__list">
                {searchQuery.data.items.map((candidate) => (
                  <button
                    key={candidate.id}
                    type="button"
                    className="glass glass--interactive list-item list-item--compact"
                    onClick={() => {
                      setSelectedCandidate(candidate)
                      setSearch(candidate.fio || '')
                      if (!fio.trim()) setFio(candidate.fio || '')
                    }}
                  >
                    <div className="font-semibold">{candidate.fio || '—'}</div>
                    <div className="text-muted text-sm">{candidate.city || '—'} · {candidate.status?.label || '—'}</div>
                  </button>
                ))}
              </div>
            ) : null}

            <div className="form-group">
              <label className="form-group__label">ФИО кандидата</label>
              <input value={selectedCandidate?.fio || fio} onChange={(event) => setFio(event.target.value)} disabled={Boolean(selectedCandidate)} />
            </div>

            <div className="form-row">
              <label className="form-group">
                <span className="form-group__label">Телефон</span>
                <input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="+7..." />
              </label>
              <label className="form-group">
                <span className="form-group__label">Город</span>
                <select value={cityId} onChange={(event) => setCityId(event.target.value)}>
                  <option value="">Выберите город</option>
                  {visibleCities.map((city) => (
                    <option key={city.id} value={String(city.id)}>
                      {city.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="form-row">
              <label className="form-group">
                <span className="form-group__label">Дата</span>
                <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
              </label>
              <label className="form-group">
                <span className="form-group__label">Время ({slotTz})</span>
                <input type="time" value={time} onChange={(event) => setTime(event.target.value)} />
              </label>
            </div>

            <label className="form-group">
              <span className="form-group__label">Рекрутер</span>
              <select value={recruiterId} onChange={(event) => setRecruiterId(event.target.value)} disabled={!isAdmin && Boolean(defaultRecruiterId)}>
                <option value="">Выберите рекрутера</option>
                {(isAdmin ? recruiters : recruiters.filter((item) => item.id === defaultRecruiterId)).map((recruiter) => (
                  <option key={recruiter.id} value={String(recruiter.id)}>
                    {recruiter.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="form-group">
              <span className="form-group__label">Комментарий</span>
              <textarea
                rows={3}
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                placeholder="Причина ручного прозвона, детали договорённости, город, пожелания"
              />
            </label>

            {error && <p className="ui-alert ui-alert--error">{error}</p>}
          </div>

          <div className="modal__footer">
            <button className="ui-btn ui-btn--primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
              {mutation.isPending ? 'Сохраняем…' : 'Сохранить ручную запись'}
            </button>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Отмена</button>
          </div>
        </div>
      </div>
    </ModalPortal>
  )
}

type RescheduleModalProps = {
  slot: SlotApiItem
  onClose: () => void
  onSuccess: () => void
  showToast: (msg: string) => void
}

export function RescheduleModal({ slot, onClose, onSuccess, showToast }: RescheduleModalProps) {
  const tzLabel = slot.recruiter_tz || slot.tz_name || 'Europe/Moscow'
  const baseIso = slot.recruiter_local_time || slot.start_utc
  const parts = getDateTimeParts(baseIso, tzLabel)
  const [date, setDate] = useState(parts.date)
  const [time, setTime] = useState(parts.time)
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)

  const rescheduleMutation = useMutation({
    mutationFn: async () => {
      setError(null)
      if (!date || !time) {
        setError('Укажите дату и время')
        throw new Error('invalid_form')
      }
      if (!reason.trim()) {
        setError('Укажите причину переноса')
        throw new Error('invalid_form')
      }
      return rescheduleSlot(slot.id, { date, time, reason })
    },
    onSuccess: () => {
      showToast('Слот перенесён')
      onSuccess()
      onClose()
    },
    onError: (err: Error) => {
      if (err.message === 'invalid_form') return
      showToast(`Ошибка: ${err.message}`)
    },
  })

  return (
    <ModalPortal>
      <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true" data-testid="slots-reschedule-modal">
        <div className="glass glass--elevated modal modal--md" onClick={(e) => e.stopPropagation()}>
          <div className="modal__header">
            <div>
              <h2 className="modal__title">Перенести слот</h2>
              <p className="modal__subtitle">
                ID {slot.id} · {slot.candidate_fio || 'Без кандидата'}
              </p>
            </div>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Закрыть</button>
          </div>

          <div className="modal__body">
            <div className="form-group">
              <label className="form-group__label">Новая дата</label>
              <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-group__label">Новое время ({tzLabel})</label>
              <input type="time" value={time} onChange={(e) => setTime(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-group__label">Причина переноса</label>
              <textarea
                rows={3}
                placeholder="Опишите причину переноса..."
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </div>
            {error && <p className="ui-alert ui-alert--error">{error}</p>}
          </div>

          <div className="modal__footer">
            <button
              className="ui-btn ui-btn--primary"
              disabled={rescheduleMutation.isPending}
              onClick={() => rescheduleMutation.mutate()}
            >
              {rescheduleMutation.isPending ? 'Отправляем…' : 'Перенести'}
            </button>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>Отмена</button>
          </div>
        </div>
      </div>
    </ModalPortal>
  )
}
