export type RecruiterFormState = {
  name: string
  tz: string
  tg_chat_id: string
  telemost_url: string
  active: boolean
  city_ids: number[]
}

export type RecruiterFormErrors = {
  name?: string
  tz?: string
  tg_chat_id?: string
  telemost_url?: string
}

export function validateRecruiterForm(form: RecruiterFormState): {
  valid: boolean
  errors: RecruiterFormErrors
} {
  const errors: RecruiterFormErrors = {}
  if (!form.name.trim()) {
    errors.name = 'Укажите имя'
  }
  if (!form.tz.trim()) {
    errors.tz = 'Укажите часовой пояс'
  }
  if (form.tg_chat_id && Number.isNaN(Number(form.tg_chat_id))) {
    errors.tg_chat_id = 'TG chat ID должен быть числом'
  }
  return { valid: Object.keys(errors).length === 0, errors }
}

export function getTzPreview(tz: string): string {
  try {
    return new Intl.DateTimeFormat('ru-RU', {
      timeZone: tz,
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date())
  } catch {
    return ''
  }
}
