import { useState } from 'react'

import CompanyLogo from './CompanyLogo'
import StateNotice from './StateNotice'
import { displayCompanyName } from '../utils/displayText'

const TIER_LANES = [
  { tier: 1, label: 'Tier 1', title: 'Immediate focus' },
  { tier: 2, label: 'Tier 2', title: 'Active watch' },
  { tier: 3, label: 'Tier 3', title: 'Longer-range monitor' },
]
const UNTRACKED_LANE = { tier: 0, label: 'Untracked', title: 'Discovery backlog' }

const DEFAULT_PREVIEW_COUNT = 4

function tierClass(tier) {
  const normalizedTier = Number(tier || 0)
  if (normalizedTier === 1) {
    return 'tier-one'
  }
  if (normalizedTier === 2) {
    return 'tier-two'
  }
  if (normalizedTier === 3) {
    return 'tier-three'
  }
  return 'tier-untracked'
}

function tierLabel(tier) {
  const normalizedTier = Number(tier || 0)
  return [1, 2, 3].includes(normalizedTier) ? `Tier ${normalizedTier}` : 'Untracked'
}

function sortCompanies(a, b) {
  const scoreA = Number(a.jobs_summary?.highest_fit_score ?? a.best_fit_score ?? -1)
  const scoreB = Number(b.jobs_summary?.highest_fit_score ?? b.best_fit_score ?? -1)
  const rolesA = Number(a.job_count || 0)
  const rolesB = Number(b.job_count || 0)

  if (scoreB !== scoreA) {
    return scoreB - scoreA
  }
  if (rolesB !== rolesA) {
    return rolesB - rolesA
  }
  return displayCompanyName(a.company_name, '').localeCompare(displayCompanyName(b.company_name, ''))
}

function bestFitLabel(company) {
  const score = Number(company.jobs_summary?.highest_fit_score ?? company.best_fit_score ?? -1)
  return score >= 0 ? `Best fit ${score}` : 'Not scored yet'
}

function openRoleLabel(count) {
  return `${count} open role${count === 1 ? '' : 's'}`
}

function laneCompanies(companies, tier) {
  return companies
    .filter((company) => Number(company.tier || 0) === tier)
    .sort(sortCompanies)
}

function untrackedCompanies(companies) {
  return companies
    .filter((company) => ![1, 2, 3].includes(Number(company.tier || 0)))
    .sort(sortCompanies)
}

