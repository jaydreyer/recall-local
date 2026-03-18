import { useEffect, useMemo, useState } from 'react'

import CompanyLogo from './CompanyLogo'
import JobDetail from './JobDetail'
import StateNotice from './StateNotice'
import { displayCompanyName } from '../utils/displayText'
import {
  buildWorkflowTimeline,
  defaultWorkflowState,
  deriveWorkflow,
  isFollowUpDue,
  PACKET_ARTIFACT_LABELS,
  preferredDemoJob,
  WORKFLOW_STAGE_LABELS,
} from '../utils/workflowDemo'

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
  return defaultWorkflowState(job).stage
}

const LANE_LABELS = {
  focus: 'Focus queue',
  review: 'Needs review',
  follow_up: 'Follow-up',
  monitor: 'Monitor',
  closed: 'Closed',
}

const QUEUE_FILTERS = {
  all: 'All roles',
  needs_approval: 'Needs approval',
  packet_in_progress: 'Packet in progress',
  ready_to_apply: 'Ready to apply',
  follow_up_due: 'Follow-up due',
}

const SUMMARY_FILTERS = ['needs_approval', 'packet_in_progress', 'ready_to_apply', 'follow_up_due']
const QUEUE_SORTS = {
  readiness: 'Most ready',
  fit: 'Highest fit',
  updated: 'Recently updated',
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
  if (laneCounts.monitor > 0) {
    return 'monitor'
  }
  if (laneCounts.closed > 0) {
    return 'closed'
  }
  return 'monitor'
}

const PACKET_ITEMS = [
  { key: 'tailoredSummary', label: 'Tailored summary' },
  { key: 'resumeBullets', label: 'Resume bullets' },
  { key: 'coverLetterDraft', label: 'Cover letter draft' },
  { key: 'outreachNote', label: 'Outreach note' },
  { key: 'interviewBrief', label: 'Interview brief' },
  { key: 'talkingPoints', label: 'Talking points' },
]

function packetArtifactMeta(artifact) {
  if (!artifact?.available) {
    return null
  }
  const parts = []
  if (artifact.source) {
    parts.push(artifact.source === 'manual' ? 'Operator-linked' : artifact.source)
  }
  if (artifact.vaultPath) {
    parts.push(artifact.vaultPath)
  } else if (artifact.updatedAt) {
    parts.push(compactRelativeTime(artifact.updatedAt))
  }
  return parts.join(' · ') || artifact.label || null
}

