import { useEffect, useState } from 'react'

const ATS_OPTIONS = [
  { value: 'greenhouse', label: 'Greenhouse' },
  { value: 'lever', label: 'Lever' },
  { value: 'workday', label: 'Workday' },
  { value: 'smartrecruiters', label: 'SmartRecruiters' },
  { value: 'ashbyhq', label: 'Ashby' },
  { value: 'other', label: 'Other' },
]

const EMPTY_FORM = {
  company_name: '',
  tier: '3',
  ats: 'greenhouse',
  board_id: '',
  url: '',
  title_filter: '',
  your_connection: '',
}

export default function AddCompanyPanel({ open, saving, error, onClose, onSave }) {
  const [form, setForm] = useState(EMPTY_FORM)

  useEffect(() => {
    if (open) {
      setForm(EMPTY_FORM)
    }
  }, [open])

  if (!open) {
    return null
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const result = await onSave({
      company_name: form.company_name.trim(),
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
    if (result?.ok) {
      onClose()
    }
  }

  return (
    <div className="settings-overlay" role="dialog" aria-modal="true">
      <div className="settings-panel">
        <div className="panel-heading">
          <div>
            <p className="section-label">Watchlist</p>
            <h2 className="section-title">Add company</h2>
          </div>
          <button type="button" className="ghost-button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="section-rule" />

        <form className="settings-form" onSubmit={handleSubmit}>
          {error && <p className="section-message error">{error}</p>}

          <label className="filter-field stacked">
            <span className="filter-label">Company</span>
            <input
              className="filter-input"
              type="text"
              value={form.company_name}
              onChange={(event) => setForm((current) => ({ ...current, company_name: event.target.value }))}
              placeholder="Airbnb"
            />
          </label>

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
              <select
                className="filter-select"
                value={form.ats}
                onChange={(event) => setForm((current) => ({ ...current, ats: event.target.value }))}
              >
                {ATS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="company-watch-grid">
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
                placeholder="https://boards-api.greenhouse.io/v1/boards/airbnb/jobs"
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
              placeholder="Why this company matters, warm intro notes, or current interview status."
            />
          </label>

          <div className="detail-actions">
            <button type="submit" className="accent-button" disabled={saving}>
              {saving ? 'Saving...' : 'Add company'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
