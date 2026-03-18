function InterviewBriefToolbar({ brief }) {
  async function copyBrief() {
    if (!brief?.brief || !navigator.clipboard) {
      return
    }
    await navigator.clipboard.writeText(brief.brief)
  }

  return (
    <div className="draft-toolbar">
      <div className="draft-toolbar-meta">
        <span className="meta-text">
          {brief.provider} · {brief.model} · {brief.word_count} words
        </span>
        {brief.generated_at ? <span className="meta-text">Generated {new Date(brief.generated_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span> : null}
        {brief.vault_path ? <span className="meta-text">{brief.vault_path}</span> : null}
      </div>
      <div className="draft-toolbar-actions">
        <button type="button" className="text-button" onClick={copyBrief}>
          Copy brief
        </button>
      </div>
    </div>
  )
}

export default function InterviewBriefDraft({ state, visible }) {
  if (!visible) {
    return null
  }

  if (state.loading) {
    return <div className="draft-shell loading">Arthur is drafting the interview brief...</div>
  }

  if (state.error) {
    return <div className="draft-shell error">{state.error}</div>
  }

  if (!state.brief) {
    return null
  }

  return (
    <div className="draft-shell">
      <InterviewBriefToolbar brief={state.brief} />
      <textarea className="draft-textarea" value={state.brief.brief} readOnly />
    </div>
  )
}
