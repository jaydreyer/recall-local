import { startTransition, useEffect, useMemo, useState } from 'react'

import {
  createCoverLetterDraft,
  createJobEvaluationRun,
  fetchJobGaps,
  fetchJobStats,
  fetchJobs,
  updateJob,
} from '../api'

const DEFAULT_FILTERS = {
  status: 'all',
  scoreRange: 'all',
  source: '',
  companyTier: '',
  sort: 'fit_score',
  order: 'desc',
  limit: 150,
}

function resolveScoreRange(scoreRange) {
  switch (scoreRange) {
    case '75-plus':
      return { min_score: 75, max_score: 100 }
    case '50-74':
      return { min_score: 50, max_score: 74 }
    case 'under-50':
      return { min_score: 0, max_score: 49 }
    default:
      return { min_score: 0, max_score: 100 }
  }
}

function buildFilters(filters) {
  const scoreBounds = resolveScoreRange(filters.scoreRange)
  return {
    status: filters.status,
    source: filters.source || undefined,
    company_tier: filters.companyTier ? Number(filters.companyTier) : undefined,
    sort: filters.sort,
    order: filters.order,
    limit: filters.limit,
    ...scoreBounds,
  }
}

function patchJobs(list, updated) {
  return list.map((job) => (job.jobId === updated.jobId ? { ...job, ...updated } : job))
}

export function useJobs() {
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [jobs, setJobs] = useState([])
  const [stats, setStats] = useState(null)
  const [gaps, setGaps] = useState(null)
  const [selectedJobId, setSelectedJobId] = useState(null)
  const [selectedJob, setSelectedJob] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [lastLoadedAt, setLastLoadedAt] = useState('')
  const [detailLoading, setDetailLoading] = useState(false)
  const [actionJobId, setActionJobId] = useState('')
  const [gapsLoading, setGapsLoading] = useState(true)
  const [gapsError, setGapsError] = useState('')
  const [gapsLoadedAt, setGapsLoadedAt] = useState('')
  const [coverLetterState, setCoverLetterState] = useState({
    jobId: '',
    loading: false,
    error: '',
    draft: null,
  })

  const apiFilters = useMemo(() => buildFilters(filters), [filters])

  function syncSelectedJob(jobId, items = jobs) {
    if (!jobId) {
      setSelectedJob(null)
      setDetailLoading(false)
      return
    }
    const match = items.find((job) => job.jobId === jobId) || null
    setSelectedJob(match)
    setDetailLoading(false)
  }

  function selectJob(jobId) {
    setSelectedJobId(jobId)
    syncSelectedJob(jobId)
  }

  async function loadJobsData() {
    setLoading(true)
    setError('')
    try {
      const [statsPayload, jobsPayload] = await Promise.all([fetchJobStats(), fetchJobs(apiFilters)])
      setStats(statsPayload)
      const items = Array.isArray(jobsPayload.items) ? jobsPayload.items : []
      setJobs(items)
      setLastLoadedAt(new Date().toISOString())
      if (!selectedJobId && items.length > 0) {
        setSelectedJobId(items[0].jobId)
        setSelectedJob(items[0])
      } else if (selectedJobId && items.length > 0 && !items.some((item) => item.jobId === selectedJobId)) {
        setSelectedJobId(items[0].jobId)
        setSelectedJob(items[0])
      } else if (selectedJobId) {
        syncSelectedJob(selectedJobId, items)
      }
    } catch (loadError) {
      setError(loadError.message || 'Unable to load jobs.')
    } finally {
      setLoading(false)
    }
  }

  async function loadGapData() {
    setGapsLoading(true)
    setGapsError('')
    try {
      const payload = await fetchJobGaps()
      setGaps(payload)
      setGapsLoadedAt(new Date().toISOString())
    } catch (loadError) {
      setGapsError(loadError.message || 'Unable to load skill gaps.')
    } finally {
      setGapsLoading(false)
    }
  }

  useEffect(() => {
    loadJobsData()
  }, [apiFilters])

  useEffect(() => {
    loadGapData()
  }, [])

  useEffect(() => {
    syncSelectedJob(selectedJobId)
  }, [jobs, selectedJobId])

  async function refresh() {
    await Promise.all([loadJobsData(), loadGapData()])
  }

  async function mutateJob(jobId, patch) {
    setActionJobId(jobId)
    setError('')
    try {
      const updated = await updateJob(jobId, patch)
      setJobs((current) => patchJobs(current, updated))
      if (selectedJobId === jobId) {
        setSelectedJob(updated)
      }
      await loadJobsData()
      return updated
    } catch (mutationError) {
      setError(mutationError.message || 'Job update failed.')
      return null
    } finally {
      setActionJobId('')
    }
  }

  async function reevaluateJob(jobId) {
    setActionJobId(jobId)
    setError('')
    try {
      await createJobEvaluationRun([jobId])
      await refresh()
    } catch (mutationError) {
      setError(mutationError.message || 'Re-evaluation failed.')
    } finally {
      setActionJobId('')
    }
  }

  async function generateDraft(jobId) {
    setCoverLetterState({ jobId, loading: true, error: '', draft: null })
    try {
      const payload = await createCoverLetterDraft({ job_id: jobId, save_to_vault: false })
      setCoverLetterState({ jobId, loading: false, error: '', draft: payload })
    } catch (draftError) {
      setCoverLetterState({
        jobId,
        loading: false,
        error: draftError.message || 'Draft generation failed.',
        draft: null,
      })
    }
  }

  function updateFilter(key, value) {
    startTransition(() => {
      setFilters((current) => ({ ...current, [key]: value }))
    })
  }

  return {
    filters,
    jobs,
    stats,
    gaps,
    loading,
    error,
    lastLoadedAt,
    gapsLoading,
    gapsError,
    gapsLoadedAt,
    selectedJobId,
    selectedJob,
    detailLoading,
    actionJobId,
    coverLetterState,
    setSelectedJobId: selectJob,
    setFilter: updateFilter,
    refresh,
    markApplied: (jobId) => mutateJob(jobId, { applied: true }),
    dismissJob: (jobId) => mutateJob(jobId, { dismissed: true }),
    saveNotes: (jobId, notes) => mutateJob(jobId, { notes }),
    reevaluateJob,
    generateDraft,
  }
}
