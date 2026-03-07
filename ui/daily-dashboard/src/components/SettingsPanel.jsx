import { useEffect, useState } from 'react'

const MODEL_OPTIONS = {
  anthropic: [
    { value: 'claude-sonnet-4-5-20250929', label: 'Claude Sonnet 4.5' },
    { value: 'claude-opus-4-5-20250929', label: 'Claude Opus 4.5' },
  ],
  openai: [{ value: 'gpt-4o', label: 'GPT-4o' }],
  gemini: [{ value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash' }],
}

function Toggle({ checked, onChange, children }) {
  return (
    <button type="button" className={checked ? 'toggle-switch active' : 'toggle-switch'} onClick={() => onChange(!checked)}>
      <span className="toggle-thumb" />
      <span>{children}</span>
    </button>
  )
}

export default function SettingsPanel({ open, settings, loading, saving, error, onClose, onSave }) {
  const [form, setForm] = useState({
    evaluation_model: 'local',
    local_model: 'llama3.2:3b',
    cloud_provider: 'anthropic',
    cloud_model: 'claude-sonnet-4-5-20250929',
    auto_escalate: true,
    escalate_threshold_gaps: 2,
    escalate_threshold_rationale_words: 20,
  })

  useEffect(() => {
    if (settings) {
      setForm(settings)
    }
  }, [settings])

  if (!open) {
    return null
  }

  const providerOptions = MODEL_OPTIONS[form.cloud_provider] || MODEL_OPTIONS.anthropic

  async function handleSubmit(event) {
    event.preventDefault()
    const saved = await onSave({
      evaluation_model: form.evaluation_model,
      local_model: form.local_model,
      cloud_provider: form.cloud_provider,
      cloud_model: form.cloud_model,
      auto_escalate: form.auto_escalate,
      escalate_threshold_gaps: Number(form.escalate_threshold_gaps),
      escalate_threshold_rationale_words: Number(form.escalate_threshold_rationale_words),
    })
    if (saved) {
      onClose()
    }
  }

  return (
    <div className="settings-overlay" role="dialog" aria-modal="true">
      <div className="settings-panel">
        <div className="panel-heading">
          <div>
            <p className="section-label">Control room</p>
            <h2 className="section-title">LLM settings</h2>
          </div>
          <button type="button" className="ghost-button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="section-rule" />

        {loading ? (
          <p className="section-message">Loading settings...</p>
        ) : (
          <form className="settings-form" onSubmit={handleSubmit}>
            {error && <p className="section-message error">{error}</p>}

            <div className="settings-row">
              <span className="filter-label">Evaluation model</span>
              <div className="toggle-group">
                <button type="button" className={form.evaluation_model === 'local' ? 'tab active compact' : 'tab compact'} onClick={() => setForm((current) => ({ ...current, evaluation_model: 'local' }))}>
                  Local
                </button>
                <button type="button" className={form.evaluation_model === 'cloud' ? 'tab active compact' : 'tab compact'} onClick={() => setForm((current) => ({ ...current, evaluation_model: 'cloud' }))}>
                  Cloud
                </button>
              </div>
            </div>

            <label className="filter-field stacked">
              <span className="filter-label">Local model</span>
              <input
                className="filter-input"
                type="text"
                value={form.local_model || ''}
                onChange={(event) => setForm((current) => ({ ...current, local_model: event.target.value }))}
                placeholder="llama3.2:3b"
              />
            </label>

            <label className="filter-field stacked">
              <span className="filter-label">Cloud provider</span>
              <select className="filter-select" value={form.cloud_provider} onChange={(event) => setForm((current) => ({ ...current, cloud_provider: event.target.value, cloud_model: (MODEL_OPTIONS[event.target.value] || MODEL_OPTIONS.anthropic)[0].value }))}>
                <option value="anthropic">Anthropic</option>
                <option value="openai">OpenAI</option>
                <option value="gemini">Gemini</option>
              </select>
            </label>

            <label className="filter-field stacked">
              <span className="filter-label">Cloud model</span>
              <select className="filter-select" value={form.cloud_model} onChange={(event) => setForm((current) => ({ ...current, cloud_model: event.target.value }))}>
                {providerOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <div className="settings-row">
              <span className="filter-label">Auto-escalate</span>
              <Toggle checked={Boolean(form.auto_escalate)} onChange={(value) => setForm((current) => ({ ...current, auto_escalate: value }))}>
                Automatically switch to cloud when local quality looks weak
              </Toggle>
            </div>

            <label className="filter-field stacked">
              <span className="filter-label">Minimum gaps before escalation</span>
              <input
                className="filter-input"
                type="number"
                min="0"
                value={form.escalate_threshold_gaps}
                onChange={(event) => setForm((current) => ({ ...current, escalate_threshold_gaps: event.target.value }))}
              />
            </label>

            <label className="filter-field stacked">
              <span className="filter-label">Minimum rationale words before escalation</span>
              <input
                className="filter-input"
                type="number"
                min="0"
                value={form.escalate_threshold_rationale_words}
                onChange={(event) => setForm((current) => ({ ...current, escalate_threshold_rationale_words: event.target.value }))}
              />
            </label>

            <div className="detail-actions">
              <button type="submit" className="accent-button" disabled={saving}>
                {saving ? 'Saving...' : 'Save settings'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
