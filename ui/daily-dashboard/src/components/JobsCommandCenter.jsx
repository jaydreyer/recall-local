import { useDeferredValue, useEffect, useMemo, useState } from 'react'

import CompanyLogo from './CompanyLogo'
import JobDetail from './JobDetail'
import StateNotice from './StateNotice'
import { displayCompanyName, displaySourceLabel } from '../utils/displayText'
import { summarizeAngle, summarizeTopGap, summarizeTopMatch } from '../utils/jobSummary'
import { deriveWorkflow, preferredDemoJob } from '../utils/workflowDemo'

const LANE_COPY = {
  focus: 'Best-fit evaluated roles ready for outreach or drafting.',
  fresh: 'New arrivals waiting for first-pass evaluation.',
  applied: 'Active applications already moved forward.',
  archive: 'Dismissed, expired, or errored roles for reference.',
}

const SOURCE_OPTIONS = [
  { value: '', label: 'All sources' },
  { value: 'career_page', label: 'Career pages' },
  { value: 'jobspy', label: 'JobSpy' },
  { value: 'chrome_extension', label: 'Chrome extension' },
]

const TIER_OPTIONS = [
  { value: '', label: 'All tiers' },
  { value: '1', label: 'Tier 1' },
  { value: '2', label: 'Tier 2' },
  { value: '3', label: 'Tier 3' },
]

const SCORE_OPTIONS = [
  { value: 'all', label: 'All scores' },
  { value: '75-plus', label: '75+' },
  { value: '50-74', label: '50-74' },
  { value: 'under-50', label: 'Under 50' },
]

const FRESHNESS_OPTIONS = [
  { value: '', label: 'All ages' },
  { value: 'current', label: '0-7 days' },
  { value: 'recent', label: '8-30 days' },
  { value: 'aging', label: '31-59 days' },
  { value: 'stale', label: '60+ days' },
  { value: 'unknown', label: 'Unknown age' },
]

function effectiveStatus(job) {
  if (job.applied || job.status === 'applied') {
    return 'applied'
  }
  if (job.dismissed || job.status === 'dismissed' || job.status === 'expired') {
    return 'dismissed'
  }
  return String(job.status || 'new').toLowerCase()
}

function laneForJob(job) {
  const status = effectiveStatus(job)
  if (status === 'applied') {
    return 'applied'
  }
  if (status === 'dismissed' || status === 'expired' || status === 'error') {
    return 'archive'
  }
  if (status === 'new') {
    return 'fresh'
  }
  if (job.freshness?.status === 'stale') {
    return 'archive'
  }
  if ((job.fit_score || 0) >= 75) {
    return 'focus'
  }
  return 'archive'
}

function scoreTone(score) {
  if ((score || 0) >= 85) {
    return 'high'
  }
  if ((score || 0) >= 70) {
    return 'medium'
  }
  return 'low'
}

function tierValue(job) {
  const tier = Number(job?.company_tier ?? 0)
  return [1, 2, 3].includes(tier) ? tier : 0
}

function tierLabel(job) {
  const tier = tierValue(job)
  return tier ? `T${tier}` : 'Untracked'
}

function compactRelativeTime(value) {
  if (!value) {
    return 'Just now'
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  const diffHours = Math.max(1, Math.round((Date.now() - parsed.getTime()) / 3600000))
  if (diffHours < 24) {
    return `${diffHours}h ago`
  }
  return `${Math.round(diffHours / 24)}d ago`
}

function freshnessClass(job) {
  const status = job.freshness?.status || 'unknown'
  if (status === 'current' || status === 'recent') {
    return 'freshness-badge current'
  }
  if (status === 'aging') {
    return 'freshness-badge aging'
  }
  if (status === 'stale') {
    return 'freshness-badge stale'
  }
  return 'freshness-badge'
}

function freshnessLabel(job) {
  return job.freshness?.label || 'Posting date unknown'
}

function formatRefreshLabel(value) {
  if (!value) {
    return 'Waiting for first sync'
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return 'Recently refreshed'
  }
  return parsed.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  })
}

function scoreLabel(job) {
  if ((job.fit_score ?? -1) >= 0) {
    return String(job.fit_score)
  }
  if (effectiveStatus(job) === 'error') {
    return 'ERR'
  }
  return 'NEW'
}

