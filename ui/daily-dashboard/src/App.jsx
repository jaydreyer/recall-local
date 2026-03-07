import { useEffect, useState } from 'react'

import CompanyList from './components/CompanyList'
import JobsCommandCenter from './components/JobsCommandCenter'
import AddCompanyPanel from './components/AddCompanyPanel'
import CompanyProfile from './components/CompanyProfile'
import FutureWidgetSlot from './components/FutureWidgetSlot'
import SettingsPanel from './components/SettingsPanel'
import SkillGapRadar from './components/SkillGapRadar'
import { useCompanies } from './hooks/useCompanies'
import { useJobs } from './hooks/useJobs'
import { useSettings } from './hooks/useSettings'

const TAB_KEYS = ['Jobs', 'Companies', 'Skill Gaps']

function companionAppUrl(port) {
  if (typeof window === 'undefined') {
    return `http://127.0.0.1:${port}`
  }
  const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:'
  const hostname = String(window.location.hostname || '127.0.0.1').trim() || '127.0.0.1'
  return `${protocol}//${hostname}:${port}`
}

function HeaderClock({ now }) {
  const dateLabel = now.toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })
  const timeLabel = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })

  return (
    <div className="header-meta">
      <div className="clock">{timeLabel}</div>
      <div className="date">{dateLabel}</div>
    </div>
  )
}

function formatRefreshLabel(value) {
  if (!value) {
    return 'Waiting for first sync'
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return 'Recently refreshed'
  }
  return parsed.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  })
}

