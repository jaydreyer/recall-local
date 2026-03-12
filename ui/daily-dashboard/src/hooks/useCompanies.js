import { useEffect, useRef, useState } from 'react'

import { createCompany, fetchCompanies, fetchCompany, refreshCompanyProfile, updateCompany } from '../api'
import { readCachedJson, writeCachedJson } from '../lib/cache'

const COMPANIES_CACHE_KEY = 'daily-dashboard-companies-snapshot-v1'
const COMPANIES_REFRESH_INTERVAL_MS = 180000
const COMPANIES_RETRY_INTERVAL_MS = 20000

function preferredCompany(items) {
  return [...items].sort((left, right) => {
    const tierDelta = Number(left.tier || 3) - Number(right.tier || 3)
    if (tierDelta !== 0) {
      return tierDelta
    }

    const leftScore = Number(left.jobs_summary?.highest_fit_score ?? left.best_fit_score ?? -1)
    const rightScore = Number(right.jobs_summary?.highest_fit_score ?? right.best_fit_score ?? -1)
    if (rightScore !== leftScore) {
      return rightScore - leftScore
    }

    const leftJobs = Number(left.job_count || 0)
    const rightJobs = Number(right.job_count || 0)
    if (rightJobs !== leftJobs) {
      return rightJobs - leftJobs
    }

    return String(left.company_name || '').localeCompare(String(right.company_name || ''))
  })[0]
}

function persistCompanySnapshot({ companies, selectedCompanyId, selectedCompany, lastLoadedAt }) {
  writeCachedJson(COMPANIES_CACHE_KEY, {
    companies,
    selectedCompanyId,
    selectedCompany,
    lastLoadedAt,
  })
}