function queueHeadline(job) {
  if (effectiveStatus(job) === 'new') {
    return 'Awaiting evaluation'
  }
  if (effectiveStatus(job) === 'error') {
    return job.score_rationale || 'Last evaluation errored.'
  }
  return summarizeAngle(job)
}

function actionLabelForJob(job) {
  if (job?.freshness?.status === 'current' && (job?.fit_score ?? -1) >= 75) {
    return 'Draft cover letter'
  }
  if ((job?.fit_score ?? -1) < 0 || effectiveStatus(job) === 'new') {
    return 'Evaluate fit'
  }
  return 'Review role'
}

function fallbackDailyActions(jobs) {
  return jobs
    .filter((job) => laneForJob(job) === 'focus' || laneForJob(job) === 'fresh')
    .slice(0, 3)
    .map((job) => ({
      actionId: `fallback-${job.jobId}`,
      jobId: job.jobId,
      actionLabel: actionLabelForJob(job),
      title: job.title,
      company: job.company,
      fit_score: job.fit_score,
      freshness: job.freshness,
      relevance: job.relevance,
      rationale: queueHeadline(job),
    }))
}

function aggregateCompanies(jobs) {
  const grouped = new Map()
  jobs.forEach((job) => {
    const key = job.company_id || job.company_normalized || job.company
    if (!key) {
      return
    }
    const current = grouped.get(key) || {
      company_id: job.company_id || job.company_normalized || key,
      company_name: displayCompanyName(job.company),
      company_tier: tierValue(job),
      job_count: 0,
      high_fit: 0,
      best_score: -1,
    }
    current.job_count += 1
    current.best_score = Math.max(current.best_score, Number(job.fit_score ?? -1))
    if ((job.fit_score || 0) >= 75) {
      current.high_fit += 1
    }
    grouped.set(key, current)
  })

  return Array.from(grouped.values())
    .sort((left, right) => (right.high_fit - left.high_fit) || (right.best_score - left.best_score) || (right.job_count - left.job_count))
    .slice(0, 6)
}

function laneJobs(jobs, lane) {
  return jobs.filter((job) => laneForJob(job) === lane)
}

function LaneButton({ lane, label, count, active, onClick }) {
  return (
    <button type="button" className={active ? 'lane-button active' : 'lane-button'} onClick={() => onClick(lane)}>
      <span>{label}</span>
      <strong>{count}</strong>
    </button>
  )
}

function MetricSkeletonCard({ tone = '' }) {
  return (
    <div className={`operator-metric-card skeleton-card ${tone}`.trim()}>
      <span className="mini-label skeleton-line short" />
      <span className="operator-metric-value skeleton-line value" />
      <p className="skeleton-copy">
        <span className="skeleton-line medium" />
        <span className="skeleton-line long" />
      </p>
    </div>
  )
}

function QueueSkeletonCard() {
  return (
    <div className="queue-card skeleton-card" aria-hidden="true">
      <div className="queue-card-topline">
        <div className="queue-card-brand">
          <span className="company-logo small skeleton-line square" />
          <div className="skeleton-stack">
            <span className="skeleton-line short" />
            <span className="skeleton-line medium" />
          </div>
        </div>
        <span className="queue-score skeleton-line short" />
      </div>
      <div className="queue-meta-row">
        <span className="skeleton-line short" />
        <span className="skeleton-line short" />
        <span className="skeleton-line short" />
      </div>
      <div className="skeleton-stack">
        <span className="skeleton-line long" />
        <span className="skeleton-line medium" />
      </div>
    </div>
  )
}

