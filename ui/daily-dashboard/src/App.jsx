import { useEffect, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { fetchJobStats, fetchTopJobs, getBridgeConfig } from './api'

const TAB_KEYS = ['Jobs', 'Companies', 'Skill Gaps', 'Settings']

const MOCK_STATS = {
  total_jobs: 18,
  score_ranges: { high: 5, medium: 8, low: 5, unscored: 0 },
  by_source: { jobspy: 9, greenhouse: 6, career_page: 3 },
  by_day: { '2026-03-03': 7, '2026-03-04': 11 },
}

const MOCK_JOBS = [
  { jobId: 'job_001', title: 'Senior Solutions Engineer', company: 'Anthropic', fit_score: 84, status: 'evaluated' },
  { jobId: 'job_002', title: 'Solutions Architect', company: 'Postman', fit_score: 79, status: 'evaluated' },
  { jobId: 'job_003', title: 'Technical Account Manager', company: 'OpenAI', fit_score: 72, status: 'evaluated' },
  { jobId: 'job_004', title: 'AI Solutions Consultant', company: 'Aisera', fit_score: 67, status: 'evaluated' },
]

function scoreRangeRows(stats) {
  const ranges = stats?.score_ranges || {}
  return [
    { name: 'High', value: ranges.high || 0 },
    { name: 'Medium', value: ranges.medium || 0 },
    { name: 'Low', value: ranges.low || 0 },
    { name: 'Unscored', value: ranges.unscored || 0 },
  ]
}

export default function App() {
  const [activeTab, setActiveTab] = useState('Jobs')
  const [now, setNow] = useState(new Date())
  const [stats, setStats] = useState(MOCK_STATS)
  const [jobs, setJobs] = useState(MOCK_JOBS)
  const [apiMode, setApiMode] = useState('connecting')

  const bridgeConfig = useMemo(() => getBridgeConfig(), [])

  useEffect(() => {
    const timerId = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timerId)
  }, [])

  useEffect(() => {
    let canceled = false

    async function hydrate() {
      try {
        const [statsPayload, jobsPayload] = await Promise.all([fetchJobStats(), fetchTopJobs()])
        if (canceled) {
          return
        }
        setStats(statsPayload)
        setJobs(Array.isArray(jobsPayload.items) ? jobsPayload.items : MOCK_JOBS)
        setApiMode('live')
      } catch (_error) {
        if (canceled) {
          return
        }
        setStats(MOCK_STATS)
        setJobs(MOCK_JOBS)
        setApiMode('mock')
      }
    }

    hydrate()
    return () => {
      canceled = true
    }
  }, [])

  const scoreData = useMemo(() => scoreRangeRows(stats), [stats])
  const dateLabel = now.toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })
  const timeLabel = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })

  return (
    <div className="page-shell">
      <div className="top-accent" />

      <header className="header reveal">
        <div>
          <p className="kicker">Atelier Ops</p>
          <h1>Daily Dashboard</h1>
          <p className="subtitle">Career intelligence workspace with room for the rest of the day.</p>
        </div>

        <div className="header-meta">
          <div className="clock">{timeLabel}</div>
          <div className="date">{dateLabel}</div>
          <div className={`api-pill ${apiMode}`}>
            <span className="dot" />
            {apiMode === 'live' ? 'Bridge connected' : apiMode === 'mock' ? 'Mock data mode' : 'Connecting'}
          </div>
        </div>
      </header>

      <nav className="tabs reveal reveal-delay-1" aria-label="Dashboard sections">
        {TAB_KEYS.map((tab) => (
          <button
            key={tab}
            type="button"
            className={tab === activeTab ? 'tab active' : 'tab'}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </nav>

      <main className="layout reveal reveal-delay-2">
        <section className="panel jobs-panel">
          <div className="panel-header">
            <h2>{activeTab}</h2>
            <span className="mono">Bridge: {bridgeConfig.baseUrl}</span>
          </div>
          <div className="rule" />

          {activeTab === 'Jobs' && (
            <div className="jobs-content">
              <div className="chart-shell">
                <p className="section-kicker">Score Distribution</p>
                <div className="chart-wrap">
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={scoreData} margin={{ top: 10, right: 0, left: -18, bottom: 0 }}>
                      <CartesianGrid stroke="#EEE8DE" vertical={false} />
                      <XAxis dataKey="name" stroke="#8F8578" tickLine={false} axisLine={false} />
                      <YAxis stroke="#8F8578" tickLine={false} axisLine={false} allowDecimals={false} />
                      <Tooltip cursor={{ fill: '#F2ECE2' }} />
                      <Bar dataKey="value" fill="#E8553A" radius={[2, 2, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div>
                <p className="section-kicker">Top Evaluated Jobs</p>
                <ul className="job-list">
                  {jobs.map((job) => (
                    <li key={job.jobId} className="job-item">
                      <div>
                        <p className="job-title">{job.title}</p>
                        <p className="job-company">{job.company}</p>
                      </div>
                      <span className="score-badge">{job.fit_score}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {activeTab === 'Companies' && (
            <div className="placeholder-copy">
              <p>Company profiles will appear here once `/v1/companies` data is hydrated.</p>
              <p>Planned widgets: profile summary, hiring velocity, top skills per company.</p>
            </div>
          )}

          {activeTab === 'Skill Gaps' && (
            <div className="placeholder-copy">
              <p>Gap radar and learning queue land in Phase 6D.</p>
              <p>This panel is reserved for `/v1/job-gaps` and course recommendation overlays.</p>
            </div>
          )}

          {activeTab === 'Settings' && (
            <div className="placeholder-copy">
              <p>LLM runtime settings will bind to `GET/PATCH /v1/llm-settings`.</p>
              <p>API key configured: {bridgeConfig.apiKeyConfigured ? 'yes' : 'no'}.</p>
            </div>
          )}
        </section>

        <aside className="panel future-panel">
          <div className="panel-header">
            <h2>Future Widgets</h2>
            <span className="mono">Reserved slots</span>
          </div>
          <div className="rule" />
          <div className="future-grid">
            <div className="future-card">
              <p className="section-kicker">Weather</p>
              <p>Morning conditions and commute glance.</p>
            </div>
            <div className="future-card">
              <p className="section-kicker">Calendar</p>
              <p>Top three events and prep notes.</p>
            </div>
            <div className="future-card">
              <p className="section-kicker">News</p>
              <p>AI and market headlines with quick summaries.</p>
            </div>
            <div className="future-card">
              <p className="section-kicker">Sports</p>
              <p>Lightweight scores panel for personal context.</p>
            </div>
          </div>
        </aside>
      </main>
    </div>
  )
}
