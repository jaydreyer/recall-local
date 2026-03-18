import { useEffect, useMemo, useState } from 'react'

import CompanyLogo from './CompanyLogo'
import JobDetail from './JobDetail'
import StateNotice from './StateNotice'
import { displayCompanyName } from '../utils/displayText'
import { buildWorkflowTimeline, deriveWorkflow } from '../utils/workflowDemo'

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

function scoreLabel(job) {
  return Number(job?.fit_score ?? -1) >= 0 ? String(job.fit_score) : 'NEW'
}

function toneForScore(score) {
  if ((score || 0) >= 85) {
    return 'high'
  }
  if ((score || 0) >= 70) {
    return 'medium'
  }
  return 'low'
}

function opsLane(job) {
  const workflow = deriveWorkflow(job)
  if (workflow.state === 'applied') {
    return 'follow_up'
  }
  if (workflow.state === 'target') {
    return 'focus'
  }
  if (workflow.state === 'new') {
    return 'review'
  }
  return 'monitor'
}

const LANE_LABELS = {
  focus: 'Focus queue',
  review: 'Needs review',
  follow_up: 'Follow-up',
  monitor: 'Monitor',
}

function firstAvailableLane(laneCounts) {
  if (laneCounts.focus > 0) {
    return 'focus'
  }
  if (laneCounts.review > 0) {
    return 'review'
  }
  if (laneCounts.follow_up > 0) {
    return 'follow_up'
  }
  return 'monitor'
}