export default function CompanyList({
  companies,
  loading,
  selectedCompanyId,
  movingCompanyId,
  onSelect,
  onMoveTier,
  onRefresh,
}) {
  const [expandedTiers, setExpandedTiers] = useState({})

  if (loading) {
    return (
      <div className="company-tier-board" aria-hidden="true">
        {TIER_LANES.map((lane) => (
          <section key={lane.tier} className="tier-lane skeleton-card">
            <div className="tier-lane-header">
              <div className="skeleton-stack">
                <span className="skeleton-line short" />
                <span className="skeleton-line medium title" />
              </div>
              <span className="skeleton-line short" />
            </div>
            <div className="tier-lane-list">
              {Array.from({ length: 2 }, (_, index) => (
                <article key={`${lane.tier}-${index}`} className="company-tier-shell skeleton-card">
                  <div className="company-card">
                    <span className="company-logo skeleton-line square" />
                    <div className="company-card-copy skeleton-stack">
                      <span className="skeleton-line medium title" />
                      <span className="skeleton-line short" />
                      <span className="skeleton-line medium" />
                      <span className="skeleton-line short" />
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
    )
  }

  function renderCompany(company) {
    const isMoving = movingCompanyId === company.company_id
    const normalizedTier = Number(company.tier || 0)

    return (
      <article key={company.company_id} className="company-tier-shell">
        <button
          type="button"
          className={company.company_id === selectedCompanyId ? 'company-card active' : 'company-card'}
          onClick={() => onSelect(company.company_id)}
        >
          <CompanyLogo company={company} className="company-logo" />
          <div className="company-card-copy">
            <h3 className="job-title">{displayCompanyName(company.company_name)}</h3>
            <span className={`tier-badge ${tierClass(company.tier)}`}>
              <span className="tier-dot" />
              {tierLabel(company.tier)}
            </span>
            <p className="company-card-meta">{openRoleLabel(Number(company.job_count || 0))}</p>
            <p className="company-card-meta">{bestFitLabel(company)}</p>
          </div>
        </button>

        <div className="company-card-footer">
          <span className="company-footer-label">Move tier</span>
          <div className="company-quick-tier-row">
            {TIER_LANES.map((target) => {
              const isCurrent = normalizedTier === target.tier
              const className = isCurrent
                ? 'tier-jump-button active'
                : isMoving
                  ? 'tier-jump-button pending'
                  : 'tier-jump-button'

              return (
                <button
                  key={`${company.company_id}-${target.tier}`}
                  type="button"
                  className={className}
                  disabled={isCurrent || isMoving}
                  onClick={() => onMoveTier(company.company_id, target.tier)}
                >
                  {isMoving && !isCurrent ? '...' : `T${target.tier}`}
                </button>
              )
            })}
          </div>
        </div>
      </article>
    )
  }

  const untrackedItems = untrackedCompanies(companies)
  const untrackedExpanded = Boolean(expandedTiers[UNTRACKED_LANE.tier])
  const visibleUntrackedItems = untrackedExpanded ? untrackedItems : []

  return (
    <div className="company-tier-board">
      {TIER_LANES.map((lane) => {
        const items = laneCompanies(companies, lane.tier)
        const expanded = Boolean(expandedTiers[lane.tier])
        const visibleItems = expanded ? items : items.slice(0, DEFAULT_PREVIEW_COUNT)
        const hiddenCount = Math.max(0, items.length - visibleItems.length)

        return (
          <section key={lane.tier} className="tier-lane">
            <div className="tier-lane-header">
              <div>
                <p className="section-label">{lane.label}</p>
                <h3 className="card-title">{lane.title}</h3>
              </div>
              <span className="meta-text">{items.length} tracked</span>
            </div>

            <div className="tier-lane-list">
              {items.length === 0 && (
                <StateNotice
                  compact
                  title="No companies in this tier yet"
                  body={lane.tier === 1 ? 'Move a company up when it becomes a real focus account.' : 'Tracked companies will appear here as the watchlist grows.'}
                  actionLabel={typeof onRefresh === 'function' ? 'Refresh list' : ''}
                  onAction={onRefresh}
                />
              )}

              {visibleItems.map((company) => renderCompany(company))}

              {(hiddenCount > 0 || expanded) && (
                <div className="tier-lane-footer">
                  <button
                    type="button"
                    className="text-button accent tier-lane-toggle"
                    onClick={() =>
                      setExpandedTiers((current) => ({
                        ...current,
                        [lane.tier]: !current[lane.tier],
                      }))
                    }
                  >
                    {expanded ? 'Show less' : `Show all ${items.length}`}
                  </button>
                </div>
              )}
            </div>
          </section>
        )
      })}
      <section className="tier-lane untracked-lane">
        <div className="tier-lane-header">
          <div>
            <p className="section-label">{UNTRACKED_LANE.label}</p>
            <h3 className="card-title">{UNTRACKED_LANE.title}</h3>
          </div>
          <span className="meta-text">{untrackedItems.length} companies</span>
        </div>

        <div className="tier-lane-list">
          {visibleUntrackedItems.map((company) => renderCompany(company))}
          <div className="tier-lane-footer">
            <button
              type="button"
              className="text-button accent tier-lane-toggle"
              onClick={() =>
                setExpandedTiers((current) => ({
                  ...current,
                  [UNTRACKED_LANE.tier]: !current[UNTRACKED_LANE.tier],
                }))
              }
            >
              {untrackedExpanded ? 'Collapse untracked' : `Show ${untrackedItems.length} untracked`}
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}
