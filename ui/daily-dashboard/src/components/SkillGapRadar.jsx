import { useMemo, useState } from 'react'

import { recommendationUrl } from '../utils/recommendationLinks'
import StateNotice from './StateNotice'

function severityClass(value) {
  if (value === 'critical') {
    return 'critical'
  }
  if (value === 'minor') {
    return 'minor'
  }
  return 'moderate'
}

function effortScore(value) {
  const text = String(value || '').toLowerCase()
  if (text.includes('hour')) {
    return 1
  }
  if (text.includes('week')) {
    return 2
  }
  if (text.includes('month')) {
    return 3
  }
  return 2
}

export default function SkillGapRadar({ gapData, loading, error, onRetry }) {
  const [view, setView] = useState('recommendations')
  const [completed, setCompleted] = useState({})
  const [showAll, setShowAll] = useState(false)

  const aggregatedGaps = Array.isArray(gapData?.aggregated_gaps) ? gapData.aggregated_gaps : []
  const maxFrequency = aggregatedGaps.reduce((max, gap) => Math.max(max, gap.frequency || 0), 1)
  const visibleGaps = showAll ? aggregatedGaps : aggregatedGaps.slice(0, 10)
  const criticalCount = aggregatedGaps.filter((gap) => gap.avg_severity === 'critical').length
  const totalRecommendations = aggregatedGaps.reduce(
    (count, gap) => count + (Array.isArray(gap.top_recommendations) ? gap.top_recommendations.length : 0),
    0
  )

  const learningPlan = useMemo(
    () =>
      aggregatedGaps
        .flatMap((gap) =>
          (Array.isArray(gap.top_recommendations) ? gap.top_recommendations : []).map((recommendation) => ({
            ...recommendation,
            gap: gap.gap,
            priorityScore: (gap.frequency || 0) * 10 - effortScore(recommendation.effort),
          }))
        )
        .sort((left, right) => right.priorityScore - left.priorityScore),
    [aggregatedGaps]
  )
  const visibleLearningPlan = showAll ? learningPlan : learningPlan.slice(0, 12)

  function toggleCompleted(key) {
    setCompleted((current) => ({ ...current, [key]: !current[key] }))
  }

  return (
    <section className="panel-section">
      <div className="panel-heading">
        <div>
          <p className="section-label">Learning radar</p>
          <h2 className="section-title">Top gaps across evaluated roles</h2>
        </div>
        <div className="toggle-row">
          <button type="button" className={view === 'recommendations' ? 'tab active compact' : 'tab compact'} onClick={() => setView('recommendations')}>
            Recommendations
          </button>
          <button type="button" className={view === 'plan' ? 'tab active compact' : 'tab compact'} onClick={() => setView('plan')}>
            Learning plan
          </button>
        </div>
      </div>
      <div className="section-rule" />

      {loading && (
        <>
          <p className="section-message">Loading learning gaps and recommendations...</p>
          <div className="gap-summary-grid" aria-hidden="true">
            {Array.from({ length: 3 }, (_, index) => (
              <div key={`gap-summary-${index}`} className="gap-summary-card skeleton-card">
                <span className="mini-label skeleton-line short" />
                <span className="mini-value skeleton-line value" />
                <div className="skeleton-stack">
                  <span className="skeleton-line long" />
                  <span className="skeleton-line medium" />
                </div>
              </div>
            ))}
          </div>
          <div className="gap-radar" aria-hidden="true">
            {Array.from({ length: 6 }, (_, index) => (
              <div key={`gap-row-${index}`} className="gap-radar-row skeleton-card">
                <div className="gap-radar-header">
                  <span className="skeleton-line medium" />
                  <span className="skeleton-line short" />
                </div>
                <div className="gap-bar-row">
                  <div className="gap-bar-track">
                    <div className="gap-bar-fill moderate skeleton-fill" style={{ width: `${72 - index * 8}%` }} />
                  </div>
                  <span className="status-badge muted">Loading</span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
      {error && (
        <StateNotice
          tone="warning"
          title="Learning radar is showing the last good snapshot"
          body={error}
          actionLabel={typeof onRetry === 'function' ? 'Retry radar' : ''}
          onAction={onRetry}
        />
      )}

      {!loading && !error && (
        <>
          {aggregatedGaps.length === 0 && (
            <StateNotice
              title="No aggregated gaps yet"
              body="This view becomes useful after more jobs have been evaluated. Once that happens, the radar will summarize the most common missing skills and learning resources."
              actionLabel={typeof onRetry === 'function' ? 'Refresh radar' : ''}
              onAction={onRetry}
            />
          )}
          <div className="gap-summary-grid">
            <div className="gap-summary-card">
              <span className="mini-label">Tracked gaps</span>
              <strong className="mini-value">{aggregatedGaps.length}</strong>
              <p className="body-copy">Distinct missing skills or domain signals across evaluated roles.</p>
            </div>
            <div className="gap-summary-card">
              <span className="mini-label">Critical</span>
              <strong className="mini-value">{criticalCount}</strong>
              <p className="body-copy">Highest-risk gaps that are blocking otherwise strong matches.</p>
            </div>
            <div className="gap-summary-card">
              <span className="mini-label">Resources</span>
              <strong className="mini-value">{totalRecommendations}</strong>
              <p className="body-copy">Linked courses and materials already mapped to the current gap set.</p>
            </div>
          </div>

          <div className="gap-radar">
            {visibleGaps.map((gap) => (
              <div key={gap.gap} className="gap-radar-row">
                <div className="gap-radar-header">
                  <span>{gap.gap}</span>
                  <span className="meta-text">{gap.frequency} role{gap.frequency === 1 ? '' : 's'}</span>
                </div>
                <div className="gap-bar-row">
                  <div className="gap-bar-track">
                    <div
                      className={`gap-bar-fill ${severityClass(gap.avg_severity)}`}
                      style={{ width: `${Math.max(12, (gap.frequency / maxFrequency) * 100)}%` }}
                    />
                  </div>
                  <span className={`status-badge ${severityClass(gap.avg_severity)}`}>{gap.avg_severity}</span>
                </div>
              </div>
            ))}
          </div>

          {view === 'recommendations' && (
            <div className="recommendation-groups">
              {visibleGaps.map((gap, index) => (
                <details key={gap.gap} className="recommendation-group" open={index === 0}>
                  <summary>
                    <span>{gap.gap}</span>
                    <span className="meta-text">{(gap.top_recommendations || []).length} recommendations</span>
                  </summary>
                  <div className="recommendation-checklist">
                    {(gap.top_recommendations || []).map((recommendation) => {
                      const key = `${gap.gap}-${recommendation.title}-${recommendation.source}`
                      const href = recommendationUrl(recommendation)
                      return (
                        <label key={key} className="check-row">
                          <input type="checkbox" checked={Boolean(completed[key])} onChange={() => toggleCompleted(key)} />
                          <span>
                            <strong>{recommendation.title}</strong>
                            <span className="check-meta">
                              {(recommendation.type || 'resource').toUpperCase()} · {recommendation.source || 'Source not provided'} ·{' '}
                              {recommendation.effort || 'Effort not provided'}
                            </span>
                            {href && (
                              <a className="text-button accent inline-link" href={href} target="_blank" rel="noreferrer">
                                Open link
                              </a>
                            )}
                          </span>
                        </label>
                      )
                    })}
                  </div>
                </details>
              ))}
            </div>
          )}

          {view === 'plan' && (
            <div className="learning-plan">
              {visibleLearningPlan.map((item) => (
                <div key={`${item.gap}-${item.title}`} className="learning-plan-row">
                  <div>
                    <p className="recommendation-title">{item.title}</p>
                    <p className="recommendation-meta">
                      {item.gap} · {item.source || 'Source not provided'} · {item.effort || 'Effort not provided'}
                    </p>
                    {recommendationUrl(item) && (
                      <a className="text-button accent inline-link" href={recommendationUrl(item)} target="_blank" rel="noreferrer">
                        Open link
                      </a>
                    )}
                  </div>
                  <span className="meta-text">Impact {item.priorityScore}</span>
                </div>
              ))}
            </div>
          )}

          {aggregatedGaps.length > 10 && (
            <div className="section-inline-actions">
              <button type="button" className="text-button accent" onClick={() => setShowAll((current) => !current)}>
                {showAll ? 'Show focus set' : `Show all ${aggregatedGaps.length} gaps`}
              </button>
            </div>
          )}
        </>
      )}
    </section>
  )
}
