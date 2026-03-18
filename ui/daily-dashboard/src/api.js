const rawBaseUrl = (import.meta.env.VITE_RECALL_API_BASE_URL || '').replace(/\/+$/, '')
const apiBaseUrl = rawBaseUrl
const apiKey = (import.meta.env.VITE_RECALL_API_KEY || '').trim()
const GET_TIMEOUT_MS = 25000
const MUTATION_TIMEOUT_MS = 45000
const RETRYABLE_STATUS_CODES = new Set([408, 429, 500, 502, 503, 504])
const RECENT_GET_TTL_MS = 3000
const inflightGetRequests = new Map()
const recentGetResponses = new Map()

function buildHeaders() {
  const headers = { Accept: 'application/json' }
  if (apiKey) {
    headers['X-API-Key'] = apiKey
  }
  return headers
}

function buildUrl(path) {
  return `${apiBaseUrl}${path}`
}

async function parseResponse(response) {
  if (!response.ok) {
    const errorText = await response.text()
    const error = new Error(`${response.status} ${response.statusText}: ${errorText}`)
    error.retryable = RETRYABLE_STATUS_CODES.has(response.status)
    throw error
  }
  return response.json()
}

function sleep(delayMs) {
  return new Promise((resolve) => window.setTimeout(resolve, delayMs))
}

async function requestJson(path, { method = 'GET', body, timeoutMs, retries = 0 } = {}) {
  let lastError = null

  for (let attempt = 0; attempt <= retries; attempt += 1) {
    const controller = new AbortController()
    const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs)

    try {
      const response = await fetch(buildUrl(path), {
        method,
        headers: body === undefined
          ? buildHeaders()
          : {
              ...buildHeaders(),
              'Content-Type': 'application/json',
            },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      })
      window.clearTimeout(timeoutId)
      return await parseResponse(response)
    } catch (error) {
      window.clearTimeout(timeoutId)
      const timedOut = error?.name === 'AbortError'
      const retryable = Boolean(error?.retryable) || timedOut || error instanceof TypeError
      lastError = timedOut ? new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s.`) : error
      if (attempt < retries && retryable) {
        await sleep(350 * (attempt + 1))
        continue
      }
      throw lastError
    }
  }

  throw lastError || new Error('Request failed.')
}

async function getJson(path) {
  const recent = recentGetResponses.get(path)
  if (recent && recent.expiresAt > Date.now()) {
    return recent.payload
  }

  const inflight = inflightGetRequests.get(path)
  if (inflight) {
    return inflight
  }

  const request = requestJson(path, {
    method: 'GET',
    timeoutMs: GET_TIMEOUT_MS,
    retries: 1,
  })
    .then((payload) => {
      recentGetResponses.set(path, {
        payload,
        expiresAt: Date.now() + RECENT_GET_TTL_MS,
      })
      return payload
    })
    .finally(() => {
      inflightGetRequests.delete(path)
    })

  inflightGetRequests.set(path, request)
  return request
}

async function sendJson(path, method, body) {
  recentGetResponses.clear()
  return requestJson(path, {
    method,
    body,
    timeoutMs: MUTATION_TIMEOUT_MS,
    retries: 0,
  })
}

function buildJobQuery(filters) {
  const params = new URLSearchParams()
  params.set('limit', String(filters.limit || 100))
  params.set('offset', '0')
  params.set('sort', filters.sort || 'fit_score')
  params.set('order', filters.order || 'desc')
  params.set('status', filters.status || 'evaluated')

  if (typeof filters.min_score === 'number') {
    params.set('min_score', String(filters.min_score))
  }
  if (typeof filters.max_score === 'number') {
    params.set('max_score', String(filters.max_score))
  }
  if (filters.source) {
    params.set('source', filters.source)
  }
  if (filters.company_tier) {
    params.set('company_tier', String(filters.company_tier))
  }
  if (filters.search) {
    params.set('search', filters.search)
  }
  if (filters.view) {
    params.set('view', String(filters.view))
  }
  return `/v1/jobs?${params.toString()}`
}

function buildCompaniesQuery(options = {}) {
  const params = new URLSearchParams()
  if (typeof options.limit === 'number' && Number.isFinite(options.limit) && options.limit > 0) {
    params.set('limit', String(options.limit))
  }
  if (typeof options.include_jobs === 'boolean') {
    params.set('include_jobs', options.include_jobs ? 'true' : 'false')
  }
  const query = params.toString()
  return query ? `/v1/companies?${query}` : '/v1/companies'
}

export function getBridgeConfig() {
  return {
    baseUrl: apiBaseUrl || 'same-origin /v1',
    apiKeyConfigured: Boolean(apiKey),
  }
}

export function fetchJobStats() {
  return getJson('/v1/job-stats')
}

export function fetchJobs(filters) {
  return getJson(buildJobQuery(filters))
}

export function fetchJob(jobId) {
  return getJson(`/v1/jobs/${jobId}`)
}

export function updateJob(jobId, patch) {
  return sendJson(`/v1/jobs/${jobId}`, 'PATCH', patch)
}

export function createJobEvaluationRun(jobIds) {
  return sendJson('/v1/job-evaluation-runs', 'POST', { job_ids: jobIds, wait: true })
}

export function fetchJobGaps() {
  return getJson('/v1/job-gaps')
}

export function fetchCompanies(options = {}) {
  return getJson(buildCompaniesQuery(options))
}

export function fetchCompany(companyId) {
  return getJson(`/v1/companies/${companyId}`)
}

export function refreshCompanyProfile(companyId) {
  return sendJson('/v1/company-profile-refresh-runs', 'POST', { company_id: companyId })
}

export function createCompany(payload) {
  return sendJson('/v1/companies', 'POST', payload)
}

export function updateCompany(companyId, patch) {
  return sendJson(`/v1/companies/${companyId}`, 'PATCH', patch)
}

export function fetchLLMSettings() {
  return getJson('/v1/llm-settings')
}

export function updateLLMSettings(patch) {
  return sendJson('/v1/llm-settings', 'PATCH', patch)
}

export function createCoverLetterDraft(payload) {
  return sendJson('/v1/cover-letter-drafts', 'POST', payload)
}

export function createTailoredSummary(payload) {
  return sendJson('/v1/tailored-summaries', 'POST', payload)
}

export function createResumeBullets(payload) {
  return sendJson('/v1/resume-bullets', 'POST', payload)
}

export function createOutreachNote(payload) {
  return sendJson('/v1/outreach-notes', 'POST', payload)
}

export function createTalkingPoints(payload) {
  return sendJson('/v1/talking-points', 'POST', payload)
}
