import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const SCORE_COLORS = {
  '0-24': '#B8AD9E',
  '25-49': '#8F8578',
  '50-74': '#A0916B',
  '75-100': '#E8553A',
}

export default function ScoreDistribution({ distribution }) {
  const chartData = Array.isArray(distribution) ? distribution : []

  return (
    <div className="chart-card">
      <div className="panel-heading compact">
        <div>
          <p className="section-label">Score distribution</p>
          <h3 className="card-title">Fit spread</h3>
        </div>
      </div>
      <div className="chart-wrap">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={chartData} margin={{ top: 8, right: 10, left: -18, bottom: 0 }}>
            <CartesianGrid stroke="#EDE5D8" vertical={false} />
            <XAxis dataKey="range" stroke="#8F8578" tickLine={false} axisLine={false} />
            <YAxis stroke="#8F8578" tickLine={false} axisLine={false} allowDecimals={false} />
            <Tooltip cursor={{ fill: '#F4EDE2' }} />
            <Bar dataKey="count" radius={[3, 3, 0, 0]}>
              {chartData.map((entry) => (
                <Cell key={entry.range} fill={SCORE_COLORS[entry.range] || '#E8553A'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