function QueueCard({ job, selected, onSelect, onDismiss, dismissible }) {
  return (
    <article className={selected ? 'queue-card selected' : 'queue-card'}>
      {dismissible && (
        <button
          type="button"
          className="queue-dismiss-button"
          aria-label={`Dismiss ${job.title}`}
          title="Dismiss role"
          onClick={(event) => {
            event.stopPropagation()
            onDismiss(job.jobId)
          }}
        >
          X
        </button>
      )}
      <button type="button" className="queue-card-main" onClick={() => onSelect(job.jobId)}>
        <div className="queue-card-topline">
          <div className="queue-card-brand">
            <CompanyLogo company={{ company_name: displayCompanyName(job.company), company_id: job.company_id || job.company_normalized }} className="company-logo small" />
            <div>
              <p className="queue-company">{displayCompanyName(job.company)}</p>
              <p className="queue-title">{job.title}</p>
            </div>
          </div>
          <span className={`queue-score ${scoreTone(job.fit_score || 0)}`}>{scoreLabel(job)}</span>
        </div>

        <div className="queue-meta-row">
          <span>{job.location || 'Unknown location'}</span>
          <span>{compactRelativeTime(job.evaluated_at || job.discovered_at || job.date_posted)}</span>
          <span>{tierLabel(job)}</span>
        </div>

        <div className="freshness-row">
          <span className={freshnessClass(job)}>{freshnessLabel(job)}</span>
          {job.relevance?.targetLabel && <span className="freshness-badge target">{job.relevance.targetLabel}</span>}
        </div>

        <p className="queue-snippet">{queueHeadline(job)}</p>
        <div className="queue-tags">
          <span className="queue-tag">Match: {summarizeTopMatch(job, { maxLength: 72 })}</span>
          <span className="queue-tag">Gap: {summarizeTopGap(job, { maxLength: 72 })}</span>
        </div>
      </button>
    </article>
  )
}

function DailyActionCard({ action, index, onOpen, onOps }) {
  return (
    <article className="daily-action-card">
      <div className="daily-action-index">{index + 1}</div>
      <div className="daily-action-body">
        <div className="daily-action-topline">
          <span className="mini-label">{action.actionLabel || 'Review role'}</span>
          <span className={freshnessClass(action)}>{freshnessLabel(action)}</span>
        </div>
        <h3 className="daily-action-title">{action.title || 'Untitled role'}</h3>
        <p className="daily-action-meta">
          {displayCompanyName(action.company)} · Fit {action.fit_score ?? 'new'}
          {action.relevance?.targetLabel ? ` · ${action.relevance.targetLabel}` : ''}
        </p>
        <p className="daily-action-rationale">{action.rationale || 'Actionable role for today.'}</p>
        <div className="daily-action-controls">
          <button type="button" className="ghost-button compact" onClick={() => onOpen(action.jobId)}>
            Dossier
          </button>
          <button type="button" className="text-button accent" onClick={() => onOps(action.jobId)}>
            Ops
          </button>
        </div>
      </div>
    </article>
  )
}

function DetailDrawer({ open, job, jobsState, loading, onClose, onOpenOps }) {
  if (!open) {
    return null
  }

  const workflow = job ? deriveWorkflow(job, jobsState.coverLetterState) : null

  return (
    <div className="detail-drawer-shell" role="dialog" aria-modal="true" aria-label="Role dossier">
      <button type="button" className="detail-drawer-backdrop" aria-label="Close dossier" onClick={onClose} />
      <aside className="detail-drawer-panel">
        <div className="panel-heading compact">
          <div>
            <p className="section-label">Role dossier</p>
            <h3 className="card-title">{job ? job.title : 'Select a role'}</h3>
          </div>
          <button type="button" className="ghost-button detail-close-button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="section-rule" />
        {job && workflow && (
          <div className="detail-drawer-meta">
            <span className="meta-chip">{displayCompanyName(job.company)}</span>
            <span className="meta-chip">{workflow.stateLabel}</span>
            <span className="meta-chip">{workflow.nextActionLabel}</span>
            <button type="button" className="text-button accent" onClick={() => onOpenOps(job.jobId)}>
              Open in Ops
            </button>
          </div>
        )}
        {loading && <p className="section-message">Loading role detail...</p>}
        {!loading && job && (
          <JobDetail
            job={job}
            busy={jobsState.actionJobId === job.jobId}
            onMarkApplied={jobsState.markApplied}
            onDismiss={jobsState.dismissJob}
            onSaveNotes={jobsState.saveNotes}
            onGenerateDraft={jobsState.generateDraft}
            onGenerateTailoredSummary={jobsState.generateTailoredSummary}
            onGenerateResumeBullets={jobsState.generateResumeBullets}
            onGenerateOutreachNote={jobsState.generateOutreachNote}
            onGenerateInterviewBrief={jobsState.generateInterviewBrief}
            onGenerateTalkingPoints={jobsState.generateTalkingPoints}
            onReevaluate={jobsState.reevaluateJob}
            coverLetterState={jobsState.coverLetterState}
            tailoredSummaryState={jobsState.tailoredSummaryState}
            outreachNoteState={jobsState.outreachNoteState}
            resumeBulletsState={jobsState.resumeBulletsState}
            interviewBriefState={jobsState.interviewBriefState}
            talkingPointsState={jobsState.talkingPointsState}
          />
        )}
        {!loading && !job && <p className="section-message">Select a role to load its dossier.</p>}
      </aside>
    </div>
  )
}

