import { apiFetch } from '@/api/client'

export type HHConnectionSummary = {
  id: number
  principal_type: string
  principal_id: number
  status: 'active' | 'error' | 'revoked' | string
  employer_id?: string | null
  employer_name?: string | null
  manager_id?: string | null
  manager_account_id?: string | null
  manager_name?: string | null
  token_expires_at?: string | null
  last_sync_at?: string | null
  last_error?: string | null
  webhook_path?: string | null
  webhook_url?: string | null
}

export type HHConnectionPayload = {
  enabled: boolean
  connected: boolean
  connection: HHConnectionSummary | null
}

export type HHImportResult = {
  total_seen?: number
  created?: number
  updated?: number
  collections_seen?: number
  negotiations_seen?: number
  negotiations_created?: number
  negotiations_updated?: number
  candidates_created?: number
  candidates_linked?: number
  resumes_upserted?: number
  candidate_ids_touched?: number[]
}

export type HHSyncJob = {
  id: number
  connection_id?: number | null
  job_type: string
  direction?: string | null
  entity_type?: string | null
  entity_external_id?: string | null
  status: 'pending' | 'running' | 'done' | 'dead' | 'error' | string
  attempts: number
  payload?: Record<string, unknown>
  last_error?: string | null
  next_retry_at?: string | null
  started_at?: string | null
  finished_at?: string | null
  created_at?: string | null
}

type HHAuthorizeResponse = {
  ok: boolean
  authorize_url: string
  state: string
}

type HHRefreshResponse = {
  ok: boolean
  connection: HHConnectionSummary
}

type HHWebhooksResponse = {
  ok: boolean
  subscriptions: Record<string, unknown>[]
}

type HHRegisterWebhooksResponse = {
  ok: boolean
  webhook_url: string
  actions: string[]
  subscription: Record<string, unknown>
}

type HHImportResponse = {
  ok: boolean
  result: HHImportResult
}

type HHJobsResponse = {
  ok: boolean
  jobs: HHSyncJob[]
}

type HHQueuedJobResponse = {
  ok: boolean
  created: boolean
  job: HHSyncJob
}

type HHRetryJobResponse = {
  ok: boolean
  job: HHSyncJob
}

export function fetchHHConnection() {
  return apiFetch<HHConnectionPayload>('/integrations/hh/connection')
}

export async function getHHAuthorizeUrl(returnTo?: string): Promise<{ authorize_url: string; state: string }> {
  const query = new URLSearchParams()
  if (returnTo?.trim()) {
    query.set('return_to', returnTo.trim())
  }
  const suffix = query.toString() ? `?${query.toString()}` : ''
  const payload = await apiFetch<HHAuthorizeResponse>(`/integrations/hh/oauth/authorize${suffix}`)
  return {
    authorize_url: payload.authorize_url,
    state: payload.state,
  }
}

export async function refreshHHTokens(): Promise<HHConnectionPayload> {
  const payload = await apiFetch<HHRefreshResponse>('/integrations/hh/oauth/refresh', {
    method: 'POST',
  })
  return {
    enabled: true,
    connected: true,
    connection: payload.connection,
  }
}

export async function listHHWebhooks(): Promise<{ subscriptions: Record<string, unknown>[] }> {
  const payload = await apiFetch<HHWebhooksResponse>('/integrations/hh/webhooks')
  return { subscriptions: payload.subscriptions }
}

export async function registerHHWebhooks(): Promise<{
  webhook_url: string
  actions: string[]
  subscription: Record<string, unknown>
}> {
  const payload = await apiFetch<HHRegisterWebhooksResponse>('/integrations/hh/webhooks/register', {
    method: 'POST',
  })
  return {
    webhook_url: payload.webhook_url,
    actions: payload.actions,
    subscription: payload.subscription,
  }
}

export async function importHHVacancies(): Promise<HHImportResult> {
  const payload = await apiFetch<HHImportResponse>('/integrations/hh/import/vacancies', {
    method: 'POST',
  })
  return payload.result
}

export async function importHHNegotiations(
  vacancyId?: string,
  fetchResumeDetails?: boolean,
): Promise<HHImportResult> {
  const query = new URLSearchParams()
  if (vacancyId?.trim()) {
    query.set('vacancy_id', vacancyId.trim())
  }
  if (typeof fetchResumeDetails === 'boolean') {
    query.set('fetch_resume_details', String(fetchResumeDetails))
  }
  const suffix = query.toString() ? `?${query.toString()}` : ''
  const payload = await apiFetch<HHImportResponse>(`/integrations/hh/import/negotiations${suffix}`, {
    method: 'POST',
  })
  return payload.result
}

export async function listHHSyncJobs(
  limit = 20,
  status?: string,
): Promise<{ jobs: HHSyncJob[] }> {
  const query = new URLSearchParams()
  query.set('limit', String(limit))
  if (status?.trim()) {
    query.set('status', status.trim())
  }
  const payload = await apiFetch<HHJobsResponse>(`/integrations/hh/jobs?${query.toString()}`)
  return { jobs: payload.jobs }
}

export async function enqueueVacanciesImport(): Promise<{ created: boolean; job: HHSyncJob }> {
  const payload = await apiFetch<HHQueuedJobResponse>('/integrations/hh/jobs/import/vacancies', {
    method: 'POST',
  })
  return {
    created: payload.created,
    job: payload.job,
  }
}

export async function enqueueNegotiationsImport(
  vacancyId?: string,
  fetchResumeDetails?: boolean,
): Promise<{ created: boolean; job: HHSyncJob }> {
  const query = new URLSearchParams()
  if (vacancyId?.trim()) {
    query.set('vacancy_id', vacancyId.trim())
  }
  if (typeof fetchResumeDetails === 'boolean') {
    query.set('fetch_resume_details', String(fetchResumeDetails))
  }
  const suffix = query.toString() ? `?${query.toString()}` : ''
  const payload = await apiFetch<HHQueuedJobResponse>(`/integrations/hh/jobs/import/negotiations${suffix}`, {
    method: 'POST',
  })
  return {
    created: payload.created,
    job: payload.job,
  }
}

export async function retryHHSyncJob(jobId: number): Promise<{ job: HHSyncJob }> {
  const payload = await apiFetch<HHRetryJobResponse>(`/integrations/hh/jobs/${jobId}/retry`, {
    method: 'POST',
  })
  return { job: payload.job }
}
