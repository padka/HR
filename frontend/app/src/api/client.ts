import { QueryClient } from '@tanstack/react-query'

export const API_URL = '/api'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000, // Data is fresh for 30s
      refetchOnWindowFocus: false, // Don't spam server on tab switch
      refetchOnReconnect: false, // Avoid reconnect storms on flaky networks
    },
  },
})

let csrfToken: string | null = null
let csrfPromise: Promise<string> | null = null

type ApiFetchInit = Omit<RequestInit, 'body'> & {
  body?: unknown
  skipCsrf?: boolean
}

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

function isFormDataBody(value: unknown): value is FormData {
  return typeof FormData !== 'undefined' && value instanceof FormData
}

function isUrlSearchParamsBody(value: unknown): value is URLSearchParams {
  return typeof URLSearchParams !== 'undefined' && value instanceof URLSearchParams
}

function isReadableStreamBody(value: unknown): value is ReadableStream {
  return typeof ReadableStream !== 'undefined' && value instanceof ReadableStream
}

function normalizeRequestBody(body: RequestInit['body'] | unknown): BodyInit | null | undefined {
  if (
    body == null
    || typeof body === 'string'
    || isFormDataBody(body)
    || isUrlSearchParamsBody(body)
    || (typeof Blob !== 'undefined' && body instanceof Blob)
    || body instanceof ArrayBuffer
    || ArrayBuffer.isView(body)
    || isReadableStreamBody(body)
  ) {
    return body as BodyInit | null | undefined
  }
  return JSON.stringify(body)
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

export async function apiFetch<T>(path: string, init?: ApiFetchInit): Promise<T> {
  const { body: requestBody, skipCsrf = false, ...requestInit } = init ?? {}
  const method = (init?.method || 'GET').toUpperCase()
  const needsCsrf = !['GET', 'HEAD', 'OPTIONS'].includes(method)
  const normalizedBody = normalizeRequestBody(requestBody)
  
  let headerObj: Record<string, string> = {}
  if (requestInit.headers) {
    if (requestInit.headers instanceof Headers) {
      requestInit.headers.forEach((value, key) => {
        headerObj[key] = value
      })
    } else if (Array.isArray(requestInit.headers)) {
      requestInit.headers.forEach(([key, value]) => {
        headerObj[key] = value
      })
    } else {
      headerObj = requestInit.headers as Record<string, string>
    }
  }

  const isFormData = isFormDataBody(requestBody)
  const isUrlEncoded = isUrlSearchParamsBody(requestBody)
  let headers = new Headers({
    ...(isFormData || isUrlEncoded || requestBody == null ? {} : { 'Content-Type': 'application/json' }),
    ...(headerObj as Record<string, string>),
  })

  if (needsCsrf && !skipCsrf) {
    const token = await fetchCsrfToken()
    if (token) headers.set('x-csrf-token', token)
  }

  const res = await fetch(API_URL + path, {
    ...requestInit,
    credentials: 'include',
    headers,
    body: normalizedBody,
  })
  if (res.status === 403 && needsCsrf && !skipCsrf) {
    // refresh token once and retry
    csrfToken = null
    const token = await fetchCsrfToken()
    const retryHeaders = new Headers(headers)
    retryHeaders.set('x-csrf-token', token)
    const retryRes = await fetch(API_URL + path, {
      ...requestInit,
      credentials: 'include',
      headers: retryHeaders,
      body: normalizedBody,
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
    if (retryRes.status === 204) {
      return undefined as T
    }
    const retryContentType = retryRes.headers.get('content-type') || ''
    if (!retryContentType || retryContentType.includes('application/json')) {
      return retryRes.json() as Promise<T>
    }
    return retryRes.text() as Promise<T>
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
  if (res.status === 204) {
    return undefined as T
  }
  const contentType = res.headers.get('content-type') || ''
  if (!contentType || contentType.includes('application/json')) {
    return res.json() as Promise<T>
  }
  return res.text() as Promise<T>
}
