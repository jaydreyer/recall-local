export default function FutureWidgetSlot({ label, title, body }) {
  return (
    <section className="panel-section future-slot">
      <p className="section-label">{label}</p>
      <h2 className="section-title">{title}</h2>
      <div className="section-rule" />
      <p className="body-copy">{body}</p>
    </section>
  )
}
