const rawBaseUrl = (import.meta.env.VITE_RECALL_API_BASE_URL || '').replace(/\/+$/, '')
const apiBaseUrl = rawBaseUrl
const apiKey = (import.meta.env.VITE_RECALL_API_KEY || '').trim()

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
    throw new Error(`${response.status} ${response.statusText}: ${errorText}`)
  }
  return response.json()
}

async function getJson(path) {
  const response = await fetch(buildUrl(path), {
    method: 'GET',
    headers: buildHeaders(),
  })
  return parseResponse(response)
}

async function sendJson(path, method, body) {
  const response = await fetch(buildUrl(path), {
    method,
    headers: {
      ...buildHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  return parseResponse(response)
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
  return `/v1/jobs?${params.toString()}`
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

export function fetchCompanies() {
  return getJson('/v1/companies')
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
