import { startTransition, useEffect, useMemo, useRef, useState } from 'react'

import {
  createCoverLetterDraft,
  createInterviewBrief,
  createJobEvaluationRun,
  createOutreachNote,
  createResumeBullets,
  createTailoredSummary,
  createTalkingPoints,
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
  search: '',
  sort: 'fit_score',
  order: 'desc',
  limit: 60,
}

const JOBS_CACHE_KEY = 'daily-dashboard-jobs-snapshot-v1'
const GAPS_CACHE_KEY = 'daily-dashboard-gap-snapshot-v1'
const JOBS_REFRESH_INTERVAL_MS = 120000
const JOBS_RETRY_INTERVAL_MS = 15000
const GAPS_REFRESH_INTERVAL_MS = 300000
const GAPS_RETRY_INTERVAL_MS = 30000

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
    search: filters.search || undefined,
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
  const hasCachedJobs = Array.isArray(cachedJobsState.jobs) && cachedJobsState.jobs.length > 0
  const hasCachedGaps = Boolean(cachedGapsState.gaps)
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [jobs, setJobs] = useState(hasCachedJobs ? cachedJobsState.jobs : [])
  const [stats, setStats] = useState(cachedJobsState.stats || null)
  const [gaps, setGaps] = useState(cachedGapsState.gaps || null)
  const [selectedJobId, setSelectedJobId] = useState(cachedJobsState.selectedJobId || null)
  const [selectedJob, setSelectedJob] = useState(null)
  const [loading, setLoading] = useState(!hasCachedJobs)
  const [error, setError] = useState('')
  const [lastLoadedAt, setLastLoadedAt] = useState(String(cachedJobsState.lastLoadedAt || ''))
  const [detailLoading, setDetailLoading] = useState(false)
  const [actionJobId, setActionJobId] = useState('')
  const [gapsLoading, setGapsLoading] = useState(false)
  const [gapsError, setGapsError] = useState('')
  const [gapsLoadedAt, setGapsLoadedAt] = useState(String(cachedGapsState.lastLoadedAt || ''))
  const [dataSource, setDataSource] = useState(hasCachedJobs ? 'cache' : 'live')
  const [gapsDataSource, setGapsDataSource] = useState(hasCachedGaps ? 'cache' : 'live')
  const [coverLetterState, setCoverLetterState] = useState({
    jobId: '',
    loading: false,
    error: '',
    draft: null,
  })
  const [tailoredSummaryState, setTailoredSummaryState] = useState({
    jobId: '',
    loading: false,
    error: '',
    summary: null,
  })
  const [outreachNoteState, setOutreachNoteState] = useState({
    jobId: '',
    loading: false,
    error: '',
    note: null,
  })
  const [resumeBulletsState, setResumeBulletsState] = useState({
    jobId: '',
    loading: false,
    error: '',
    bullets: null,
  })
  const [interviewBriefState, setInterviewBriefState] = useState({
    jobId: '',
    loading: false,
    error: '',
    brief: null,
  })
  const [talkingPointsState, setTalkingPointsState] = useState({
    jobId: '',
    loading: false,
    error: '',
    talkingPoints: null,
  })
  const jobsLengthRef = useRef(jobs.length)
  const hasStatsRef = useRef(Boolean(stats))
  const hasGapsRef = useRef(Boolean(gaps))

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

  useEffect(() => {
    jobsLengthRef.current = jobs.length
    hasStatsRef.current = Boolean(stats)
    hasGapsRef.current = Boolean(gaps)
  }, [jobs.length, stats, gaps])

  async function loadJobsData({ background = false } = {}) {
    if (!background || (!jobsLengthRef.current && !hasStatsRef.current)) {
      setLoading(true)
    }
    setError('')
    try {
      const jobsPayload = await fetchJobs(apiFilters)
      const items = Array.isArray(jobsPayload.items) ? jobsPayload.items : []
      const refreshedAt = new Date().toISOString()
      let nextSelectedJobId = selectedJobId

      setJobs(items)
      setLastLoadedAt(refreshedAt)
      setDataSource('live')

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
          setDataSource('live')
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
        setDataSource('cache')
        setError(`Showing last cached board snapshot. Live refresh failed: ${message}`)
      } else {
        setError(message)
      }
    } finally {
      setLoading(false)
    }
  }

  async function loadGapData({ background = false } = {}) {
    if (!background || !hasGapsRef.current) {
      setGapsLoading(true)
    }
    setGapsError('')
    try {
      const payload = await fetchJobGaps()
      const refreshedAt = new Date().toISOString()
      setGaps(payload)
      setGapsLoadedAt(refreshedAt)
      setGapsDataSource('live')
      persistGapSnapshot({ gaps: payload, lastLoadedAt: refreshedAt })
    } catch (loadError) {
      const message = loadError.message || 'Unable to load skill gaps.'
      if (gaps) {
        setGapsDataSource('cache')
        setGapsError(`Showing last cached learning radar. Live refresh failed: ${message}`)
      } else {
        setGapsError(message)
      }
    } finally {
      setGapsLoading(false)
    }
  }

  useEffect(() => {
    loadJobsData({ background: hasCachedJobs })
  }, [apiFilters, selectedJobId, jobs.length, stats])

  useEffect(() => {
    if (loadGaps) {
      loadGapData({ background: hasCachedGaps })
    }
  }, [loadGaps])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined
    }

    const intervalId = window.setInterval(() => {
      if (!document.hidden) {
        loadJobsData({ background: true })
      }
    }, JOBS_REFRESH_INTERVAL_MS)

    function handleForegroundRefresh() {
      loadJobsData({ background: true })
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
  }, [apiFilters])

  useEffect(() => {
    if (typeof window === 'undefined' || !error) {
      return undefined
    }
    const retryId = window.setTimeout(() => {
      loadJobsData({ background: true })
    }, JOBS_RETRY_INTERVAL_MS)
    return () => window.clearTimeout(retryId)
  }, [error, apiFilters, selectedJobId, jobs.length, stats])

  useEffect(() => {
    if (typeof window === 'undefined' || !loadGaps) {
      return undefined
    }

    const intervalId = window.setInterval(() => {
      if (!document.hidden) {
        loadGapData({ background: true })
      }
    }, GAPS_REFRESH_INTERVAL_MS)

    function handleForegroundGapRefresh() {
      loadGapData({ background: true })
    }

    function handleVisibilityChange() {
      if (!document.hidden) {
        handleForegroundGapRefresh()
      }
    }

    window.addEventListener('online', handleForegroundGapRefresh)
    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      window.clearInterval(intervalId)
      window.removeEventListener('online', handleForegroundGapRefresh)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [loadGaps, gaps])

  useEffect(() => {
    if (typeof window === 'undefined' || !loadGaps || !gapsError) {
      return undefined
    }
    const retryId = window.setTimeout(() => {
      loadGapData({ background: true })
    }, GAPS_RETRY_INTERVAL_MS)
    return () => window.clearTimeout(retryId)
  }, [gapsError, loadGaps, gaps])

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
      await loadJobsData({ background: true })
    } catch (draftError) {
      setCoverLetterState({
        jobId,
        loading: false,
        error: draftError.message || 'Draft generation failed.',
        draft: null,
      })
    }
  }

  async function generateTailoredSummary(jobId) {
    setTailoredSummaryState({ jobId, loading: true, error: '', summary: null })
    try {
      const payload = await createTailoredSummary({ job_id: jobId, save_to_vault: false })
      setTailoredSummaryState({ jobId, loading: false, error: '', summary: payload })
      await loadJobsData({ background: true })
    } catch (summaryError) {
      setTailoredSummaryState({
        jobId,
        loading: false,
        error: summaryError.message || 'Tailored summary generation failed.',
        summary: null,
      })
    }
  }

  async function generateResumeBullets(jobId) {
    setResumeBulletsState({ jobId, loading: true, error: '', bullets: null })
    try {
      const payload = await createResumeBullets({ job_id: jobId, save_to_vault: false })
      setResumeBulletsState({ jobId, loading: false, error: '', bullets: payload })
      await loadJobsData({ background: true })
    } catch (bulletsError) {
      setResumeBulletsState({
        jobId,
        loading: false,
        error: bulletsError.message || 'Resume bullet generation failed.',
        bullets: null,
      })
    }
  }

  async function generateOutreachNote(jobId) {
    setOutreachNoteState({ jobId, loading: true, error: '', note: null })
    try {
      const payload = await createOutreachNote({ job_id: jobId, save_to_vault: false })
      setOutreachNoteState({ jobId, loading: false, error: '', note: payload })
      await loadJobsData({ background: true })
    } catch (noteError) {
      setOutreachNoteState({
        jobId,
        loading: false,
        error: noteError.message || 'Outreach note generation failed.',
        note: null,
      })
    }
  }

  async function generateInterviewBrief(jobId) {
    setInterviewBriefState({ jobId, loading: true, error: '', brief: null })
    try {
      const payload = await createInterviewBrief({ job_id: jobId, save_to_vault: false })
      setInterviewBriefState({ jobId, loading: false, error: '', brief: payload })
      await loadJobsData({ background: true })
    } catch (briefError) {
      setInterviewBriefState({
        jobId,
        loading: false,
        error: briefError.message || 'Interview brief generation failed.',
        brief: null,
      })
    }
  }

  async function generateTalkingPoints(jobId) {
    setTalkingPointsState({ jobId, loading: true, error: '', talkingPoints: null })
    try {
      const payload = await createTalkingPoints({ job_id: jobId, save_to_vault: false })
      setTalkingPointsState({ jobId, loading: false, error: '', talkingPoints: payload })
      await loadJobsData({ background: true })
    } catch (pointsError) {
      setTalkingPointsState({
        jobId,
        loading: false,
        error: pointsError.message || 'Talking points generation failed.',
        talkingPoints: null,
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
    dataSource,
    gapsLoading,
    gapsError,
    gapsLoadedAt,
    gapsDataSource,
    selectedJobId,
    selectedJob,
    detailLoading,
    actionJobId,
    coverLetterState,
    tailoredSummaryState,
    outreachNoteState,
    resumeBulletsState,
    interviewBriefState,
    talkingPointsState,
    setSelectedJobId: selectJob,
    setFilter: updateFilter,
    refresh,
    loadGapData,
    markApplied: (jobId) => mutateJob(jobId, { applied: true }),
    dismissJob: (jobId) => mutateJob(jobId, { dismissed: true }),
    saveNotes: (jobId, notes) => mutateJob(jobId, { notes }),
    updateWorkflow: (jobId, workflow) => mutateJob(jobId, { workflow }),
    reevaluateJob,
    generateDraft,
    generateTailoredSummary,
    generateResumeBullets,
    generateOutreachNote,
    generateInterviewBrief,
    generateTalkingPoints,
  }
}