export default function App() {
  const [activeTab, setActiveTab] = useState('Jobs')
  const [now, setNow] = useState(new Date())
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [addCompanyOpen, setAddCompanyOpen] = useState(false)

  const jobsState = useJobs()
  const companiesState = useCompanies()
  const settingsState = useSettings()
  const recallLocalUrl = companionAppUrl(8170)

  useEffect(() => {
    const timerId = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timerId)
  }, [])

  return (
    <div className="page-shell">
      <div className="page-top-accent" />

      <header className="page-header reveal">
        <div>
          <div className="eyebrow-row">
            <span className="status-dot" />
            <p className="kicker">Mission Control · Alpha</p>
          </div>
          <h1 className="page-title">
            Jay&apos;s Ops
            <br />
            Console
          </h1>
        </div>

        <div className="header-actions">
          <HeaderClock now={now} />
          <a className="header-link" href={recallLocalUrl}>
            Open Recall.local
          </a>
          <button type="button" className="settings-trigger" aria-label="LLM settings" onClick={() => setSettingsOpen(true)}>
            <span aria-hidden="true">+</span>
          </button>
        </div>
      </header>

      <div className="section-rule page-rule reveal reveal-delay-1" />
      <p className="page-subtitle reveal reveal-delay-1">
        A working board for triage, fit review, and fast draft creation across the roles that matter most.
      </p>

      <nav className="dashboard-tabs reveal reveal-delay-2" aria-label="Dashboard sections">
        {TAB_KEYS.map((tab) => (
          <button
            key={tab}
            type="button"
            className={tab === activeTab ? 'dashboard-tab active' : 'dashboard-tab'}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </nav>

      <main className={activeTab === 'Jobs' ? 'dashboard-grid jobs-mode reveal reveal-delay-3' : 'dashboard-grid reveal reveal-delay-3'}>
        <section className="primary-column">
          {activeTab === 'Jobs' && (
            <JobsCommandCenter
              jobsState={jobsState}
              settings={settingsState.settings}
              onOpenSettings={() => setSettingsOpen(true)}
              onOpenCompany={(companyId) => {
                companiesState.selectCompany(companyId)
                setActiveTab('Companies')
              }}
            />
          )}

          {activeTab === 'Companies' && (
            <section className="panel-section">
              <div className="panel-heading">
                <div>
                  <p className="section-label">Tracked companies</p>
                  <h2 className="section-title">Company profiles</h2>
                </div>
                <div className="panel-actions">
                  <button type="button" className="text-button accent" onClick={() => setAddCompanyOpen(true)}>
                    Add company
                  </button>
                  <button
                    type="button"
                    className="text-button"
                    onClick={companiesState.refresh}
                    disabled={companiesState.loading}
                  >
                    Refresh list
                  </button>
                </div>
              </div>
              <div className="section-rule" />
              <div className="section-status-row">
                <span className={companiesState.loading ? 'status-chip loading' : 'status-chip'}>
                  <span className={companiesState.loading ? 'status-dot pulse' : 'status-dot'} />
                  {companiesState.loading ? 'Loading watchlist' : 'Watchlist ready'}
                </span>
                <span className="meta-text">
                  {companiesState.lastLoadedAt
                    ? `Last refreshed ${formatRefreshLabel(companiesState.lastLoadedAt)}`
                    : 'Waiting for first sync'}
                </span>
              </div>
              {companiesState.error && <p className="section-message error">{companiesState.error}</p>}
              <CompanyList
                companies={companiesState.companies}
                loading={companiesState.loading}
                selectedCompanyId={companiesState.selectedCompanyId}
                movingCompanyId={companiesState.savingCompanyId}
                onSelect={companiesState.selectCompany}
                onMoveTier={companiesState.moveCompanyTier}
              />
              <CompanyProfile
                company={companiesState.selectedCompany}
                loading={companiesState.detailLoading || (companiesState.loading && !companiesState.selectedCompany)}
                error={companiesState.detailError || companiesState.saveError}
                onRefresh={companiesState.refreshSelectedCompany}
                refreshing={companiesState.refreshing}
                onSaveSettings={companiesState.updateCompany}
                saving={companiesState.saving}
              />
            </section>
          )}

          {activeTab === 'Skill Gaps' && (
            <>
              <div className="section-status-row skill-gap-status">
                <span className={jobsState.gapsLoading ? 'status-chip loading' : 'status-chip'}>
                  <span className={jobsState.gapsLoading ? 'status-dot pulse' : 'status-dot'} />
                  {jobsState.gapsLoading ? 'Loading learning radar' : 'Learning radar ready'}
                </span>
                <span className="meta-text">
                  {jobsState.gapsLoadedAt
                    ? `Last refreshed ${formatRefreshLabel(jobsState.gapsLoadedAt)}`
                    : 'Waiting for first sync'}
                </span>
              </div>
              <SkillGapRadar
                gapData={jobsState.gaps}
                loading={jobsState.gapsLoading}
                error={jobsState.gapsError}
              />
            </>
          )}
        </section>

        <aside className="secondary-column">
          {activeTab !== 'Jobs' && (
            <>
              <div className="panel-section panel-stack">
                <div className="panel-heading">
                  <div>
                    <p className="section-label">Bridge snapshot</p>
                    <h2 className="section-title">Signal board</h2>
                  </div>
                </div>
                <div className="section-rule" />
                <div className="mini-metrics">
                  <div>
                    <span className="mini-label">High fit</span>
                    <strong className="mini-value">{jobsState.stats?.high_fit_count ?? '...'}</strong>
                  </div>
                  <div>
                    <span className="mini-label">Companies</span>
                    <strong className="mini-value">{companiesState.loading ? '...' : companiesState.companies.length}</strong>
                  </div>
                  <div>
                    <span className="mini-label">Focus gaps</span>
                    <strong className="mini-value">{jobsState.gaps?.aggregated_gaps?.length ?? '...'}</strong>
                  </div>
                </div>
              </div>

              <FutureWidgetSlot
                label="Profile posture"
                title="Preferred locations"
                body="Remote and Twin Cities roles remain the preferred alert lane for high-fit notifications."
              />
              <FutureWidgetSlot
                label="Settings"
                title="Model controls"
                body={`Current evaluation mode: ${settingsState.settings?.evaluation_model || 'local'} · ${settingsState.settings?.local_model || 'llama3.2:3b'}.`}
              />
            </>
          )}
        </aside>
      </main>

      <SettingsPanel
        open={settingsOpen}
        settings={settingsState.settings}
        loading={settingsState.loading}
        saving={settingsState.saving}
        error={settingsState.error}
        onClose={() => setSettingsOpen(false)}
        onSave={settingsState.saveSettings}
      />
      <AddCompanyPanel
        open={addCompanyOpen}
        saving={companiesState.saving}
        error={companiesState.saveError}
        onClose={() => setAddCompanyOpen(false)}
        onSave={companiesState.createCompany}
      />
    </div>
  )
}
