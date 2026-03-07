function metricRows(stats) {
  return [
    { label: 'New Today', value: stats?.new_today ?? 0 },
    { label: 'High Fit', value: stats?.high_fit_count ?? stats?.score_ranges?.high ?? 0 },
    { label: 'Average Score', value: stats?.average_fit_score ?? 0 },
    { label: 'Total', value: stats?.total_jobs ?? 0 },
  ]
}

export default function StatsBar({ stats }) {
  return (
    <section className="stats-bar">
      {metricRows(stats).map((metric) => (
        <div key={metric.label} className="stats-item">
          <span className="stats-value">{metric.value}</span>
          <span className="stats-label">{metric.label}</span>
        </div>
      ))}
    </section>
  )
}