export function useCompanies({ enabled = false } = {}) {
  const cachedState = readCachedJson(COMPANIES_CACHE_KEY, {})
  const hasCachedCompanies = Array.isArray(cachedState.companies) && cachedState.companies.length > 0
  const [companies, setCompanies] = useState(hasCachedCompanies ? cachedState.companies : [])
  const [selectedCompanyId, setSelectedCompanyId] = useState(cachedState.selectedCompanyId || '')
  const [selectedCompany, setSelectedCompany] = useState(cachedState.selectedCompany || null)
  const [loading, setLoading] = useState(enabled && !hasCachedCompanies)
  const [detailLoading, setDetailLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [savingCompanyId, setSavingCompanyId] = useState('')
  const [error, setError] = useState('')
  const [lastLoadedAt, setLastLoadedAt] = useState(String(cachedState.lastLoadedAt || ''))
  const [detailError, setDetailError] = useState('')
  const [saveError, setSaveError] = useState('')
  const [dataSource, setDataSource] = useState(hasCachedCompanies ? 'cache' : 'live')
  const companiesCountRef = useRef(companies.length)

  useEffect(() => {
    companiesCountRef.current = companies.length
  }, [companies.length])

  async function loadCompanies({ background = false } = {}) {
    if (!background || !companiesCountRef.current) {
      setLoading(true)
    }
    setError('')
    setSaveError('')
    try {
      const payload = await fetchCompanies({ include_jobs: false, limit: 300 })
      const items = Array.isArray(payload.items) ? payload.items : []
      const refreshedAt = new Date().toISOString()
      let nextSelectedCompanyId = selectedCompanyId

      setCompanies(items)
      setLastLoadedAt(refreshedAt)
      setDataSource('live')

      if (items.length > 0 && (!nextSelectedCompanyId || !items.some((item) => item.company_id === nextSelectedCompanyId))) {
        const preferred = preferredCompany(items)
        if (preferred) {
          nextSelectedCompanyId = preferred.company_id
          setSelectedCompanyId(nextSelectedCompanyId)
        }
      } else if (!nextSelectedCompanyId && items.length > 0) {
        const preferred = items.find((item) => item.job_count > 0) || items[0]
        nextSelectedCompanyId = preferred.company_id
        setSelectedCompanyId(nextSelectedCompanyId)
      }

      persistCompanySnapshot({
        companies: items,
        selectedCompanyId: nextSelectedCompanyId,
        selectedCompany,
        lastLoadedAt: refreshedAt,
      })
    } catch (loadError) {
      const message = loadError.message || 'Unable to load companies.'
      if (companies.length > 0) {
        setDataSource('cache')
        setError(`Showing cached watchlist. Live refresh failed: ${message}`)
      } else {
        setError(message)
      }
    } finally {
      setLoading(false)
    }
  }

  async function loadCompany(companyId) {
    if (!companyId || !enabled) {
      setSelectedCompany(null)
      return
    }
    setDetailLoading(true)
    setDetailError('')
    try {
      const payload = await fetchCompany(companyId)
      setSelectedCompany(payload)
      persistCompanySnapshot({
        companies,
        selectedCompanyId: companyId,
        selectedCompany: payload,
        lastLoadedAt,
      })
    } catch (loadError) {
      const cachedDetail = cachedState.selectedCompany
      if (cachedDetail && cachedDetail.company_id === companyId) {
        setSelectedCompany(cachedDetail)
        setDetailError(`Showing cached company profile. Live refresh failed: ${loadError.message || 'Unable to load company profile.'}`)
      } else {
        setSelectedCompany(null)
        setDetailError(loadError.message || 'Unable to load company profile.')
      }
    } finally {
      setDetailLoading(false)
    }
  }

  useEffect(() => {
    if (enabled) {
      loadCompanies({ background: hasCachedCompanies })
    }
  }, [enabled])

  useEffect(() => {
    if (enabled) {
      loadCompany(selectedCompanyId)
    }
  }, [enabled, selectedCompanyId])

  useEffect(() => {
    if (typeof window === 'undefined' || !enabled) {
      return undefined
    }

    const intervalId = window.setInterval(() => {
      if (!document.hidden) {
        loadCompanies({ background: true })
      }
    }, COMPANIES_REFRESH_INTERVAL_MS)

    function handleForegroundRefresh() {
      loadCompanies({ background: true })
      if (selectedCompanyId) {
        loadCompany(selectedCompanyId)
      }
    }

    function handleVisibilityChange() {
      if (!document.hidden) {
        handleForegroundRefresh()
      }
    }

    window.addEventListener('focus', handleForegroundRefresh)
    window.addEventListener('online', handleForegroundRefresh)
    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      window.clearInterval(intervalId)
      window.removeEventListener('focus', handleForegroundRefresh)
      window.removeEventListener('online', handleForegroundRefresh)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [enabled, selectedCompanyId])

  useEffect(() => {
    if (typeof window === 'undefined' || !enabled || !error) {
      return undefined
    }
    const retryId = window.setTimeout(() => {
      loadCompanies({ background: true })
    }, COMPANIES_RETRY_INTERVAL_MS)
    return () => window.clearTimeout(retryId)
  }, [enabled, error])

  async function refreshSelectedCompany() {
    if (!selectedCompanyId) {
      return
    }
    setRefreshing(true)
    setDetailError('')
    try {
      await refreshCompanyProfile(selectedCompanyId)
      await Promise.all([loadCompanies({ background: true }), loadCompany(selectedCompanyId)])
    } catch (refreshError) {
      setDetailError(refreshError.message || 'Unable to refresh company profile.')
    } finally {
      setRefreshing(false)
    }
  }

  async function saveCompanyDraft(draft, { companyId } = {}) {
    setSaving(true)
    setSavingCompanyId(companyId || '__new__')
    setSaveError('')
    try {
      const payload = companyId ? await updateCompany(companyId, draft) : await createCompany(draft)
      const savedId = payload.company_id || companyId
      await loadCompanies({ background: false })
      if (savedId) {
        setSelectedCompanyId(savedId)
        await loadCompany(savedId)
      }
      return { ok: true, payload }
    } catch (saveError) {
      setSaveError(saveError.message || 'Unable to save company settings.')
      return { ok: false, error: saveError }
    } finally {
      setSaving(false)
      setSavingCompanyId('')
    }
  }

  return {
    companies,
    selectedCompanyId,
    selectedCompany,
    loading,
    detailLoading,
    refreshing,
    saving,
    savingCompanyId,
    error,
    lastLoadedAt,
    dataSource,
    detailError,
    saveError,
    selectCompany: setSelectedCompanyId,
    refresh: loadCompanies,
    refreshSelectedCompany,
    createCompany: (draft) => saveCompanyDraft(draft),
    updateCompany: (companyId, draft) => saveCompanyDraft(draft, { companyId }),
    moveCompanyTier: (companyId, tier) => saveCompanyDraft({ tier }, { companyId }),
  }
}
