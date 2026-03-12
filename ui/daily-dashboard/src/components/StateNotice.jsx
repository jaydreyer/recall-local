export default function StateNotice({
  tone = 'neutral',
  title,
  body,
  actionLabel = '',
  onAction = null,
  compact = false,
}) {
  return (
    <div className={`state-notice ${tone} ${compact ? 'compact' : ''}`.trim()} role="status">
      <div className="state-notice-copy">
        {title ? <strong className="state-notice-title">{title}</strong> : null}
        {body ? <p className="state-notice-body">{body}</p> : null}
      </div>
      {actionLabel && typeof onAction === 'function' ? (
        <button type="button" className="state-notice-action" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </div>
  )
}
