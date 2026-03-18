function TalkingPointsToolbar({ talkingPoints }) {
  async function copyTalkingPoints() {
    if (!talkingPoints?.talking_points || !navigator.clipboard) {
      return
    }
    await navigator.clipboard.writeText(talkingPoints.talking_points)
  }

  return (
    <div className="draft-toolbar">
      <div className="draft-toolbar-meta">
        <span className="meta-text">
          {talkingPoints.provider} · {talkingPoints.model} · {talkingPoints.word_count} words
        </span>
        {talkingPoints.point_count ? <span className="meta-text">{talkingPoints.point_count} points</span> : null}
        {talkingPoints.generated_at ? <span className="meta-text">Generated {new Date(talkingPoints.generated_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span> : null}
        {talkingPoints.vault_path ? <span className="meta-text">{talkingPoints.vault_path}</span> : null}
      </div>
      <div className="draft-toolbar-actions">
        <button type="button" className="text-button" onClick={copyTalkingPoints}>
          Copy points
        </button>
      </div>
    </div>
  )
}

export default function TalkingPointsDraft({ state, visible }) {
  if (!visible) {
    return null
  }

  if (state.loading) {
    return <div className="draft-shell loading">Arthur is drafting talking points...</div>
  }

  if (state.error) {
    return <div className="draft-shell error">{state.error}</div>
  }

  if (!state.talkingPoints) {
    return null
  }

  return (
    <div className="draft-shell">
      <TalkingPointsToolbar talkingPoints={state.talkingPoints} />
      <textarea className="draft-textarea" value={state.talkingPoints.talking_points} readOnly />
    </div>
  )
}
