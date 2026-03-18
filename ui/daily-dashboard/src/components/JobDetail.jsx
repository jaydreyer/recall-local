import { useEffect, useState } from 'react'

import CoverLetterDraft from './CoverLetterDraft'
import OutreachNoteDraft from './OutreachNoteDraft'
import TailoredSummaryDraft from './TailoredSummaryDraft'
import { recommendationUrl } from '../utils/recommendationLinks'

function recommendationKey(item) {
  return `${item.type || 'item'}-${item.title || ''}-${item.source || ''}`
}

function GapRecommendation({ recommendation }) {
  const href = recommendationUrl(recommendation)

  return (
    <div className="recommendation-row">
      <div>
        <p className="recommendation-title">{recommendation.title}</p>
        <p className="recommendation-meta">
          {(recommendation.type || 'resource').toUpperCase()} · {recommendation.source || 'Source not provided'} ·{' '}
          {recommendation.effort || 'Effort not provided'}
        </p>
      </div>
      {href && (
        <a className="text-button accent recommendation-link" href={href} target="_blank" rel="noreferrer">
          Open link
        </a>
      )}
    </div>
  )
}

function evidenceLines(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean)
  }

  const text = String(value || '').trim()
  if (!text) {
    return []
  }

  if (text.startsWith('[') && text.endsWith(']')) {
    const matches = Array.from(text.matchAll(/'([^']+)'|"([^"]+)"/g))
      .map((match) => match[1] || match[2] || '')
      .map((item) => item.trim())
      .filter(Boolean)
    if (matches.length > 0) {
      return matches
    }
  }

  return text
    .split(/\n+|•/g)
    .map((item) => item.trim())
    .filter(Boolean)
}

function scoreLabel(job) {
  return Number(job.fit_score ?? -1) >= 0 ? String(job.fit_score) : 'NEW'
}

const SCORECARD_LABELS = {
  role_alignment: 'Role match',
  technical_alignment: 'Technical fit',
  domain_alignment: 'Domain fit',
  seniority_alignment: 'Seniority',
  communication_alignment: 'Communication',
}

function scoringMeta(job) {
  const scoring = job?.observation?.scoring
  if (scoring && typeof scoring === 'object') {
    return scoring
  }
  return {
    version: job?.scoring_version,
    scorecard: job?.scorecard,
    raw_model_fit_score: job?.raw_model_fit_score,
    computed_fit_score: job?.fit_score,
  }
}

