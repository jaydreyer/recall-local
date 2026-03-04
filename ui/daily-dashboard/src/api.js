const apiBaseUrl = (import.meta.env.VITE_RECALL_API_BASE_URL || 'http://localhost:8090').replace(/\/+$/, '')
const apiKey = (import.meta.env.VITE_RECALL_API_KEY || '').trim()

function buildHeaders() {
  const headers = { Accept: 'application/json' }
  if (apiKey) {
    headers['X-API-Key'] = apiKey
  }
  return headers
}

async function getJson(path) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: 'GET',
    headers: buildHeaders(),
  })
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`${response.status} ${response.statusText}: ${errorText}`)
  }
  return response.json()
}

export async function fetchJobStats() {
  return getJson('/v1/job-stats')
}

export async function fetchTopJobs() {
  return getJson('/v1/jobs?status=evaluated&sort=fit_score&order=desc&limit=5&offset=0')
}

export function getBridgeConfig() {
  return {
    baseUrl: apiBaseUrl,
    apiKeyConfigured: Boolean(apiKey),
  }
}
