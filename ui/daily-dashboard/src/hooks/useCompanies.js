import { useEffect, useState } from 'react'

import { createCompany, fetchCompanies, fetchCompany, refreshCompanyProfile, updateCompany } from '../api'
import { readCachedJson, writeCachedJson } from '../lib/cache'

const COMPANIES_CACHE_KEY = 'daily-dashboard-companies-snapshot-v1'

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

function persistCompanySnapshot({ companies, selectedCompanyId, lastLoadedAt }) {
  writeCachedJson(COMPANIES_CACHE_KEY, {
    companies,
    selectedCompanyId,
    lastLoadedAt,
  })
}

export function useCompanies({ enabled = false } = {}) {
  const cachedState = readCachedJson(COMPANIES_CACHE_KEY, {})
  const [companies, setCompanies] = useState(Array.isArray(cachedState.companies) ? cachedState.companies : [])
  const [selectedCompanyId, setSelectedCompanyId] = useState(cachedState.selectedCompanyId || '')
  const [selectedCompany, setSelectedCompany] = useState(null)
  const [loading, setLoading] = useState(enabled && !(Array.isArray(cachedState.companies) && cachedState.companies.length > 0))
  const [detailLoading, setDetailLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [savingCompanyId, setSavingCompanyId] = useState('')
  const [error, setError] = useState('')
  const [lastLoadedAt, setLastLoadedAt] = useState(String(cachedState.lastLoadedAt || ''))
  const [detailError, setDetailError] = useState('')
  const [saveError, setSaveError] = useState('')

  async function loadCompanies() {
    setLoading(true)
    setError('')
    setSaveError('')
    try {
      const payload = await fetchCompanies({ include_jobs: false, limit: 300 })
      const items = Array.isArray(payload.items) ? payload.items : []
      const refreshedAt = new Date().toISOString()
      let nextSelectedCompanyId = selectedCompanyId

      setCompanies(items)
      setLastLoadedAt(refreshedAt)

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
        lastLoadedAt: refreshedAt,
      })
    } catch (loadError) {
      const message = loadError.message || 'Unable to load companies.'
      if (companies.length > 0) {
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
    } catch (loadError) {
      setSelectedCompany(null)
      setDetailError(loadError.message || 'Unable to load company profile.')
    } finally {
      setDetailLoading(false)
    }
  }

  useEffect(() => {
    if (enabled) {
      loadCompanies()
    }
  }, [enabled])

  useEffect(() => {
    if (enabled) {
      loadCompany(selectedCompanyId)
    }
  }, [enabled, selectedCompanyId])

  async function refreshSelectedCompany() {
    if (!selectedCompanyId) {
      return
    }
    setRefreshing(true)
    setDetailError('')
    try {
      await refreshCompanyProfile(selectedCompanyId)
      await Promise.all([loadCompanies(), loadCompany(selectedCompanyId)])
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
      await loadCompanies()
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
