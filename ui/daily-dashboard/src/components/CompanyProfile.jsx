import { useEffect, useState } from 'react'

import CompanyLogo from './CompanyLogo'
import StateNotice from './StateNotice'
import { displayCompanyName } from '../utils/displayText'

function metadataChips(company) {
  return [
    company.remote_policy,
    company.headquarters,
    company.company_size,
    company.funding_stage,
  ].filter(Boolean)
}

function displayBestFit(value) {
  const score = Number(value ?? -1)
  return score >= 0 ? String(score) : 'n/a'
}

function displayJobScore(job) {
  const score = Number(job.fit_score ?? -1)
  return score >= 0 ? String(score) : 'NEW'
}

function topSkillData(skillData) {
  return [...skillData]
    .sort((left, right) => Number(right.count || 0) - Number(left.count || 0))
    .slice(0, 6)
}

export default function CompanyProfile({ company, loading, error, onRefresh, refreshing, onSaveSettings, saving }) {
  const [form, setForm] = useState({
    tier: '3',
    ats: 'greenhouse',
    board_id: '',
    url: '',
    title_filter: '',
    your_connection: '',
  })
  const [showAllJobs, setShowAllJobs] = useState(false)

  useEffect(() => {
    if (company) {
      setForm({
        tier: String(company.tier || 3),
        ats: company.ats || 'greenhouse',
        board_id: company.board_id || '',
        url: company.careers_url || company.url || '',
        title_filter: Array.isArray(company.title_filter) ? company.title_filter.join(', ') : '',
        your_connection: company.your_connection || '',
      })
      setShowAllJobs(false)
    }
  }, [company])

  if (loading) {
    return <p className="section-message">Loading company profile and watch settings...</p>
  }
  if (error && !company) {
    return <StateNotice tone="warning" title="Company profile is unavailable right now" body={error} actionLabel="Retry profile" onAction={onRefresh} />
  }
  if (!company) {
    return <StateNotice title="Select a company to view the profile" body="Choose a company from the watchlist to load its board context, score summary, and tracking settings." />
  }

  const skillData = topSkillData(Array.isArray(company.skill_chart) ? company.skill_chart : [])
  const jobs = Array.isArray(company.jobs) ? company.jobs : []
  const visibleJobs = showAllJobs ? jobs : jobs.slice(0, 12)
  const jobsByStatus = company.jobs_summary?.jobs_by_status || {}
  const maxSkillCount = skillData.reduce((max, item) => Math.max(max, Number(item.count || 0)), 1)

  async function handleWatchSave(event) {
    event.preventDefault()
    await onSaveSettings(company.company_id, {
      tier: Number(form.tier),
      ats: form.ats.trim(),
      board_id: form.board_id.trim(),
      url: form.url.trim(),
      title_filter: form.title_filter
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean),
      your_connection: form.your_connection.trim(),
    })
  }

  return (
    <section className="company-profile">
      {error && <p className="section-message error">{error}</p>}
      <div className="panel-heading">
        <div className="company-header">
          <CompanyLogo company={company} className="company-logo large" />
          <div>
            <h2 className="section-title large">{displayCompanyName(company.company_name)}</h2>
            <div className="chip-row">
              {metadataChips(company).map((chip) => (
                <span key={chip} className="meta-chip">
                  {chip}
                </span>
              ))}
              <span className="meta-chip">Tier {company.tier || 3}</span>
            </div>
          </div>
        </div>
        <div className="detail-actions right">
          {company.careers_url && (
            <a className="text-button accent" href={company.careers_url} target="_blank" rel="noreferrer">
              Careers page
            </a>
          )}
          <button type="button" className="ghost-button" onClick={onRefresh} disabled={refreshing}>
            {refreshing ? 'Refreshing...' : 'Refresh profile'}
          </button>
        </div>
      </div>

      <div className="section-rule" />
      <p className="body-copy">{company.description || 'No company summary is stored yet.'}</p>
      <p className="meta-text">{company.about_source || 'Derived from tracked jobs'}</p>

      <div className="section-rule" />
      <form className="company-watch-card" onSubmit={handleWatchSave}>
        <div className="panel-heading compact">
          <div>
            <p className="section-label">Watch settings</p>
            <h3 className="card-title">Tracking and tier controls</h3>
          </div>
          <span className="meta-text">Changes here affect future discovery and the board tiering.</span>
        </div>

        <div className="company-watch-grid">
          <label className="filter-field stacked">
            <span className="filter-label">Tier</span>
            <select
              className="filter-select"
              value={form.tier}
              onChange={(event) => setForm((current) => ({ ...current, tier: event.target.value }))}
            >
              <option value="1">Tier 1</option>
              <option value="2">Tier 2</option>
              <option value="3">Tier 3</option>
            </select>
          </label>

          <label className="filter-field stacked">
            <span className="filter-label">ATS</span>
            <input
              className="filter-input"
              type="text"
              value={form.ats}
              onChange={(event) => setForm((current) => ({ ...current, ats: event.target.value }))}
              placeholder="greenhouse"
            />
          </label>

          <label className="filter-field stacked">
            <span className="filter-label">Board ID</span>
            <input
              className="filter-input"
              type="text"
              value={form.board_id}
              onChange={(event) => setForm((current) => ({ ...current, board_id: event.target.value }))}
              placeholder="airbnb"
            />
          </label>

          <label className="filter-field stacked">
            <span className="filter-label">Career page URL</span>
            <input
              className="filter-input"
              type="text"
              value={form.url}
              onChange={(event) => setForm((current) => ({ ...current, url: event.target.value }))}
              placeholder="https://boards-api.greenhouse.io/v1/boards/company/jobs"
            />
          </label>
        </div>

        <label className="filter-field stacked">
          <span className="filter-label">Title filters</span>
          <input
            className="filter-input"
            type="text"
            value={form.title_filter}
            onChange={(event) => setForm((current) => ({ ...current, title_filter: event.target.value }))}
            placeholder="solutions, platform, technical"
          />
        </label>

        <label className="filter-field stacked">
          <span className="filter-label">Your connection</span>
          <textarea
            className="notes-textarea"
            value={form.your_connection}
            onChange={(event) => setForm((current) => ({ ...current, your_connection: event.target.value }))}
            placeholder="Warm intros, recruiter context, or why this company matters."
          />
        </label>

        <div className="detail-actions">
          <button type="submit" className="accent-button" disabled={saving}>
            {saving ? 'Saving...' : 'Save watch settings'}
          </button>
        </div>
      </form>

      <div className="company-columns">
        <div className="aside-card">
          <p className="section-label">What they look for</p>
          <ul className="plain-list">
            {(company.what_they_look_for || []).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>

        <div className="aside-card warm">
          <p className="section-label">Your connection</p>
          <p className="body-copy">{company.your_connection || 'No warm connection note is stored for this company yet.'}</p>
        </div>
      </div>

      <div className="section-rule" />
      <div className="jobs-company-list">
        <div className="panel-heading compact">
          <div>
            <p className="section-label">Jobs from this company</p>
            <h3 className="card-title">
              {company.jobs_summary?.job_count || jobs.length} roles · best fit {displayBestFit(company.jobs_summary?.highest_fit_score)}
            </h3>
          </div>
          <span className="meta-text">
            {jobsByStatus.new || 0} new · {jobsByStatus.evaluated || 0} evaluated · {jobsByStatus.applied || 0} applied
          </span>
        </div>

        <div className="mini-job-list">
          {visibleJobs.map((job) => (
            <div key={job.jobId} className="mini-job-card">
              <div>
                <p className="job-title">{job.title}</p>
                <p className="job-meta">{job.location || 'Unknown location'}</p>
              </div>
              <span className="score-value inline">{displayJobScore(job)}</span>
            </div>
          ))}
        </div>
        {jobs.length > 12 && (
          <div className="section-inline-actions">
            <button type="button" className="text-button accent" onClick={() => setShowAllJobs((current) => !current)}>
              {showAllJobs ? 'Show top roles' : `Show all ${jobs.length} roles`}
            </button>
          </div>
        )}
      </div>

      <div className="section-rule" />
      <div className="chart-card wide">
        <div className="panel-heading compact">
          <div>
            <p className="section-label">Key skills they value</p>
            <h3 className="card-title">Skill frequency</h3>
          </div>
          <span className="meta-text">Top {skillData.length} themes from tracked roles</span>
        </div>
        {skillData.length === 0 ? (
          <p className="section-message">No skill-signal data is available for this company yet.</p>
        ) : (
          <div className="company-skill-bars">
            {skillData.map((item) => (
              <div key={item.skill} className="company-skill-row">
                <div className="company-skill-head">
                  <p className="company-skill-name">{item.skill}</p>
                  <span className="meta-text">{item.count} roles</span>
                </div>
                <div className="company-skill-meter">
                  <div
                    className="company-skill-fill"
                    style={{ width: `${Math.max(12, (Number(item.count || 0) / maxSkillCount) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
