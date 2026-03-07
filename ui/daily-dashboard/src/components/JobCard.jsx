import JobDetail from './JobDetail'

function scoreClass(score) {
  if (score >= 75) {
    return 'high'
  }
  if (score >= 50) {
    return 'medium'
  }
  return 'low'
}

function tierClass(tier) {
  if (tier === 1) {
    return 'tier-one'
  }
  if (tier === 2) {
    return 'tier-two'
  }
  return 'tier-three'
}

function firstMatch(job) {
  const skills = Array.isArray(job.matching_skills) ? job.matching_skills : []
  if (skills.length === 0) {
    return 'No matching skills persisted yet.'
  }
  const first = skills[0]
  return typeof first === 'string' ? first : first.skill || first.name || 'Match unavailable'
}

function firstGap(job) {
  const gaps = Array.isArray(job.gaps) ? job.gaps : []
  if (gaps.length === 0) {
    return 'No top gap captured.'
  }
  const first = gaps[0]
  if (typeof first === 'string') {
    return first
  }
  return first.gap || first.skill || first.name || 'Gap unavailable'
}

function relativeTime(value) {
  if (!value) {
    return 'Unknown timing'
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

export default function JobCard({
  job,
  expanded,
  selected,
  busy,
  onToggle,
  onSelect,
  onMarkApplied,
  onDismiss,
  onSaveNotes,
  onGenerateDraft,
  onReevaluate,
  coverLetterState,
}) {
  return (
    <article className={selected ? 'job-card selected' : 'job-card'}>
      <button type="button" className="job-card-main" onClick={() => onSelect(job.jobId)}>
        <div className="job-card-topline">
          <div>
            <h3 className="job-title">{job.title}</h3>
            <p className="job-meta">{job.company}</p>
          </div>
          <div className="job-card-side">
            <span className={`tier-badge ${tierClass(job.company_tier)}`}>
              <span className="tier-dot" />
              T{job.company_tier || 3}
            </span>
          </div>
        </div>

        <div className="section-rule subtle" />

        <div className="job-card-midline">
          <div>
            <span className="meta-text">Score</span>
            <div className={`score-value ${scoreClass(job.fit_score || 0)}`}>{job.fit_score ?? 0}</div>
          </div>
          <div className="job-meta-right">
            <span>{job.location || 'Unknown location'}</span>
            <span>{relativeTime(job.discovered_at || job.evaluated_at)}</span>
          </div>
        </div>

        <div className="section-rule subtle" />

        <div className="summary-lines">
          <p>
            <span className="summary-label">Top match:</span> {firstMatch(job)}
          </p>
          <p>
            <span className="summary-label">Top gap:</span> {firstGap(job)}
          </p>
        </div>
      </button>

      <div className="job-card-actions">
        <button type="button" className="text-button accent" onClick={() => onToggle(job.jobId)}>
          {expanded ? 'Hide Details' : 'View Details'}
        </button>
        <button type="button" className="ghost-button compact" onClick={() => onMarkApplied(job.jobId)} disabled={busy}>
          Mark Applied
        </button>
        <button type="button" className="ghost-button compact" onClick={() => onDismiss(job.jobId)} disabled={busy}>
          Dismiss
        </button>
      </div>

      {expanded && (
        <JobDetail
          job={job}
          busy={busy}
          onMarkApplied={onMarkApplied}
          onDismiss={onDismiss}
          onSaveNotes={onSaveNotes}
          onGenerateDraft={onGenerateDraft}
          onReevaluate={onReevaluate}
          coverLetterState={coverLetterState}
        />
      )}
    </article>
  )
}