function WorkflowRail({
  job,
  coverLetterState,
  workflowState,
  onApproveNextAction,
  onApprovePacket,
  onTogglePacketItem,
  onMoveStage,
  onScheduleFollowUp,
  onMarkFollowUpDueNow,
  onMarkFollowUpComplete,
  onResetFollowUp,
  onSetRecommendedNextAction,
}) {
  const workflow = deriveWorkflow(job, coverLetterState, workflowState)
  const timeline = buildWorkflowTimeline(job, coverLetterState)
  const showFollowUpActions = job?.status === 'applied' || workflowState?.stage === 'follow_up'
  const coverLetterArtifact = workflow.coverLetterArtifact

  return (
    <div className="ops-rail-stack">
      <section className="ops-rail-card">
        <div className="panel-heading compact">
          <div>
            <p className="section-label">Demo storyline</p>
            <h3 className="card-title">How to narrate this role</h3>
          </div>
        </div>
        <div className="section-rule" />
        <div className="demo-story-list">
          <div className="timeline-row">
            <span className="timeline-dot" aria-hidden="true" />
            <div>
              <strong>1. Explain the fit</strong>
              <p className="meta-text">Start with the score and strongest match.</p>
            </div>
          </div>
          <div className="timeline-row">
            <span className="timeline-dot" aria-hidden="true" />
            <div>
              <strong>2. Show the next action</strong>
              <p className="meta-text">Point to blockers, approvals, and packet readiness.</p>
            </div>
          </div>
          <div className="timeline-row">
            <span className="timeline-dot" aria-hidden="true" />
            <div>
              <strong>3. Generate or approve</strong>
              <p className="meta-text">Use the checklist or draft CTA to show execution support.</p>
            </div>
          </div>
        </div>
      </section>

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
            <span className="mini-label">Lane</span>
            <strong>{workflow.stageLabel}</strong>
          </div>
          <div className="ops-kv">
            <span className="mini-label">State</span>
            <strong>{workflow.stateLabel}</strong>
          </div>
          <div className="ops-kv">
            <span className="mini-label">Next action</span>
            <strong>{workflow.nextActionLabel}</strong>
          </div>
          <div className="ops-kv">
            <span className="mini-label">Confidence</span>
            <strong>{workflow.nextActionConfidence ? workflow.nextActionConfidence.toUpperCase() : 'Not set'}</strong>
          </div>
          <div className="ops-kv">
            <span className="mini-label">Due</span>
            <strong>{workflow.nextActionDueLabel || 'Not set'}</strong>
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
        {workflow.nextActionRationale ? (
          <div className="workflow-callout pending">
            <p className="section-label">Recommendation rationale</p>
            <strong>{workflow.nextActionLabel}</strong>
            <p className="body-copy">{workflow.nextActionRationale}</p>
          </div>
        ) : null}
        <div className="section-inline-actions workflow-action-row">
          <button type="button" className="text-button accent" onClick={onApproveNextAction}>
            Approve next action
          </button>
          <button type="button" className="ghost-button" onClick={onSetRecommendedNextAction}>
            Sync recommendation
          </button>
          <button type="button" className="ghost-button" onClick={onApprovePacket}>
            Approve packet
          </button>
        </div>
        <div className="workflow-stage-grid">
          {Object.entries(LANE_LABELS).map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={workflow.stage === key ? 'workflow-stage-button active' : 'workflow-stage-button'}
              onClick={() => onMoveStage(key)}
            >
              {label}
            </button>
          ))}
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
          <p className="body-copy">This workflow signal now persists with the role, so approvals and packet progress survive refreshes and demos.</p>
        </div>
      </section>

      <section className="ops-rail-card">
        <div className="panel-heading compact">
          <div>
            <p className="section-label">Application packet</p>
            <h3 className="card-title">Draft and approval checklist</h3>
          </div>
        </div>
        <div className="section-rule" />
        <div className="packet-checklist">
          {PACKET_ITEMS.map((item) => (
            <label key={item.key} className="packet-check-row">
              <input
                type="checkbox"
                checked={Boolean(workflowState?.packet?.[item.key])}
                onChange={() => onTogglePacketItem(item.key)}
              />
              <div className="packet-check-copy">
                <span>{item.label}</span>
                {packetArtifactMeta(workflow.packetArtifacts?.[item.key]) ? (
                  <span className="packet-artifact-meta">{packetArtifactMeta(workflow.packetArtifacts?.[item.key])}</span>
                ) : null}
              </div>
            </label>
          ))}
        </div>
        {coverLetterArtifact?.available ? (
          <div className="workflow-callout pending">
            <p className="section-label">Linked artifact</p>
            <strong>Cover letter draft</strong>
            <p className="body-copy">
              {coverLetterArtifact.provider && coverLetterArtifact.model
                ? `${coverLetterArtifact.provider} · ${coverLetterArtifact.model}`
                : 'Generated draft metadata persisted'}
              {coverLetterArtifact.wordCount ? ` · ${coverLetterArtifact.wordCount} words` : ''}
            </p>
            {coverLetterArtifact.vaultPath ? (
              <p className="meta-text">{coverLetterArtifact.vaultPath}</p>
            ) : null}
          </div>
        ) : null}
        <div className="ops-artifact-list">
          {PACKET_ITEMS.filter((item) => item.key !== 'coverLetterDraft')
            .map((item) => ({ ...item, artifact: workflow.packetArtifacts?.[item.key] }))
            .filter((item) => item.artifact?.available)
            .map((item) => (
              <div key={item.key} className="ops-artifact-row">
                <div>
                  <strong>{item.label}</strong>
                  <p className="meta-text">{packetArtifactMeta(item.artifact)}</p>
                </div>
                <span className="packet-artifact-pill">{item.artifact?.status || 'linked'}</span>
              </div>
            ))}
        </div>
      </section>

      <section className="ops-rail-card">
        <div className="panel-heading compact">
          <div>
            <p className="section-label">Follow-through</p>
            <h3 className="card-title">Follow-up plan</h3>
          </div>
        </div>
        <div className="section-rule" />
        <div className="ops-status-stack">
          <div className="ops-kv">
            <span className="mini-label">Status</span>
            <strong>{workflow.followUpLabel}</strong>
          </div>
          <div className="ops-kv">
            <span className="mini-label">Due</span>
            <strong>{workflow.followUpDueLabel || 'Not set'}</strong>
          </div>
          {workflow.followUpCompletedLabel ? (
            <div className="ops-kv">
              <span className="mini-label">Last completed</span>
              <strong>{workflow.followUpCompletedLabel}</strong>
            </div>
          ) : null}
        </div>
        {showFollowUpActions ? (
          <div className="workflow-follow-up-actions">
            <button type="button" className="ghost-button" onClick={() => onScheduleFollowUp(3)}>
              Schedule +3d
            </button>
            <button type="button" className="ghost-button" onClick={onMarkFollowUpDueNow}>
              Due now
            </button>
            <button type="button" className="text-button accent" onClick={onMarkFollowUpComplete}>
              Mark sent
            </button>
            <button type="button" className="ghost-button" onClick={onResetFollowUp}>
              Reset follow-up
            </button>
          </div>
        ) : (
          <p className="body-copy">Follow-up controls become active once a role moves into the applied lane.</p>
        )}
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
                {event.detail ? <p className="timeline-detail">{event.detail}</p> : null}
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
  const [queueFilter, setQueueFilter] = useState('all')
  const [queueSort, setQueueSort] = useState('readiness')
  const jobs = Array.isArray(jobsState.jobs) ? jobsState.jobs : []
  const demoJob = useMemo(() => preferredDemoJob(jobs), [jobs])
  const laneCounts = useMemo(
    () => ({
      focus: jobs.filter((job) => opsLane(job) === 'focus').length,
      review: jobs.filter((job) => opsLane(job) === 'review').length,
      follow_up: jobs.filter((job) => opsLane(job) === 'follow_up').length,
      monitor: jobs.filter((job) => opsLane(job) === 'monitor').length,
      closed: jobs.filter((job) => opsLane(job) === 'closed').length,
    }),
    [jobs]
  )
  const summaryCounts = useMemo(() => {
    const counts = {
      needs_approval: 0,
      packet_in_progress: 0,
      ready_to_apply: 0,
      follow_up_due: 0,
    }
    for (const job of jobs) {
      const workflowState = defaultWorkflowState(job)
      const workflow = deriveWorkflow(job, jobsState.coverLetterState, workflowState)
      if (workflowState.nextActionApproval !== 'approved' || workflowState.packetApproval !== 'approved') {
        counts.needs_approval += 1
      }
      if (Object.values(workflowState.packet || {}).some(Boolean) && workflowState.packetApproval !== 'approved') {
        counts.packet_in_progress += 1
      }
      if (workflow.stage === 'focus' && workflowState.packetApproval === 'approved') {
        counts.ready_to_apply += 1
      }
      if (isFollowUpDue(job)) {
        counts.follow_up_due += 1
      }
    }
    return counts
  }, [jobs, jobsState.coverLetterState])
  const filteredJobs = useMemo(
    () =>
      jobs
        .filter((job) => opsLane(job) === lane)
        .filter((job) => {
          const workflowState = defaultWorkflowState(job)
          const workflow = deriveWorkflow(job, jobsState.coverLetterState, workflowState)
          if (queueFilter === 'needs_approval') {
            return workflowState.nextActionApproval !== 'approved' || workflowState.packetApproval !== 'approved'
          }
          if (queueFilter === 'packet_in_progress') {
            return Object.values(workflowState.packet || {}).some(Boolean) && workflowState.packetApproval !== 'approved'
          }
          if (queueFilter === 'ready_to_apply') {
            return workflow.stage === 'focus' && workflowState.packetApproval === 'approved'
          }
          if (queueFilter === 'follow_up_due') {
            return isFollowUpDue(job)
          }
          return true
        })
        .sort((left, right) => {
          const leftWorkflowState = defaultWorkflowState(left)
          const rightWorkflowState = defaultWorkflowState(right)
          const leftWorkflow = deriveWorkflow(left, jobsState.coverLetterState, leftWorkflowState)
          const rightWorkflow = deriveWorkflow(right, jobsState.coverLetterState, rightWorkflowState)

          if (queueSort === 'fit') {
            return Number(right.fit_score ?? -1) - Number(left.fit_score ?? -1)
          }

          if (queueSort === 'updated') {
            const leftTime = new Date(leftWorkflowState.updatedAt || left.applied_at || left.evaluated_at || left.discovered_at || left.date_posted || 0).getTime()
            const rightTime = new Date(rightWorkflowState.updatedAt || right.applied_at || right.evaluated_at || right.discovered_at || right.date_posted || 0).getTime()
            return rightTime - leftTime
          }

          const readinessScore = (job, workflow, workflowState) => {
            let score = 0
            if (workflow.stage === 'focus') score += 50
            if (workflowState.packetApproval === 'approved') score += 40
            if (workflowState.nextActionApproval === 'approved') score += 18
            score += Object.values(workflowState.packet || {}).filter(Boolean).length * 4
            score += Math.max(0, Number(job.fit_score ?? 0) / 10)
            return score
          }

          return (
            readinessScore(right, rightWorkflow, rightWorkflowState) -
            readinessScore(left, leftWorkflow, leftWorkflowState)
          )
        })
        .slice(0, 30),
    [jobs, lane, jobsState.coverLetterState, queueFilter, queueSort]
  )
  const selectedJob = jobsState.selectedJob || demoJob || filteredJobs[0] || jobs[0] || null
  const selectedLane = selectedJob ? opsLane(selectedJob) : firstAvailableLane(laneCounts)
  const workflowState = defaultWorkflowState(selectedJob)
  const workflow = deriveWorkflow(selectedJob, jobsState.coverLetterState, workflowState)

  function nextIsoDays(days) {
    return new Date(Date.now() + days * 24 * 60 * 60 * 1000).toISOString()
  }

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

  useEffect(() => {
    if (filteredJobs.length > 0) {
      return
    }
    setQueueFilter('all')
  }, [filteredJobs.length, lane])

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

      <div className="ops-summary-strip">
        {SUMMARY_FILTERS.map((key) => (
          <button
            key={key}
            type="button"
            className={queueFilter === key ? 'ops-summary-card active' : 'ops-summary-card'}
            onClick={() => {
              if (queueFilter === key) {
                setQueueFilter('all')
                return
              }
              setQueueFilter(key)
            }}
          >
            <span className="mini-label">{QUEUE_FILTERS[key]}</span>
            <strong className="ops-summary-value">{summaryCounts[key]}</strong>
            <span className="meta-text">{queueFilter === key ? 'Showing filtered queue' : 'Click to focus the queue'}</span>
          </button>
        ))}
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
          <div className="ops-filter-list" aria-label="Queue filters">
            {Object.entries(QUEUE_FILTERS).map(([key, label]) => (
              <button
                key={key}
                type="button"
                className={queueFilter === key ? 'queue-filter-chip active' : 'queue-filter-chip'}
                onClick={() => setQueueFilter(key)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="ops-sort-row">
            <span className="mini-label">Sort queue</span>
            <div className="ops-filter-list" aria-label="Queue sorting">
              {Object.entries(QUEUE_SORTS).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  className={queueSort === key ? 'queue-filter-chip active' : 'queue-filter-chip'}
                  onClick={() => setQueueSort(key)}
                >
                  {label}
                </button>
              ))}
            </div>
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
                    <span>{WORKFLOW_STAGE_LABELS[itemWorkflow.stage] || itemWorkflow.stateLabel}</span>
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
                        <span>{workflow.stageLabel}</span>
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
            <WorkflowRail
              job={selectedJob}
              coverLetterState={jobsState.coverLetterState}
              workflowState={workflowState}
              onApproveNextAction={() => jobsState.updateWorkflow(selectedJob.jobId, { nextActionApproval: 'approved' })}
              onSetRecommendedNextAction={() =>
                jobsState.updateWorkflow(selectedJob.jobId, {
                  nextAction: {
                    action: workflow.nextAction,
                    rationale: workflow.nextActionRationale,
                    confidence: workflow.nextActionConfidence,
                    dueAt: workflow.nextActionDueAt || null,
                  },
                })
              }
              onApprovePacket={() => jobsState.updateWorkflow(selectedJob.jobId, { packetApproval: 'approved' })}
              onTogglePacketItem={(key) =>
                jobsState.updateWorkflow(selectedJob.jobId, {
                  packet: {
                    [key]: !workflowState?.packet?.[key],
                  },
                  ...(key === 'coverLetterDraft'
                    ? {}
                    : {
                        artifacts: {
                          [key]: {
                            status: !workflowState?.packet?.[key] ? 'ready' : 'draft',
                            updatedAt: new Date().toISOString(),
                            source: 'manual',
                            notes: `${PACKET_ARTIFACT_LABELS[key]} ${!workflowState?.packet?.[key] ? 'linked' : 'reopened'} in Ops.`,
                          },
                        },
                      }),
                })
              }
              onMoveStage={(stage) => jobsState.updateWorkflow(selectedJob.jobId, { stage })}
              onScheduleFollowUp={(days) =>
                jobsState.updateWorkflow(selectedJob.jobId, {
                  stage: 'follow_up',
                  followUp: {
                    status: 'scheduled',
                    dueAt: nextIsoDays(days),
                  },
                })
              }
              onMarkFollowUpDueNow={() =>
                jobsState.updateWorkflow(selectedJob.jobId, {
                  stage: 'follow_up',
                  followUp: {
                    status: 'scheduled',
                    dueAt: new Date().toISOString(),
                  },
                })
              }
              onMarkFollowUpComplete={() =>
                jobsState.updateWorkflow(selectedJob.jobId, {
                  stage: 'monitor',
                  followUp: {
                    status: 'completed',
                    dueAt: null,
                    lastCompletedAt: new Date().toISOString(),
                  },
                })
              }
              onResetFollowUp={() =>
                jobsState.updateWorkflow(selectedJob.jobId, {
                  stage: 'follow_up',
                  followUp: {
                    status: 'not_scheduled',
                    dueAt: null,
                    lastCompletedAt: null,
                  },
                })
              }
            />
          ) : (
            <StateNotice compact title="Workflow rail waiting on a role" body="Select a role to see blockers, packet status, and timeline." />
          )}
        </aside>
      </div>
    </section>
  )
}
