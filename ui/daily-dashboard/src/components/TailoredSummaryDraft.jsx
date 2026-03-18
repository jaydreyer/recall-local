export default function TailoredSummaryDraft({ state, visible }) {
  if (!visible) {
    return null
  }

  if (state.loading) {
    return (
      <div className="detail-artifact-note">
        <p className="section-label">Tailored summary</p>
        <p className="body-copy">Generating tailored summary...</p>
      </div>
    )
  }

  if (state.error) {
    return (
      <div className="detail-artifact-note">
        <p className="section-label">Tailored summary</p>
        <p className="body-copy">{state.error}</p>
      </div>
    )
  }

  if (!state.summary) {
    return null
  }

  return (
    <div className="detail-artifact-note">
      <p className="section-label">Tailored summary</p>
      <p className="body-copy">
        {state.summary.provider && state.summary.model
          ? `${state.summary.provider} · ${state.summary.model}`
          : 'Generated summary metadata persisted'}
        {state.summary.word_count ? ` · ${state.summary.word_count} words` : ''}
      </p>
      <div className="description-pane">{state.summary.summary}</div>
      <p className="meta-text">
        Generated {new Date(state.summary.generated_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
        {state.summary.vault_path ? ` · ${state.summary.vault_path}` : ''}
      </p>
    </div>
  )
}