export default function JobsCommandCenter({ jobsState, settings, onOpenSettings, onOpenCompany, onOpenOps }) {
  const [activeLane, setActiveLane] = useState('focus')
  const [search, setSearch] = useState('')
  const [detailOpen, setDetailOpen] = useState(false)
  const deferredSearch = useDeferredValue(search)
  const jobs = Array.isArray(jobsState.jobs) ? jobsState.jobs : []
  const query = deferredSearch.trim().toLowerCase()

  const laneCounts = useMemo(
    () => ({
      focus: laneJobs(jobs, 'focus').length,
      fresh: laneJobs(jobs, 'fresh').length,
      applied: laneJobs(jobs, 'applied').length,
      archive: laneJobs(jobs, 'archive').length,
    }),
    [jobs]
  )

  const visibleJobs = useMemo(() => laneJobs(jobs, activeLane).slice(0, 24), [activeLane, jobs])
  const dailyActions = useMemo(() => {
    const apiActions = Array.isArray(jobsState.dailyActions) ? jobsState.dailyActions : []
    return apiActions.length > 0 ? apiActions.slice(0, 3) : fallbackDailyActions(jobs)
  }, [jobs, jobsState.dailyActions])

  const selectedJob = jobsState.selectedJob
  const isInitialLoad = jobsState.loading && jobs.length === 0 && !jobsState.lastLoadedAt
  const isRefreshing = jobsState.loading && !isInitialLoad
  const selectedVisible = selectedJob && visibleJobs.some((job) => job.jobId === selectedJob.jobId)
  const demoJob = useMemo(() => preferredDemoJob(jobs), [jobs])
  const heroJob = selectedVisible ? selectedJob : demoJob || visibleJobs[0] || jobs[0] || null
  const heroWorkflow = heroJob ? deriveWorkflow(heroJob, jobsState.coverLetterState) : null

  const companyPulse = useMemo(() => aggregateCompanies(jobs), [jobs])
  const appliedCount = jobs.filter((job) => effectiveStatus(job) === 'applied').length
  const staleActiveCount = jobsState.stats?.freshness?.active_stale_jobs ?? jobs.filter((job) => job.freshness?.status === 'stale' && !['applied', 'dismissed', 'expired', 'error'].includes(effectiveStatus(job))).length
  const actionableCount = jobsState.stats?.freshness?.active_actionable_jobs ?? jobs.filter((job) => ['current', 'recent'].includes(job.freshness?.status)).length

  function openDossier(jobId) {
    jobsState.setSelectedJobId(jobId)
    setDetailOpen(true)
  }

  useEffect(() => {
    if (jobsState.filters.status !== 'all') {
      jobsState.setFilter('status', 'all')
    }
    if (jobsState.filters.scoreRange !== 'all') {
      jobsState.setFilter('scoreRange', 'all')
    }
  }, [])

  useEffect(() => {
    if (jobsState.filters.search !== query) {
      jobsState.setFilter('search', query)
    }
  }, [query, jobsState.filters.search])

  useEffect(() => {
    if (heroJob && jobsState.selectedJobId !== heroJob.jobId) {
      jobsState.setSelectedJobId(heroJob.jobId)
    }
  }, [heroJob, jobsState.selectedJobId])

  return (
    <section className="jobs-command">
      <div className="jobs-command-header">
        <div>
          <p className="section-label">Career operator deck</p>
          <h2 className="section-title large">Search, score, and move</h2>
          <p className="body-copy">
            Triage live openings, keep the best roles in view, and move from evaluation to notes or drafts without losing context.
          </p>
        </div>
        <div className="jobs-command-actions">
          <button type="button" className="ghost-button" onClick={onOpenSettings}>
            Model settings
          </button>
          <button type="button" className="text-button accent" onClick={jobsState.refresh} disabled={jobsState.loading}>
            {jobsState.loading ? 'Refreshing...' : 'Refresh data'}
          </button>
        </div>
      </div>

      <div className="section-rule" />

      <div className="section-status-row">
        <span className={isInitialLoad || isRefreshing ? 'status-chip loading' : jobsState.dataSource === 'cache' ? 'status-chip warning' : 'status-chip'}>
          <span className={isInitialLoad || isRefreshing ? 'status-dot pulse' : 'status-dot'} />
          {isInitialLoad ? 'Loading live jobs' : isRefreshing ? 'Refreshing live jobs' : jobsState.dataSource === 'cache' ? 'Cached board snapshot on screen' : 'Live board ready'}
        </span>
        <span className="meta-text">
          {jobsState.lastLoadedAt ? `Last refreshed ${formatRefreshLabel(jobsState.lastLoadedAt)}` : 'Waiting for first sync'}
        </span>
      </div>

      <div className="operator-metric-grid">
        {isInitialLoad ? (
          <>
            <MetricSkeletonCard tone="accent" />
            <MetricSkeletonCard />
            <MetricSkeletonCard />
            <MetricSkeletonCard tone="success" />
          </>
        ) : (
          <>
            <div className="operator-metric-card accent">
              <span className="mini-label">Focus queue</span>
              <strong className="operator-metric-value">{laneCounts.focus}</strong>
              <p>High-fit evaluated roles ready for outreach.</p>
            </div>
            <div className="operator-metric-card">
              <span className="mini-label">Actionable age</span>
              <strong className="operator-metric-value">{actionableCount}</strong>
              <p>Active postings from the last 30 days.</p>
            </div>
            <div className="operator-metric-card">
              <span className="mini-label">Stale active</span>
              <strong className="operator-metric-value">{staleActiveCount}</strong>
              <p>Active roles 60+ days old, kept visible but out of the top queue.</p>
            </div>
            <div className="operator-metric-card success">
              <span className="mini-label">Applied</span>
              <strong className="operator-metric-value">{appliedCount}</strong>
              <p>{settings?.evaluation_model || 'local'} model active · {settings?.local_model || 'llama3.2:3b'}</p>
            </div>
          </>
        )}
      </div>

      <div className="section-rule" />

      <section className="daily-actions-panel">
        <div className="panel-heading compact">
          <div>
            <p className="section-label">Today</p>
            <h3 className="card-title">Top 3 moves</h3>
          </div>
          <span className="meta-text">Ranked by fit, freshness, and packet readiness</span>
        </div>
        <div className="daily-actions-grid">
          {isInitialLoad
            ? Array.from({ length: 3 }, (_, index) => (
                <div key={`daily-action-skeleton-${index}`} className="daily-action-card skeleton-card" aria-hidden="true">
                  <span className="daily-action-index skeleton-line square" />
                  <div className="skeleton-stack">
                    <span className="skeleton-line short" />
                    <span className="skeleton-line long" />
                    <span className="skeleton-line medium" />
                  </div>
                </div>
              ))
            : dailyActions.map((action, index) => (
                <DailyActionCard
                  key={action.actionId || action.jobId}
                  action={action}
                  index={index}
                  onOpen={openDossier}
                  onOps={onOpenOps}
                />
              ))}
          {!isInitialLoad && dailyActions.length === 0 && (
            <StateNotice
              compact
              title="No daily moves are ready"
              body="Refresh the board or broaden filters once new evaluated target roles arrive."
              actionLabel="Refresh data"
              onAction={jobsState.refresh}
            />
          )}
        </div>
      </section>

      <div className="operator-toolbar">
        <label className="operator-search">
          <span className="filter-label">Search live roles</span>
          <input
            className="filter-input"
            type="text"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search all roles by title, company, location, gaps, or notes..."
          />
        </label>

        <div className="lane-row" aria-label="Queue lanes">
          <LaneButton lane="focus" label="Focus" count={laneCounts.focus} active={activeLane === 'focus'} onClick={setActiveLane} />
          <LaneButton lane="fresh" label="Fresh" count={laneCounts.fresh} active={activeLane === 'fresh'} onClick={setActiveLane} />
          <LaneButton lane="applied" label="Applied" count={laneCounts.applied} active={activeLane === 'applied'} onClick={setActiveLane} />
          <LaneButton lane="archive" label="Archive" count={laneCounts.archive} active={activeLane === 'archive'} onClick={setActiveLane} />
        </div>

        <div className="operator-filter-row">
          <label className="filter-field compact">
            <span className="filter-label">Score</span>
            <select className="filter-select" value={jobsState.filters.scoreRange} onChange={(event) => jobsState.setFilter('scoreRange', event.target.value)}>
              {SCORE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="filter-field compact">
            <span className="filter-label">Source</span>
            <select className="filter-select" value={jobsState.filters.source} onChange={(event) => jobsState.setFilter('source', event.target.value)}>
              {SOURCE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="filter-field compact">
            <span className="filter-label">Age</span>
            <select className="filter-select" value={jobsState.filters.freshness} onChange={(event) => jobsState.setFilter('freshness', event.target.value)}>
              {FRESHNESS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="filter-field compact">
            <span className="filter-label">Tier</span>
            <select className="filter-select" value={jobsState.filters.companyTier} onChange={(event) => jobsState.setFilter('companyTier', event.target.value)}>
              {TIER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="overview-stack">
        {isInitialLoad ? (
          <section className="spotlight-card skeleton-card">
            <div className="spotlight-brand-row">
              <div className="spotlight-brand">
                <span className="company-logo large skeleton-line square" />
                <div className="skeleton-stack">
                  <span className="skeleton-line short" />
                  <span className="skeleton-line long title" />
                  <span className="skeleton-line medium" />
                </div>
              </div>
              <div className="spotlight-score-block">
                <span className="mini-label">Fit score</span>
                <span className="spotlight-score skeleton-line value" />
              </div>
            </div>
            <div className="spotlight-insights">
              <div className="spotlight-insight skeleton-stack">
                <span className="mini-label">Top match</span>
                <span className="skeleton-line medium" />
                <span className="skeleton-line short" />
              </div>
              <div className="spotlight-insight skeleton-stack">
                <span className="mini-label">Biggest gap</span>
                <span className="skeleton-line medium" />
                <span className="skeleton-line short" />
              </div>
              <div className="spotlight-insight skeleton-stack">
                <span className="mini-label">Angle</span>
                <span className="skeleton-line long" />
                <span className="skeleton-line medium" />
              </div>
            </div>
          </section>
        ) : heroJob ? (
          <section className="spotlight-card">
            <div className="spotlight-brand-row">
              <div className="spotlight-brand">
                <CompanyLogo company={{ company_name: displayCompanyName(heroJob.company), company_id: heroJob.company_id || heroJob.company_normalized }} className="company-logo large" />
                <div>
                  <button
                    type="button"
                    className="meta-link"
                    onClick={() => onOpenCompany(heroJob.company_id || heroJob.company_normalized)}
                  >
                    {displayCompanyName(heroJob.company)}
                  </button>
                  <h3 className="spotlight-title">{heroJob.title}</h3>
                  <div className="spotlight-meta-row">
                    <span>{heroJob.location || 'Unknown location'}</span>
                    <span>{displaySourceLabel(heroJob.source)}</span>
                    <span>{heroWorkflow?.stateLabel || 'Queued'}</span>
                    <span>{freshnessLabel(heroJob)}</span>
                  </div>
                </div>
              </div>

              <div className="spotlight-score-block">
                <span className="mini-label">Fit score</span>
                <strong className={`spotlight-score ${scoreTone(heroJob.fit_score || 0)}`}>{scoreLabel(heroJob)}</strong>
              </div>
            </div>

            <div className="spotlight-insights">
              <div className="spotlight-insight">
                <span className="mini-label">Top match</span>
                <p>{summarizeTopMatch(heroJob, { maxLength: 112 })}</p>
              </div>
              <div className="spotlight-insight">
                <span className="mini-label">Biggest gap</span>
                <p>{summarizeTopGap(heroJob, { maxLength: 112 })}</p>
              </div>
              <div className="spotlight-insight">
                <span className="mini-label">Next best action</span>
                <p>{heroWorkflow?.nextActionLabel || queueHeadline(heroJob)}</p>
              </div>
            </div>

            {demoJob?.jobId === heroJob.jobId && (
              <div className="demo-note">
                <span className="mini-label">Demo-ready role</span>
                <p className="body-copy">This role has the clearest fit, rationale, and packet story for a live walkthrough.</p>
              </div>
            )}

            <div className="spotlight-actions">
              <button type="button" className="mission-primary-button inline" onClick={() => openDossier(heroJob.jobId)}>
                Open dossier
              </button>
              <button type="button" className="ghost-button" onClick={() => onOpenOps(heroJob.jobId)}>
                Open in Ops
              </button>
              <button
                type="button"
                className="ghost-button"
                onClick={() => jobsState.generateDraft(heroJob.jobId)}
                disabled={jobsState.actionJobId === heroJob.jobId || (heroJob.fit_score ?? -1) < 0}
              >
                Draft cover letter
              </button>
              {heroJob.url && (
                <a className="text-button accent" href={heroJob.url} target="_blank" rel="noreferrer">
                  Open posting
                </a>
              )}
            </div>
          </section>
        ) : (
          <section className="panel-section">
            <StateNotice
              title="No roles are on the board yet"
              body="Try refreshing the board. If this persists, the bridge may still be warming caches or the current filters may be too narrow."
              actionLabel="Refresh data"
              onAction={jobsState.refresh}
            />
          </section>
        )}

        <div className="operator-subgrid">
          <section className="queue-panel">
            <div className="panel-heading compact">
              <div>
                <p className="section-label">{activeLane} lane</p>
                <h3 className="card-title">{visibleJobs.length} visible roles</h3>
              </div>
              <span className="meta-text">{LANE_COPY[activeLane]}</span>
            </div>
            <div className="section-rule" />
            {jobsState.error && visibleJobs.length > 0 && (
              <StateNotice
                tone="warning"
                compact
                title="Working from the last good board snapshot"
                body={jobsState.error}
                actionLabel="Retry now"
                onAction={jobsState.refresh}
              />
            )}
            {isRefreshing && <p className="section-message">Refreshing jobs while keeping the current board in view…</p>}
            {isInitialLoad && <p className="section-message">Loading the first live set of roles from the bridge…</p>}
            {!jobsState.loading && visibleJobs.length === 0 && (
              <StateNotice
                compact
                title={jobs.length === 0 ? 'No roles loaded yet' : 'No roles matched this lane'}
                body={
                  jobs.length === 0
                    ? 'The board does not have any visible roles yet. Refresh to try the live bridge again.'
                    : 'Try another lane, clear the search box, or broaden the source and score filters.'
                }
                actionLabel={jobs.length === 0 ? 'Refresh data' : 'Show all scores'}
                onAction={jobs.length === 0 ? jobsState.refresh : () => jobsState.setFilter('scoreRange', 'all')}
              />
            )}
            <div className="queue-list">
              {isInitialLoad
                ? Array.from({ length: 4 }, (_, index) => <QueueSkeletonCard key={`queue-skeleton-${index}`} />)
                : visibleJobs.map((job) => (
                    <QueueCard
                      key={job.jobId}
                      job={job}
                      selected={heroJob?.jobId === job.jobId}
                      onSelect={openDossier}
                      onDismiss={jobsState.dismissJob}
                      dismissible={activeLane === 'focus'}
                    />
                  ))}
            </div>
          </section>

          <section className="company-pulse-panel">
            <div className="panel-heading compact">
              <div>
                <p className="section-label">Company pulse</p>
                <h3 className="card-title">Where the board is hottest</h3>
              </div>
            </div>
            <div className="section-rule" />
            <div className="company-pulse-list">
              {isInitialLoad
                ? Array.from({ length: 4 }, (_, index) => (
                    <div key={`pulse-skeleton-${index}`} className="company-pulse-card skeleton-card" aria-hidden="true">
                      <span className="company-logo small skeleton-line square" />
                      <div className="skeleton-stack">
                        <span className="skeleton-line short" />
                        <span className="skeleton-line medium" />
                      </div>
                    </div>
                  ))
                : companyPulse.map((company) => (
                    <button key={company.company_id} type="button" className="company-pulse-card" onClick={() => onOpenCompany(company.company_id)}>
                      <CompanyLogo company={company} className="company-logo small" />
                      <div>
                        <strong>{company.company_name}</strong>
                        <span>{company.job_count} roles · best {company.best_score > -1 ? company.best_score : 'n/a'}</span>
                      </div>
                    </button>
                  ))}
              {!isInitialLoad && companyPulse.length === 0 && (
                <StateNotice
                  compact
                  title="Company pulse is waiting on more roles"
                  body="This panel fills in once the current board has enough matching roles to surface company heat."
                />
              )}
            </div>
          </section>
        </div>
      </div>

      <DetailDrawer
        open={detailOpen}
        job={jobsState.selectedJob}
        jobsState={jobsState}
        loading={jobsState.detailLoading}
        onClose={() => setDetailOpen(false)}
        onOpenOps={(jobId) => {
          setDetailOpen(false)
          onOpenOps(jobId)
        }}
      />
    </section>
  )
}
