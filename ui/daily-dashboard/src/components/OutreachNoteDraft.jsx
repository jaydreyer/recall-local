function OutreachToolbar({ note }) {
  async function copyNote() {
    if (!note?.note || !navigator.clipboard) {
      return
    }
    await navigator.clipboard.writeText(note.note)
  }

  return (
    <div className="draft-toolbar">
      <div className="draft-toolbar-meta">
        <span className="meta-text">
          {note.provider} · {note.model} · {note.word_count} words
        </span>
        {note.generated_at ? <span className="meta-text">Generated {new Date(note.generated_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span> : null}
        {note.vault_path ? <span className="meta-text">{note.vault_path}</span> : null}
      </div>
      <div className="draft-toolbar-actions">
        <button type="button" className="text-button" onClick={copyNote}>
          Copy note
        </button>
      </div>
    </div>
  )
}

export default function OutreachNoteDraft({ state, visible }) {
  if (!visible) {
    return null
  }

  if (state.loading) {
    return <div className="draft-shell loading">Arthur is drafting an outreach note...</div>
  }

  if (state.error) {
    return <div className="draft-shell error">{state.error}</div>
  }

  if (!state.note) {
    return null
  }

  return (
    <div className="draft-shell">
      <OutreachToolbar note={state.note} />
      <textarea className="draft-textarea" value={state.note.note} readOnly />
    </div>
  )
}
