function DraftToolbar({ draft }) {
  async function copyDraft() {
    if (!draft?.draft || !navigator.clipboard) {
      return
    }
    await navigator.clipboard.writeText(draft.draft)
  }

  return (
    <div className="draft-toolbar">
      <span className="meta-text">
        {draft.provider} · {draft.model} · {draft.word_count} words
      </span>
      <button type="button" className="text-button" onClick={copyDraft}>
        Copy draft
      </button>
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
