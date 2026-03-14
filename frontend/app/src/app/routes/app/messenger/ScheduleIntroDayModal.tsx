import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'

import { fetchCities, scheduleCandidateIntroDay } from '@/api/services/candidates'
import { browserTimeZone, buildSlotTimePreview } from '@/app/lib/timezonePreview'
import { ModalPortal } from '@/shared/components/ModalPortal'

import {
  buildIntroDayFallback,
  getTomorrowDate,
  renderIntroDayTemplate,
} from './messenger.utils'
import type { CityOption, IntroDayTemplateContext } from './messenger.types'

type ScheduleIntroDayModalProps = {
  candidateId: number
  candidateFio: string
  candidateCity?: string | null
  introDayTemplate?: string | null
  introDayTemplateContext?: IntroDayTemplateContext | null
  onClose: () => void
  onSuccess: () => void
}

export function ScheduleIntroDayModal({
  candidateId,
  candidateFio,
  candidateCity,
  introDayTemplate,
  introDayTemplateContext,
  onClose,
  onSuccess,
}: ScheduleIntroDayModalProps) {
  const [form, setForm] = useState({
    date: getTomorrowDate(),
    time: '10:00',
    customMessage: '',
  })
  const [template, setTemplate] = useState('')
  const [error, setError] = useState<string | null>(null)
  const recruiterTz = browserTimeZone()

  const citiesQuery = useQuery<CityOption[]>({
    queryKey: ['cities'],
    queryFn: fetchCities,
  })

  const candidateTz = useMemo(() => {
    const cities = citiesQuery.data || []
    if (!candidateCity) return 'Europe/Moscow'
    const match = cities.find((city) => city.name.toLowerCase() === candidateCity.toLowerCase())
    return match?.tz || 'Europe/Moscow'
  }, [candidateCity, citiesQuery.data])

  useEffect(() => {
    if (!introDayTemplate) {
      setTemplate('')
      setForm((prev) => ({
        ...prev,
        customMessage: buildIntroDayFallback(candidateFio, prev.date, prev.time),
      }))
      return
    }

    setTemplate(introDayTemplate)
    setForm((prev) => ({
      ...prev,
      customMessage: renderIntroDayTemplate(
        introDayTemplate,
        candidateFio,
        prev.date,
        prev.time,
        introDayTemplateContext,
      ),
    }))
  }, [candidateFio, introDayTemplate, introDayTemplateContext])

  useEffect(() => {
    setForm((prev) => ({
      ...prev,
      customMessage: template
        ? renderIntroDayTemplate(template, candidateFio, prev.date, prev.time, introDayTemplateContext)
        : buildIntroDayFallback(candidateFio, prev.date, prev.time),
    }))
  }, [candidateFio, form.date, form.time, introDayTemplateContext, template])

  const preview = useMemo(
    () => buildSlotTimePreview(form.date, form.time, recruiterTz, candidateTz),
    [candidateTz, form.date, form.time, recruiterTz],
  )

  const mutation = useMutation({
    mutationFn: async () =>
      scheduleCandidateIntroDay(candidateId, {
        date: form.date,
        time: form.time,
        custom_message: form.customMessage,
      }),
    onSuccess: () => {
      setError(null)
      onSuccess()
    },
    onError: (mutationError: unknown) => {
      setError((mutationError as Error).message || 'Не удалось назначить ознакомительный день')
    },
  })

  return (
    <ModalPortal>
      <div className="modal-overlay" onClick={(event) => event.target === event.currentTarget && onClose()} role="dialog" aria-modal="true">
        <div className="glass glass--elevated modal modal--sm messenger-introday-modal">
          <div className="modal__header">
            <div>
              <h2 className="modal__title">Назначить ознакомительный день</h2>
              <p className="modal__subtitle">
                Кандидат: <strong>{candidateFio}</strong>
                {candidateCity ? <><br />Город: {candidateCity}</> : null}
              </p>
            </div>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>
              Закрыть
            </button>
          </div>

          {error ? <div className="ui-alert ui-alert--error">{error}</div> : null}

          <div className="modal__body">
            {!introDayTemplate ? (
              <div className="ui-alert ui-alert--warning">
                В профиле города не найден шаблон ознакомительного дня. Можно отредактировать текст вручную.
              </div>
            ) : null}

            <div className="form-row">
              <label className="form-group">
                <span className="form-group__label">Дата</span>
                <input type="date" value={form.date} onChange={(event) => setForm((prev) => ({ ...prev, date: event.target.value }))} />
              </label>
              <label className="form-group">
                <span className="form-group__label">Время ({recruiterTz})</span>
                <input type="time" value={form.time} onChange={(event) => setForm((prev) => ({ ...prev, time: event.target.value }))} />
              </label>
            </div>

            {preview ? (
              <div className="glass slot-preview messenger-introday-modal__preview">
                <div>
                  <div className="slot-preview__label">Вы вводите</div>
                  <div className="slot-preview__value">{preview.recruiterLabel}</div>
                  <div className="slot-preview__hint">{preview.recruiterTz}</div>
                </div>
                <div>
                  <div className="slot-preview__label">Кандидат увидит</div>
                  <div className="slot-preview__value">{preview.candidateLabel}</div>
                  <div className="slot-preview__hint">{preview.candidateTz}</div>
                </div>
              </div>
            ) : null}

            <label className="form-group form-group--mt">
              <span className="form-group__label">Сообщение кандидату</span>
              <textarea
                rows={7}
                value={form.customMessage}
                onChange={(event) => setForm((prev) => ({ ...prev, customMessage: event.target.value }))}
                placeholder="Текст приглашения..."
                className="ui-input ui-input--multiline"
              />
            </label>
          </div>

          <div className="modal__footer">
            <button className="ui-btn ui-btn--primary" onClick={() => mutation.mutate()} disabled={!form.date || !form.time || mutation.isPending}>
              {mutation.isPending ? 'Назначаем…' : 'Назначить ОД'}
            </button>
            <button className="ui-btn ui-btn--ghost" onClick={onClose}>
              Отмена
            </button>
          </div>
        </div>
      </div>
    </ModalPortal>
  )
}