function WorkflowRail({ job, coverLetterState }) {
  const workflow = deriveWorkflow(job, coverLetterState)
  const timeline = buildWorkflowTimeline(job, coverLetterState)

  return (
    <div className="ops-rail-stack">
      <section className="ops-rail-card">
        <div className="panel-heading compact">
          <div>
            <p className="section-label">Workflow state</p>
            <h3 className="card-title">What should happen next</h3>
          </div>
        </div>
        <div className="section-rule" />
        <div className="ops-status-stack">
          <div className="ops-kv">
            <span className="mini-label">State</span>
            <strong>{workflow.stateLabel}</strong>
          </div>
          <div className="ops-kv">
            <span className="mini-label">Next action</span>
            <strong>{workflow.nextActionLabel}</strong>
          </div>
          <div className="ops-kv">
            <span className="mini-label">Packet status</span>
            <strong>{workflow.packetLabel}</strong>
          </div>
          <div className="ops-kv">
            <span className="mini-label">Approval</span>
            <strong>{workflow.approvalLabel}</strong>
          </div>
        </div>
      </section>

      <section className="ops-rail-card">
        <div className="panel-heading compact">
          <div>
            <p className="section-label">Blockers</p>
            <h3 className="card-title">What is holding this up</h3>
          </div>
        </div>
        <div className="section-rule" />
        <div className={`workflow-callout ${workflow.blockerTone}`}>
          <p className="section-label">Primary blocker</p>
          <strong>{workflow.blocker}</strong>
          <p className="body-copy">This is a demo-time workflow signal derived from the current role state and fit data.</p>
        </div>
      </section>

      <section className="ops-rail-card">
        <div className="panel-heading compact">
          <div>
            <p className="section-label">Timeline</p>
            <h3 className="card-title">Recent activity</h3>
          </div>
        </div>
        <div className="section-rule" />
        <div className="workflow-timeline">
          {timeline.map((event) => (
            <div key={`${event.type}-${event.dateLabel}`} className="timeline-row">
              <span className="timeline-dot" aria-hidden="true" />
              <div>
                <strong>{event.label}</strong>
                <p className="meta-text">{event.dateLabel}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

export default function OpsWorkspace({ jobsState, onBackToOverview }) {
  const [lane, setLane] = useState('focus')
  const jobs = Array.isArray(jobsState.jobs) ? jobsState.jobs : []
  const laneCounts = useMemo(
    () => ({
      focus: jobs.filter((job) => opsLane(job) === 'focus').length,
      review: jobs.filter((job) => opsLane(job) === 'review').length,
      follow_up: jobs.filter((job) => opsLane(job) === 'follow_up').length,
      monitor: jobs.filter((job) => opsLane(job) === 'monitor').length,
    }),
    [jobs]
  )
  const filteredJobs = useMemo(() => jobs.filter((job) => opsLane(job) === lane).slice(0, 30), [jobs, lane])
  const selectedJob = jobsState.selectedJob || filteredJobs[0] || jobs[0] || null
  const selectedLane = selectedJob ? opsLane(selectedJob) : firstAvailableLane(laneCounts)
  const workflow = deriveWorkflow(selectedJob, jobsState.coverLetterState)

  useEffect(() => {
    if (!jobs.length) {
      return
    }

    if (selectedJob && selectedLane !== lane) {
      setLane(selectedLane)
      return
    }

    if (!selectedJob && laneCounts[lane] === 0) {
      setLane(firstAvailableLane(laneCounts))
    }
  }, [jobs.length, lane, laneCounts, selectedJob, selectedLane])

  return (
    <section className="ops-workspace reveal reveal-delay-3">
      <div className="ops-workspace-header">
        <div>
          <div className="eyebrow-row compact">
            <span className="status-dot" />
            <p className="kicker">Application Ops Copilot</p>
          </div>
          <h2 className="page-title ops-title">Move strong roles through the pipeline</h2>
          <p className="page-subtitle ops-subtitle">
            A desktop-first control room for triage, tailoring, approvals, and follow-through across your best opportunities.
          </p>
        </div>
        <button type="button" className="ghost-button" onClick={onBackToOverview}>
          Back to overview
        </button>
      </div>

      <div className="ops-workspace-grid">
        <aside className="ops-queue-panel">
          <div className="panel-heading compact">
            <div>
              <p className="section-label">Queue</p>
              <h3 className="card-title">Working lanes</h3>
            </div>
          </div>
          <div className="section-rule" />
          <div className="ops-lane-list" aria-label="Ops lanes">
            {Object.entries(LANE_LABELS).map(([key, label]) => (
              <button
                key={key}
                type="button"
                className={lane === key ? 'lane-button active' : 'lane-button'}
                onClick={() => setLane(key)}
              >
                <span>{label}</span>
                <strong>{laneCounts[key]}</strong>
              </button>
            ))}
          </div>
          <div className="ops-queue-list">
            {filteredJobs.map((job) => {
              const itemWorkflow = deriveWorkflow(job, jobsState.coverLetterState)
              return (
                <button
                  key={job.jobId}
                  type="button"
                  className={selectedJob?.jobId === job.jobId ? 'queue-card selected' : 'queue-card'}
                  onClick={() => jobsState.setSelectedJobId(job.jobId)}
                >
                  <div className="queue-card-topline">
                    <div className="queue-card-brand">
                      <CompanyLogo company={{ company_name: displayCompanyName(job.company), company_id: job.company_id || job.company_normalized }} className="company-logo small" />
                      <div>
                        <p className="queue-company">{displayCompanyName(job.company)}</p>
                        <p className="queue-title">{job.title}</p>
                      </div>
                    </div>
                    <span className={`queue-score ${toneForScore(job.fit_score || 0)}`}>{scoreLabel(job)}</span>
                  </div>
                  <div className="queue-meta-row">
                    <span>{itemWorkflow.stateLabel}</span>
                    <span>{itemWorkflow.nextActionLabel}</span>
                    <span>{compactRelativeTime(job.evaluated_at || job.discovered_at || job.date_posted)}</span>
                  </div>
                </button>
              )
            })}
            {!jobsState.loading && filteredJobs.length === 0 && (
              <StateNotice compact title="No roles in this lane yet" body="Switch lanes or refresh the board to pull in a fresh working set." />
            )}
          </div>
        </aside>

        <main className="ops-center-panel">
          {!selectedJob && (
            <StateNotice
              title="No role selected yet"
              body="Refresh the board or pick a lane with visible roles to start the demo flow."
              actionLabel="Refresh data"
              onAction={jobsState.refresh}
            />
          )}

          {selectedJob && (
            <>
              <section className="ops-hero-card">
                <div className="spotlight-brand-row">
                  <div className="spotlight-brand">
                    <CompanyLogo company={{ company_name: displayCompanyName(selectedJob.company), company_id: selectedJob.company_id || selectedJob.company_normalized }} className="company-logo large" />
                    <div>
                      <p className="queue-company">{displayCompanyName(selectedJob.company)}</p>
                      <h3 className="spotlight-title">{selectedJob.title}</h3>
                      <div className="spotlight-meta-row">
                        <span>{selectedJob.location || 'Unknown location'}</span>
                        <span>{workflow.stateLabel}</span>
                        <span>{workflow.priorityLabel}</span>
                        <span>{compactRelativeTime(selectedJob.evaluated_at || selectedJob.discovered_at || selectedJob.date_posted)}</span>
                      </div>
                    </div>
                  </div>

                  <div className="spotlight-score-block">
                    <span className="mini-label">Fit score</span>
                    <strong className={`spotlight-score ${toneForScore(selectedJob.fit_score || 0)}`}>{scoreLabel(selectedJob)}</strong>
                  </div>
                </div>

                <div className="ops-hero-grid">
                  <div className="spotlight-insight">
                    <span className="mini-label">Next best action</span>
                    <p>{workflow.nextActionLabel}</p>
                  </div>
                  <div className="spotlight-insight">
                    <span className="mini-label">Primary blocker</span>
                    <p>{workflow.blocker}</p>
                  </div>
                  <div className="spotlight-insight">
                    <span className="mini-label">Packet readiness</span>
                    <p>{workflow.packetLabel}</p>
                  </div>
                </div>
              </section>

              <section className="ops-detail-card">
                <div className="panel-heading compact">
                  <div>
                    <p className="section-label">Role workspace</p>
                    <h3 className="card-title">Application packet and dossier</h3>
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
              </section>
            </>
          )}
        </main>

        <aside className="ops-rail-panel">
          {selectedJob ? (
            <WorkflowRail job={selectedJob} coverLetterState={jobsState.coverLetterState} />
          ) : (
            <StateNotice compact title="Workflow rail waiting on a role" body="Select a role to see blockers, packet status, and timeline." />
          )}
        </aside>
      </div>
    </section>
  )
}
