import { QueryClient } from '@tanstack/react-query'

export const API_URL = '/api'
export const queryClient = new QueryClient()

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API_URL + path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    const err = new Error(text || res.statusText) as Error & { status?: number }
    err.status = res.status
    throw err
  }
  return res.json() as Promise<T>
}
