import { QueryClient } from '@tanstack/react-query'

export const API_URL = '/api'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000, // Data is fresh for 30s
      refetchOnWindowFocus: false, // Don't spam server on tab switch
    },
  },
})

let csrfToken: string | null = null
let csrfPromise: Promise<string> | null = null

type ErrorDetails = {
  message?: string
}

type ErrorPayload = {
  detail?: string | ErrorDetails
  message?: string
  errors?: string[]
  error?: string | ErrorDetails
}

type ApiClientError = Error & {
  status?: number
  data?: unknown
}

function isErrorDetails(value: unknown): value is ErrorDetails {
  return Boolean(value) && typeof value === 'object' && typeof (value as ErrorDetails).message === 'string'
}

function isErrorPayload(value: unknown): value is ErrorPayload {
  return Boolean(value) && typeof value === 'object'
}

async function fetchCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken
  if (!csrfPromise) {
    csrfPromise = fetch(`${API_URL}/csrf`, { credentials: 'include' })
      .then(async (res) => {
        if (!res.ok) throw new Error('CSRF fetch failed')
        const data = (await res.json()) as { token?: string }
        csrfToken = data.token || ''
        return csrfToken
      })
      .finally(() => {
        csrfPromise = null
      })
  }
  return csrfPromise
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method || 'GET').toUpperCase()
  const needsCsrf = !['GET', 'HEAD', 'OPTIONS'].includes(method)
  
  let headerObj: Record<string, string> = {}
  if (init?.headers) {
    if (init.headers instanceof Headers) {
      init.headers.forEach((value, key) => {
        headerObj[key] = value
      })
    } else if (Array.isArray(init.headers)) {
      init.headers.forEach(([key, value]) => {
        headerObj[key] = value
      })
    } else {
      headerObj = init.headers as Record<string, string>
    }
  }

  const isFormData = typeof FormData !== 'undefined' && init?.body instanceof FormData
  let headers = new Headers({
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(headerObj as Record<string, string>),
  })

  if (needsCsrf) {
    const token = await fetchCsrfToken()
    if (token) headers.set('x-csrf-token', token)
  }

  const res = await fetch(API_URL + path, {
    credentials: 'include',
    headers,
    ...init,
  })
  if (res.status === 403 && needsCsrf) {
    // refresh token once and retry
    csrfToken = null
    const token = await fetchCsrfToken()
    const retryHeaders = new Headers(headers)
    retryHeaders.set('x-csrf-token', token)
    const retryRes = await fetch(API_URL + path, {
      credentials: 'include',
      headers: retryHeaders,
      ...init,
    })
    if (!retryRes.ok) {
      let retryMsg = ''
      try {
        const retryData = await retryRes.json()
        retryMsg = retryData?.detail?.message || retryData?.detail || retryData?.message || ''
        if (typeof retryMsg !== 'string') retryMsg = JSON.stringify(retryMsg)
      } catch {
        retryMsg = await retryRes.text().catch(() => '')
      }
      const err = new Error(retryMsg || retryRes.statusText || 'Ошибка авторизации') as Error & { status?: number }
      err.status = retryRes.status
      throw err
    }
    return retryRes.json() as Promise<T>
  }
  if (!res.ok) {
    let message = ''
    let data: unknown = null
    const contentType = res.headers.get('content-type') || ''
    if (contentType.includes('application/json')) {
      try {
        data = await res.json()
      } catch {
        data = null
      }
    } else {
      const text = await res.text()
      try {
        data = JSON.parse(text)
      } catch {
        message = text
      }
    }
    if (!message && data) {
      if (typeof data === 'string') message = data
      else if (isErrorPayload(data) && data.detail) {
        message = typeof data.detail === 'string' ? data.detail : data.detail.message || ''
      } else if (isErrorPayload(data) && typeof data.message === 'string') {
        message = data.message
      } else if (isErrorPayload(data) && Array.isArray(data.errors)) {
        message = data.errors.join(', ')
      } else if (isErrorPayload(data) && data.error) {
        if (typeof data.error === 'string') message = data.error
        else if (isErrorDetails(data.error)) message = data.error.message || ''
        else message = JSON.stringify(data.error)
      }
    }
    const err = new Error(message || res.statusText || `Ошибка ${res.status}`) as ApiClientError
    err.status = res.status
    err.data = data
    throw err
  }
  return res.json() as Promise<T>
}
