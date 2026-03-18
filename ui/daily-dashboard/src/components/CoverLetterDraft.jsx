function DraftToolbar({ draft }) {
  async function copyDraft() {
    if (!draft?.draft || !navigator.clipboard) {
      return
    }
    await navigator.clipboard.writeText(draft.draft)
  }

  return (
    <div className="draft-toolbar">
      <div className="draft-toolbar-meta">
        <span className="meta-text">
          {draft.provider} · {draft.model} · {draft.word_count} words
        </span>
        {draft.generated_at ? <span className="meta-text">Generated {new Date(draft.generated_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span> : null}
        {draft.vault_path ? <span className="meta-text">{draft.vault_path}</span> : null}
      </div>
      <div className="draft-toolbar-actions">
        <button type="button" className="text-button" onClick={copyDraft}>
          Copy draft
        </button>
      </div>
    </div>
  )
}

export default function CoverLetterDraft({ state, visible }) {
  if (!visible) {
    return null
  }

  if (state.loading) {
    return <div className="draft-shell loading">Arthur is drafting...</div>
  }

  if (state.error) {
    return <div className="draft-shell error">{state.error}</div>
  }

  if (!state.draft) {
    return null
  }

  return (
    <div className="draft-shell">
      <DraftToolbar draft={state.draft} />
      <textarea className="draft-textarea" value={state.draft.draft} readOnly />
    </div>
  )
}
