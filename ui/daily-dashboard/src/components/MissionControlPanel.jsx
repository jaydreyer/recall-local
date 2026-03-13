import { useEffect, useMemo, useState } from 'react'

import JobDetail from './JobDetail'
import { summarizeAngle } from '../utils/jobSummary'

const CAPTURE_STORAGE_KEY = 'daily-dashboard-captures-v1'
const CAPTURE_TYPES = ['Idea', 'Reminder', 'Errand', 'Follow-up']

const STATUS_META = {
  active: { label: 'Active', className: 'active' },
  queued: { label: 'Queued', className: 'queued' },
  done: { label: 'Complete', className: 'done' },
}

function compactTime(value) {
  if (!value) {
    return 'Now'
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  const diffMinutes = Math.max(1, Math.round((Date.now() - parsed.getTime()) / 60000))
  if (diffMinutes < 60) {
    return `${String(diffMinutes).padStart(2, '0')}m`
  }
  const diffHours = Math.round(diffMinutes / 60)
  if (diffHours < 24) {
    return `${String(diffHours).padStart(2, '0')}h`
  }
  return `${String(Math.round(diffHours / 24)).padStart(2, '0')}d`
}

function loadStoredCaptures() {
  if (typeof window === 'undefined') {
    return []
  }
  try {
    const parsed = JSON.parse(window.localStorage.getItem(CAPTURE_STORAGE_KEY) || '[]')
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function persistCaptures(captures) {
  if (typeof window === 'undefined') {
    return
  }
  window.localStorage.setItem(CAPTURE_STORAGE_KEY, JSON.stringify(captures))
}

function badgeStatus(job, index) {
  if (job.applied) {
    return STATUS_META.done
  }
  if (job.dismissed) {
    return STATUS_META.queued
  }
  return index === 0 ? STATUS_META.active : STATUS_META.queued
}

function captureTypeForIndex(index) {
  return ['Follow-up', 'Idea', 'Reminder'][index] || 'Idea'
}

function buildDerivedCaptures(jobs) {
  return jobs.slice(0, 3).map((job, index) => ({
    id: `job-${job.jobId}`,
    type: captureTypeForIndex(index),
    text: summarizeAngle(job, { maxLength: 110 }) || `Review ${job.company} · ${job.title} before outreach.`,
    time: compactTime(job.evaluated_at || job.discovered_at),
    jobId: job.jobId,
  }))
}

function buildMemoryHighlights(jobs) {
  return jobs.slice(0, 4).map((job) => ({
    id: `memory-${job.jobId}`,
    time: compactTime(job.evaluated_at || job.discovered_at),
    text: `${job.company} · ${job.title} scored ${job.fit_score ?? 'n/a'}`,
    jobId: job.jobId,
  }))
}

function buildAutomationItems(jobs) {
  return jobs.slice(0, 3).map((job, index) => ({
    id: `automation-${job.jobId}`,
    title: job.title,
    desc: summarizeAngle(job, { maxLength: 110 }),
    owner: job.company,
    status: badgeStatus(job, index),
    jobId: job.jobId,
  }))
}

function recommendationLead(job) {
  const skills = Array.isArray(job.matching_skills) ? job.matching_skills : []
  if (skills.length > 0) {
    const first = skills[0]
    return typeof first === 'string' ? first : first.skill || first.name || 'Strong fit'
  }
  return 'Strong fit'
}

function FocusTaskRow({ job, index, onOpenJob }) {
  const status = badgeStatus(job, index)

  return (
    <button type="button" className="focus-task-row" onClick={() => onOpenJob(job.jobId)}>
      <div className="focus-task-copy">
        <p className="focus-task-title">{job.title}</p>
        <span className="focus-task-owner">Assigned to Arthur</span>
      </div>
      <span className={`lux-badge ${status.className}`}>
        <span className="lux-dot" />
        {status.label}
      </span>
    </button>
  )
}

function EmptyState({ children }) {
  return <p className="section-message mission-empty">{children}</p>
}

function CaptureRow({ capture, onOpenJob }) {
  return (
    <button type="button" className="capture-row" onClick={() => capture.jobId && onOpenJob(capture.jobId)}>
      <div className={`capture-accent ${capture.type.toLowerCase().replace(/[^a-z]+/g, '-')}`} />
      <div className="capture-copy">
        <div className="capture-meta-row">
          <span className={`capture-type ${capture.type.toLowerCase().replace(/[^a-z]+/g, '-')}`}>{capture.type}</span>
          <span className="meta-text">{capture.time}</span>
        </div>
        <p>{capture.text}</p>
      </div>
    </button>
  )
}

function MemoryRow({ item, onOpenJob }) {
  return (
    <button type="button" className="memory-row" onClick={() => onOpenJob(item.jobId)}>
      <span className="meta-text">{item.time}</span>
      <p>{item.text}</p>
    </button>
  )
}

function AutomationRow({ item, onOpenJob }) {
  return (
    <button type="button" className="automation-row" onClick={() => onOpenJob(item.jobId)}>
      <div className="automation-copy">
        <div className="automation-topline">
          <span className="automation-title">{item.title}</span>
          <span className={`lux-badge ${item.status.className}`}>
            <span className="lux-dot" />
            {item.status.label}
          </span>
        </div>
        <p className="automation-desc">{item.desc}</p>
        <span className="meta-text">{item.owner}</span>
      </div>
    </button>
  )
}

export default function MissionControlPanel({
  now,
  jobsState,
  settings,
  onOpenSettings,
  onOpenCompany,
}) {
  const [captureText, setCaptureText] = useState('')
  const [selectedCaptureType, setSelectedCaptureType] = useState('Idea')
  const [storedCaptures, setStoredCaptures] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [detailOpen, setDetailOpen] = useState(false)

  const jobs = Array.isArray(jobsState.jobs) ? jobsState.jobs : []
  const stats = jobsState.stats || {}
  const selectedJob = jobsState.selectedJob

  useEffect(() => {
    setStoredCaptures(loadStoredCaptures())
  }, [])

  const focusJobs = useMemo(() => jobs.slice(0, 2), [jobs])
  const derivedCaptures = useMemo(() => buildDerivedCaptures(jobs), [jobs])
  const memoryHighlights = useMemo(() => buildMemoryHighlights(jobs), [jobs])
  const automationItems = useMemo(() => buildAutomationItems(jobs), [jobs])

  const captures = useMemo(() => {
    const manual = storedCaptures.slice(0, 3)
    if (manual.length >= 3) {
      return manual
    }
    return [...manual, ...derivedCaptures].slice(0, 3)
  }, [derivedCaptures, storedCaptures])

  const searchResults = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    if (!query) {
      return []
    }
    return jobs
      .filter((job) => `${job.title} ${job.company} ${job.location || ''}`.toLowerCase().includes(query))
      .slice(0, 5)
  }, [jobs, searchQuery])

  function openJob(jobId) {
    jobsState.setSelectedJobId(jobId)
    setDetailOpen(true)
  }

  function saveCapture() {
    const text = captureText.trim()
    if (!text) {
      return
    }
    const next = [
      {
        id: `capture-${Date.now()}`,
        type: selectedCaptureType,
        text,
        time: new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' }).format(new Date()),
      },
      ...storedCaptures,
    ].slice(0, 12)
    setStoredCaptures(next)
    persistCaptures(next)
    setCaptureText('')
  }

  return (
    <section className="mission-control">
      <div className="mission-grid">
        <div className="mission-left">
          <section className="mission-section">
            <div className="mission-section-header">
              <h2 className="mission-section-title">Morning Brief</h2>
              <span className="meta-text">
                {now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
            <div className="section-rule mission-rule" />

            <div className="mission-subsection">
              <span className="mission-subtitle accent">Focus Tasks</span>
              <div className="mission-list">
                {focusJobs.length > 0 ? (
                  focusJobs.map((job, index) => (
                    <div key={job.jobId} className="mission-list-item">
                      <FocusTaskRow job={job} index={index} onOpenJob={openJob} />
                      {index < focusJobs.length - 1 && <div className="section-rule subtle" />}
                    </div>
                  ))
                ) : (
                  <EmptyState>No evaluated roles have landed yet.</EmptyState>
                )}
              </div>
            </div>

            <div className="mission-subsection">
              <span className="mission-subtitle muted">Fresh Captures</span>
              <div className="mission-list">
                {captures.length > 0 ? (
                  captures.map((capture, index) => (
                    <div key={capture.id} className="mission-list-item">
                      <CaptureRow capture={capture} onOpenJob={openJob} />
                      {index < captures.length - 1 && <div className="section-rule subtle" />}
                    </div>
                  ))
                ) : (
                  <EmptyState>Quick captures will appear here after the first save.</EmptyState>
                )}
              </div>
            </div>

            <div className="mission-subsection">
              <span className="mission-subtitle success">Memory Highlights</span>
              <div className="mission-list">
                {memoryHighlights.length > 0 ? (
                  memoryHighlights.map((item, index) => (
                    <div key={item.id} className="mission-list-item">
                      <MemoryRow item={item} onOpenJob={openJob} />
                      {index < memoryHighlights.length - 1 && <div className="section-rule subtle" />}
                    </div>
                  ))
                ) : (
                  <EmptyState>Memory highlights will populate once jobs are evaluated.</EmptyState>
                )}
              </div>
            </div>

            <div className="mission-subsection memory-explorer-shell">
              <div className="mission-section-header">
                <h2 className="mission-section-title">Memory Explorer</h2>
                <span className="meta-text">{stats.total_jobs || jobs.length} roles</span>
              </div>
              <div className="section-rule mission-rule" />
              <input
                type="text"
                className="memory-search-input"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Search memories..."
              />
              {searchResults.length > 0 && (
                <div className="memory-search-results">
                  {searchResults.map((job) => (
                    <button
                      key={job.jobId}
                      type="button"
                      className="memory-search-result"
                      onClick={() => openJob(job.jobId)}
                    >
                      <span>{job.title}</span>
                      <span className="meta-text">{job.company}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </section>
        </div>

        <aside className="mission-right">
          <section className="mission-section sidebar-section">
            <div className="mission-section-header">
              <h2 className="mission-section-title">Quick Capture</h2>
              <button type="button" className="meta-link" onClick={onOpenSettings}>
                {settings?.evaluation_model || 'local'} · {settings?.local_model || 'llama3.2:3b'}
              </button>
            </div>
            <div className="section-rule mission-rule" />
            <textarea
              className="quick-capture-input"
              value={captureText}
              onChange={(event) => setCaptureText(event.target.value)}
              placeholder="Jay mentioned a recruiter at Company X..."
            />
            <div className="capture-type-row">
              {CAPTURE_TYPES.map((type) => (
                <button
                  key={type}
                  type="button"
                  className={selectedCaptureType === type ? 'capture-type-button active' : 'capture-type-button'}
                  onClick={() => setSelectedCaptureType(type)}
                >
                  {type}
                </button>
              ))}
            </div>
            <button type="button" className="mission-primary-button" onClick={saveCapture}>
              Save to Mission Control
            </button>
          </section>

          <section className="mission-section sidebar-section">
            <div className="mission-section-header">
              <h2 className="mission-section-title">Automation Board</h2>
              <span className="meta-text">{automationItems.length} tracked</span>
            </div>
            <div className="section-rule mission-rule" />
            <div className="mission-list">
              {automationItems.length > 0 ? (
                automationItems.map((item, index) => (
                  <div key={item.id} className="mission-list-item">
                    <AutomationRow item={item} onOpenJob={openJob} />
                    {index < automationItems.length - 1 && <div className="section-rule subtle" />}
                  </div>
                ))
              ) : (
                <EmptyState>Automation tasks will appear after discovery and evaluation runs complete.</EmptyState>
              )}
            </div>
          </section>

          <section className="mission-section sidebar-section">
            <div className="mission-section-header">
              <h2 className="mission-section-title">Calendar Radar</h2>
              <span className="meta-text">Next 48h</span>
            </div>
            <div className="section-rule mission-rule" />
            <div className="calendar-placeholder">
              <div className="calendar-placeholder-icon">◎</div>
              <p>Nothing scheduled</p>
              <span>Events will appear here once OAuth tokens are connected.</span>
            </div>
          </section>
        </aside>
      </div>

      {detailOpen && selectedJob && (
        <div className="detail-modal-overlay" role="dialog" aria-modal="true">
          <div className="detail-modal">
            <div className="detail-modal-header">
              <div>
                <p className="section-label">Role inspector</p>
                <h2 className="section-title">{selectedJob.title}</h2>
                <button
                  type="button"
                  className="meta-link"
                  onClick={() => onOpenCompany(selectedJob.company_id || selectedJob.company_normalized)}
                >
                  {selectedJob.company}
                </button>
              </div>
              <button type="button" className="ghost-button" onClick={() => setDetailOpen(false)}>
                Close
              </button>
            </div>
            <div className="section-rule" />
            <div className="detail-modal-summary">
              <div className="detail-summary-item">
                <span className="mini-label">Score</span>
                <strong className="mini-value">{selectedJob.fit_score ?? 0}</strong>
              </div>
              <div className="detail-summary-item">
                <span className="mini-label">Top match</span>
                <strong className="detail-summary-copy">{recommendationLead(selectedJob)}</strong>
              </div>
              <div className="detail-summary-item">
                <span className="mini-label">Model</span>
                <strong className="detail-summary-copy">
                  {settings?.evaluation_model || 'local'} · {settings?.local_model || 'llama3.2:3b'}
                </strong>
              </div>
            </div>
            <div className="section-rule" />
            <JobDetail
              job={selectedJob}
              busy={jobsState.actionJobId === selectedJob.jobId}
              onMarkApplied={jobsState.markApplied}
              onDismiss={jobsState.dismissJob}
              onSaveNotes={jobsState.saveNotes}
              onGenerateDraft={jobsState.generateDraft}
              onReevaluate={jobsState.reevaluateJob}
              coverLetterState={jobsState.coverLetterState}
            />
          </div>
        </div>
      )}
    </section>
  )
}
