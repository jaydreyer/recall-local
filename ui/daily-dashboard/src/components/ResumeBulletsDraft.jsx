function ResumeBulletsToolbar({ bullets }) {
  async function copyBullets() {
    if (!bullets?.bullets || !navigator.clipboard) {
      return
    }
    await navigator.clipboard.writeText(bullets.bullets)
  }

  return (
    <div className="draft-toolbar">
      <div className="draft-toolbar-meta">
        <span className="meta-text">
          {bullets.provider} · {bullets.model} · {bullets.word_count} words
        </span>
        {bullets.bullet_count ? <span className="meta-text">{bullets.bullet_count} bullets</span> : null}
        {bullets.generated_at ? <span className="meta-text">Generated {new Date(bullets.generated_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span> : null}
        {bullets.vault_path ? <span className="meta-text">{bullets.vault_path}</span> : null}
      </div>
      <div className="draft-toolbar-actions">
        <button type="button" className="text-button" onClick={copyBullets}>
          Copy bullets
        </button>
      </div>
    </div>
  )
}

export default function ResumeBulletsDraft({ state, visible }) {
  if (!visible) {
    return null
  }

  if (state.loading) {
    return <div className="draft-shell loading">Arthur is tailoring resume bullets...</div>
  }

  if (state.error) {
    return <div className="draft-shell error">{state.error}</div>
  }

  if (!state.bullets) {
    return null
  }

  return (
    <div className="draft-shell">
      <ResumeBulletsToolbar bullets={state.bullets} />
      <textarea className="draft-textarea" value={state.bullets.bullets} readOnly />
    </div>
  )
}
