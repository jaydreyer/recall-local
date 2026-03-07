import { useEffect, useState } from 'react'

import { createCompany, fetchCompanies, fetchCompany, refreshCompanyProfile, updateCompany } from '../api'

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

export function useCompanies() {
  const [companies, setCompanies] = useState([])
  const [selectedCompanyId, setSelectedCompanyId] = useState('')
  const [selectedCompany, setSelectedCompany] = useState(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [savingCompanyId, setSavingCompanyId] = useState('')
  const [error, setError] = useState('')
  const [lastLoadedAt, setLastLoadedAt] = useState('')
  const [detailError, setDetailError] = useState('')
  const [saveError, setSaveError] = useState('')

  async function loadCompanies() {
    setLoading(true)
    setError('')
    setSaveError('')
    try {
      const payload = await fetchCompanies()
      const items = Array.isArray(payload.items) ? payload.items : []
      setCompanies(items)
      setLastLoadedAt(new Date().toISOString())
      if (items.length > 0 && (!selectedCompanyId || !items.some((item) => item.company_id === selectedCompanyId))) {
        const preferred = preferredCompany(items)
        if (preferred) {
          setSelectedCompanyId(preferred.company_id)
        }
      } else if (!selectedCompanyId) {
        const preferred = items.find((item) => item.job_count > 0) || items[0]
        setSelectedCompanyId(preferred.company_id)
      }
    } catch (loadError) {
      setError(loadError.message || 'Unable to load companies.')
    } finally {
      setLoading(false)
    }
  }

  async function loadCompany(companyId) {
    if (!companyId) {
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
    loadCompanies()
  }, [])

  useEffect(() => {
    loadCompany(selectedCompanyId)
  }, [selectedCompanyId])

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
