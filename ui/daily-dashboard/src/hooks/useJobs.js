import { startTransition, useEffect, useMemo, useState } from 'react'

import {
  createCoverLetterDraft,
  createJobEvaluationRun,
  fetchJob,
  fetchJobGaps,
  fetchJobStats,
  fetchJobs,
  updateJob,
} from '../api'
import { readCachedJson, writeCachedJson } from '../lib/cache'

const DEFAULT_FILTERS = {
  status: 'all',
  scoreRange: 'all',
  source: '',
  companyTier: '',
  sort: 'fit_score',
  order: 'desc',
  limit: 60,
}

const JOBS_CACHE_KEY = 'daily-dashboard-jobs-snapshot-v1'
const GAPS_CACHE_KEY = 'daily-dashboard-gap-snapshot-v1'

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
    view: 'summary',
    ...scoreBounds,
  }
}

function patchJobs(list, updated) {
  return list.map((job) => (job.jobId === updated.jobId ? { ...job, ...updated } : job))
}

function persistJobsSnapshot({ jobs, stats, lastLoadedAt, selectedJobId }) {
  writeCachedJson(JOBS_CACHE_KEY, {
    jobs,
    stats,
    lastLoadedAt,
    selectedJobId,
  })
}

function persistGapSnapshot({ gaps, lastLoadedAt }) {
  writeCachedJson(GAPS_CACHE_KEY, {
    gaps,
    lastLoadedAt,
  })
}

export function useJobs({ loadGaps = false } = {}) {
  const cachedJobsState = readCachedJson(JOBS_CACHE_KEY, {})
  const cachedGapsState = readCachedJson(GAPS_CACHE_KEY, {})
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [jobs, setJobs] = useState(Array.isArray(cachedJobsState.jobs) ? cachedJobsState.jobs : [])
  const [stats, setStats] = useState(cachedJobsState.stats || null)
  const [gaps, setGaps] = useState(cachedGapsState.gaps || null)
  const [selectedJobId, setSelectedJobId] = useState(cachedJobsState.selectedJobId || null)
  const [selectedJob, setSelectedJob] = useState(null)
  const [loading, setLoading] = useState(!(Array.isArray(cachedJobsState.jobs) && cachedJobsState.jobs.length > 0))
  const [error, setError] = useState('')
  const [lastLoadedAt, setLastLoadedAt] = useState(String(cachedJobsState.lastLoadedAt || ''))
  const [detailLoading, setDetailLoading] = useState(false)
  const [actionJobId, setActionJobId] = useState('')
  const [gapsLoading, setGapsLoading] = useState(false)
  const [gapsError, setGapsError] = useState('')
  const [gapsLoadedAt, setGapsLoadedAt] = useState(String(cachedGapsState.lastLoadedAt || ''))
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
  }

  function selectJob(jobId) {
    setSelectedJobId(jobId)
    syncSelectedJob(jobId)
  }

  async function loadJobsData() {
    setLoading(true)
    setError('')
    try {
      const jobsPayload = await fetchJobs(apiFilters)
      const items = Array.isArray(jobsPayload.items) ? jobsPayload.items : []
      const refreshedAt = new Date().toISOString()
      let nextSelectedJobId = selectedJobId

      setJobs(items)
      setLastLoadedAt(refreshedAt)

      if (!nextSelectedJobId && items.length > 0) {
        nextSelectedJobId = items[0].jobId
        setSelectedJobId(nextSelectedJobId)
      } else if (nextSelectedJobId && items.length > 0 && !items.some((item) => item.jobId === nextSelectedJobId)) {
        nextSelectedJobId = items[0].jobId
        setSelectedJobId(nextSelectedJobId)
      }

      if (nextSelectedJobId) {
        syncSelectedJob(nextSelectedJobId, items)
      }

      persistJobsSnapshot({
        jobs: items,
        stats,
        lastLoadedAt: refreshedAt,
        selectedJobId: nextSelectedJobId,
      })

      fetchJobStats()
        .then((statsPayload) => {
          setStats(statsPayload)
          persistJobsSnapshot({
            jobs: items,
            stats: statsPayload,
            lastLoadedAt: refreshedAt,
            selectedJobId: nextSelectedJobId,
          })
        })
        .catch(() => {
          // Keep the board usable even if stats lag or fail.
        })
    } catch (loadError) {
      const message = loadError.message || 'Unable to load jobs.'
      if (jobs.length > 0 || stats) {
        setError(`Showing last cached board snapshot. Live refresh failed: ${message}`)
      } else {
        setError(message)
      }
    } finally {
      setLoading(false)
    }
  }

  async function loadGapData() {
    setGapsLoading(true)
    setGapsError('')
    try {
      const payload = await fetchJobGaps()
      const refreshedAt = new Date().toISOString()
      setGaps(payload)
      setGapsLoadedAt(refreshedAt)
      persistGapSnapshot({ gaps: payload, lastLoadedAt: refreshedAt })
    } catch (loadError) {
      const message = loadError.message || 'Unable to load skill gaps.'
      if (gaps) {
        setGapsError(`Showing last cached learning radar. Live refresh failed: ${message}`)
      } else {
        setGapsError(message)
      }
    } finally {
      setGapsLoading(false)
    }
  }

  useEffect(() => {
    loadJobsData()
  }, [apiFilters])

  useEffect(() => {
    if (loadGaps) {
      loadGapData()
    }
  }, [loadGaps])

  useEffect(() => {
    syncSelectedJob(selectedJobId)
  }, [jobs, selectedJobId])

  useEffect(() => {
    const jobId = String(selectedJobId || '').trim()
    const summaryJob = jobs.find((job) => job.jobId === jobId) || null
    if (!jobId || !summaryJob) {
      return
    }

    let cancelled = false
    setSelectedJob(summaryJob)
    setDetailLoading(true)

    fetchJob(jobId)
      .then((payload) => {
        if (!cancelled) {
          setSelectedJob(payload || summaryJob)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSelectedJob(summaryJob)
        }
      })
      .finally(() => {
        if (!cancelled) {
          setDetailLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [jobs, selectedJobId])

  async function refresh() {
    const tasks = [loadJobsData()]
    if (loadGaps) {
      tasks.push(loadGapData())
    }
    await Promise.all(tasks)
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
    loadGapData,
    markApplied: (jobId) => mutateJob(jobId, { applied: true }),
    dismissJob: (jobId) => mutateJob(jobId, { dismissed: true }),
    saveNotes: (jobId, notes) => mutateJob(jobId, { notes }),
    reevaluateJob,
    generateDraft,
  }
}
