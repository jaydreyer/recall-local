import { useEffect, useState } from 'react'

import AddCompanyPanel from './components/AddCompanyPanel'
import CompanyList from './components/CompanyList'
import CompanyProfile from './components/CompanyProfile'
import FutureWidgetSlot from './components/FutureWidgetSlot'
import JobsCommandCenter from './components/JobsCommandCenter'
import OpsWorkspace from './components/OpsWorkspace'
import SettingsPanel from './components/SettingsPanel'
import SkillGapRadar from './components/SkillGapRadar'
import { useCompanies } from './hooks/useCompanies'
import { useJobs } from './hooks/useJobs'
import { useSettings } from './hooks/useSettings'

const TAB_KEYS = ['Jobs', 'Companies', 'Skill Gaps']
const VIEW_KEYS = ['Overview', 'Ops']
const ACTIVE_TAB_STORAGE_KEY = 'daily-dashboard-active-tab-v1'

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

function parseLocationState() {
  if (typeof window === 'undefined') {
    return { view: 'Overview', tab: 'Jobs', jobId: '' }
  }
  const params = new URLSearchParams(window.location.search)
  const requestedView = String(params.get('view') || 'overview').trim().toLowerCase()
  const requestedTab = String(params.get('tab') || '').trim()
  return {
    view: requestedView === 'ops' ? 'Ops' : 'Overview',
    tab: TAB_KEYS.includes(requestedTab) ? requestedTab : 'Jobs',
    jobId: String(params.get('jobId') || '').trim(),
  }
}

function syncLocationState({ view, tab, jobId }) {
  if (typeof window === 'undefined') {
    return
  }
  const params = new URLSearchParams(window.location.search)
  params.set('view', String(view || 'Overview').toLowerCase())
  if (tab && tab !== 'Jobs') {
    params.set('tab', tab)
  } else {
    params.delete('tab')
  }
  if (jobId) {
    params.set('jobId', jobId)
  } else {
    params.delete('jobId')
  }
  const next = `${window.location.pathname}?${params.toString()}`
  window.history.replaceState({}, '', next)
}

export default function App() {
  const locationState = parseLocationState()
  const [activeView, setActiveView] = useState(locationState.view)
  const [activeTab, setActiveTab] = useState(() => {
    if (typeof window === 'undefined') {
      return 'Jobs'
    }
    if (locationState.tab) {
      return locationState.tab
    }
    const stored = String(window.localStorage.getItem(ACTIVE_TAB_STORAGE_KEY) || '').trim()
    return TAB_KEYS.includes(stored) ? stored : 'Jobs'
  })
  const [now, setNow] = useState(new Date())
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [addCompanyOpen, setAddCompanyOpen] = useState(false)

  const jobsState = useJobs({ loadGaps: activeView === 'Overview' && activeTab === 'Skill Gaps' })
  const companiesState = useCompanies({ enabled: activeView === 'Overview' && activeTab === 'Companies' })
  const settingsState = useSettings({ enabled: settingsOpen })
  const recallLocalUrl = companionAppUrl(8170)

  useEffect(() => {
    const timerId = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timerId)
  }, [])

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(ACTIVE_TAB_STORAGE_KEY, activeTab)
    }
  }, [activeTab])

  useEffect(() => {
    syncLocationState({ view: activeView, tab: activeTab, jobId: jobsState.selectedJobId })
  }, [activeView, activeTab, jobsState.selectedJobId])

  useEffect(() => {
    if (locationState.jobId && locationState.jobId !== jobsState.selectedJobId) {
      jobsState.setSelectedJobId(locationState.jobId)
    }
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined
    }

    function handlePopState() {
      const next = parseLocationState()
      setActiveView(next.view)
      setActiveTab(next.tab)
      if (next.jobId) {
        jobsState.setSelectedJobId(next.jobId)
      }
    }

    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [jobsState])

  return (
    <div className={activeView === 'Ops' ? 'page-shell ops-shell' : 'page-shell'}>
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
        {activeView === 'Ops'
          ? 'An operator workstation for moving strong roles from evaluation to action.'
          : 'A working board for triage, fit review, and fast draft creation across the roles that matter most.'}
      </p>

      <nav className="view-switch reveal reveal-delay-2" aria-label="Application sections">
        {VIEW_KEYS.map((view) => (
          <button
            key={view}
            type="button"
            className={view === activeView ? 'dashboard-tab active' : 'dashboard-tab'}
            onClick={() => setActiveView(view)}
          >
            {view}
          </button>
        ))}
      </nav>

      {activeView === 'Overview' && (
        <>
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
                  onOpenOps={(jobId) => {
                    if (jobId) {
                      jobsState.setSelectedJobId(jobId)
                    }
                    setActiveView('Ops')
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
                    <span className={companiesState.loading ? 'status-chip loading' : companiesState.dataSource === 'cache' ? 'status-chip warning' : 'status-chip'}>
                      <span className={companiesState.loading ? 'status-dot pulse' : 'status-dot'} />
                      {companiesState.loading ? 'Loading watchlist' : companiesState.dataSource === 'cache' ? 'Cached watchlist on screen' : 'Watchlist ready'}
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
                    onRefresh={companiesState.refresh}
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
                    <span className={jobsState.gapsLoading ? 'status-chip loading' : jobsState.gapsDataSource === 'cache' ? 'status-chip warning' : 'status-chip'}>
                      <span className={jobsState.gapsLoading ? 'status-dot pulse' : 'status-dot'} />
                      {jobsState.gapsLoading ? 'Loading learning radar' : jobsState.gapsDataSource === 'cache' ? 'Cached learning radar on screen' : 'Learning radar ready'}
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
                    onRetry={jobsState.loadGapData}
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
        </>
      )}

      {activeView === 'Ops' && (
        <OpsWorkspace
          jobsState={jobsState}
          onBackToOverview={() => setActiveView('Overview')}
        />
      )}

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