function ScoreBreakdown({ job }) {
  const scoring = scoringMeta(job)
  const version = String(scoring?.version || '').trim()
  const scorecard = scoring?.scorecard && typeof scoring.scorecard === 'object' ? scoring.scorecard : {}
  const rows = Object.entries(SCORECARD_LABELS)
    .map(([key, label]) => {
      const value = Number(scorecard[key])
      if (Number.isNaN(value)) {
        return null
      }
      return { key, label, value }
    })
    .filter(Boolean)

  if (!version && rows.length === 0) {
    return null
  }

  const rawModelFitScore =
    scoring?.raw_model_fit_score === null || scoring?.raw_model_fit_score === undefined || scoring?.raw_model_fit_score === ''
      ? null
      : Number(scoring.raw_model_fit_score)
  const showRawModelFitScore = rawModelFitScore !== null && !Number.isNaN(rawModelFitScore) && rawModelFitScore >= 0

  return (
    <div className="detail-block scoring-block">
      <div className="score-breakdown-heading">
        <p className="section-label">How this scored</p>
        <span className="meta-chip">{version || 'Legacy score'}</span>
      </div>

      {rows.length > 0 && (
        <div className="score-breakdown-list">
          {rows.map((row) => (
            <div key={row.key} className="score-breakdown-row">
              <div className="score-breakdown-copy">
                <span>{row.label}</span>
                <span className="meta-text">{row.value}/5</span>
              </div>
              <div className="score-breakdown-track" aria-hidden="true">
                <div className="score-breakdown-fill" style={{ width: `${Math.max(12, row.value * 20)}%` }} />
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="scoring-footnote">
        <span>Computed rubric score: {scoreLabel(job)}</span>
        {showRawModelFitScore && <span>Raw model score: {rawModelFitScore}</span>}
      </div>
    </div>
  )
}

function MatchingSkills({ job }) {
  const skills = Array.isArray(job.matching_skills) ? job.matching_skills : []
  if (skills.length === 0) {
    return <p className="empty-copy">No matching skills were persisted for this job yet.</p>
  }

  return (
    <div className="detail-grid">
      {skills.map((skill, index) => {
        if (typeof skill === 'string') {
          return (
            <div key={`${skill}-${index}`} className="detail-grid-row">
              <span>{skill}</span>
              <span className="meta-text">Resume evidence linked in evaluation</span>
            </div>
          )
        }

        const lines = evidenceLines(skill.evidence || skill.resume_evidence)
        return (
          <div key={recommendationKey(skill)} className="detail-grid-row">
            <span>{skill.skill || skill.name}</span>
            {lines.length <= 1 ? (
              <span className="meta-text">{lines[0] || 'Evidence not persisted'}</span>
            ) : (
              <ul className="evidence-list">
                {lines.map((line) => (
                  <li key={`${recommendationKey(skill)}-${line}`} className="evidence-item">
                    {line}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )
      })}
    </div>
  )
}

function GapList({ job }) {
  const gaps = Array.isArray(job.gaps) ? job.gaps : []
  if (gaps.length === 0) {
    return <p className="empty-copy">No skill gaps were persisted for this job.</p>
  }

  return (
    <div className="gap-list">
      {gaps.map((gap, index) => {
        if (typeof gap === 'string') {
          return (
            <div key={`${gap}-${index}`} className="gap-card">
              <div className="gap-card-header">
                <strong>{gap}</strong>
                <span className="status-badge muted">Moderate</span>
              </div>
            </div>
          )
        }

        const recommendations = Array.isArray(gap.recommendations) ? gap.recommendations : []
        return (
          <div key={gap.gap || gap.skill || index} className="gap-card">
            <div className="gap-card-header">
              <strong>{gap.gap || gap.skill || gap.name}</strong>
              <span className={`status-badge ${gap.severity || 'moderate'}`}>{gap.severity || 'moderate'}</span>
            </div>
            {recommendations.length > 0 && (
              <div className="recommendation-list">
                {recommendations.map((recommendation) => (
                  <GapRecommendation
                    key={recommendationKey(recommendation)}
                    recommendation={recommendation}
                  />
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

export default function JobDetail({
  job,
  busy,
  onMarkApplied,
  onDismiss,
  onSaveNotes,
  onGenerateDraft,
  onGenerateTailoredSummary,
  onGenerateOutreachNote,
  onReevaluate,
  coverLetterState,
  tailoredSummaryState,
  outreachNoteState,
}) {
  const [notes, setNotes] = useState(job.notes || '')
  const persistedDraft = job?.workflow?.artifacts?.coverLetterDraft || null
  const persistedTailoredSummary = job?.workflow?.artifacts?.tailoredSummary || null
  const persistedOutreachNote = job?.workflow?.artifacts?.outreachNote || null

  useEffect(() => {
    setNotes(job.notes || '')
  }, [job.jobId, job.notes])

  return (
    <div className="job-detail">
      <div className="detail-columns">
        <div className="detail-column">
          <div className="score-hero">
            <span className="score-hero-value">{scoreLabel(job)}</span>
            <div>
              <p className="section-label">Score rationale</p>
              <p className="body-copy">{job.score_rationale || 'No rationale persisted yet.'}</p>
            </div>
          </div>

          <ScoreBreakdown job={job} />

          <div className="detail-block">
            <p className="section-label">Description</p>
            <div className="description-pane">{job.description || 'No description persisted.'}</div>
          </div>

          <div className="detail-block">
            <p className="section-label">Matching skills</p>
            <MatchingSkills job={job} />
          </div>

          <div className="detail-block">
            <p className="section-label">Gaps and recommendations</p>
            <GapList job={job} />
          </div>
        </div>

        <div className="detail-column secondary">
          <div className="aside-card accent">
            <p className="section-label">Application tip</p>
            <p className="body-copy">{job.application_tips || 'No application tips were generated yet.'}</p>
          </div>

          <div className="aside-card warm">
            <p className="section-label">Cover letter angle</p>
            <p className="body-copy">{job.cover_letter_angle || 'No cover letter angle persisted yet.'}</p>
          </div>

          <div className="detail-block">
            <p className="section-label">Notes</p>
            <textarea
              className="notes-textarea"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Add application notes, outreach context, or prep reminders."
            />
          </div>

          <div className="detail-actions detail-actions-grid">
            <button type="button" className="text-button accent detail-inline-action" onClick={() => onMarkApplied(job.jobId)} disabled={busy}>
              Mark Applied
            </button>
            <button type="button" className="ghost-button detail-inline-action" onClick={() => onDismiss(job.jobId)} disabled={busy}>
              Dismiss
            </button>
            <button type="button" className="ghost-button detail-inline-action" onClick={() => onSaveNotes(job.jobId, notes)} disabled={busy}>
              Save Notes
            </button>
            <button type="button" className="ghost-button detail-inline-action" onClick={() => onReevaluate(job.jobId)} disabled={busy}>
              Re-evaluate
            </button>
          </div>

          <div className="detail-actions detail-actions-stack">
            <button type="button" className="ghost-button detail-inline-action" onClick={() => onGenerateTailoredSummary(job.jobId)} disabled={busy}>
              Generate Tailored Summary
            </button>
            <button type="button" className="ghost-button detail-inline-action" onClick={() => onGenerateOutreachNote(job.jobId)} disabled={busy}>
              Generate Outreach Note
            </button>
            <button type="button" className="accent-button detail-primary-action" onClick={() => onGenerateDraft(job.jobId)} disabled={busy}>
              Generate Cover Letter Draft
            </button>
            {persistedTailoredSummary?.updatedAt ? (
              <div className="detail-artifact-note">
                <p className="section-label">Latest tailored summary artifact</p>
                <p className="body-copy">{persistedTailoredSummary.notes || 'Tailored summary artifact linked.'}</p>
                <p className="meta-text">
                  Updated {new Date(persistedTailoredSummary.updatedAt).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                  {persistedTailoredSummary.vaultPath ? ` · ${persistedTailoredSummary.vaultPath}` : ''}
                </p>
              </div>
            ) : null}
            {persistedOutreachNote?.updatedAt ? (
              <div className="detail-artifact-note">
                <p className="section-label">Latest outreach note artifact</p>
                <p className="body-copy">{persistedOutreachNote.notes || 'Outreach note artifact linked.'}</p>
                <p className="meta-text">
                  Updated {new Date(persistedOutreachNote.updatedAt).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                  {persistedOutreachNote.vaultPath ? ` · ${persistedOutreachNote.vaultPath}` : ''}
                </p>
              </div>
            ) : null}
            {persistedDraft?.generatedAt ? (
              <div className="detail-artifact-note">
                <p className="section-label">Latest draft artifact</p>
                <p className="body-copy">
                  {persistedDraft.provider && persistedDraft.model
                    ? `${persistedDraft.provider} · ${persistedDraft.model}`
                    : 'Draft metadata persisted'}
                  {persistedDraft.wordCount ? ` · ${persistedDraft.wordCount} words` : ''}
                </p>
                <p className="meta-text">
                  Generated {new Date(persistedDraft.generatedAt).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                  {persistedDraft.vaultPath ? ` · ${persistedDraft.vaultPath}` : ''}
                </p>
              </div>
            ) : null}
            {job.url && (
              <a className="text-button detail-inline-action" href={job.url} target="_blank" rel="noreferrer">
                Open posting
              </a>
            )}
          </div>
        </div>
      </div>

      <TailoredSummaryDraft state={tailoredSummaryState} visible={tailoredSummaryState.jobId === job.jobId} />
      <OutreachNoteDraft state={outreachNoteState} visible={outreachNoteState.jobId === job.jobId} />
      <CoverLetterDraft state={coverLetterState} visible={coverLetterState.jobId === job.jobId} />
    </div>
  )
}
