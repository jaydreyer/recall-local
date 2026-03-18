import { useDeferredValue, useState } from 'react'

import Filters from './Filters'
import JobCard from './JobCard'
import ScoreDistribution from './ScoreDistribution'
import StatsBar from './StatsBar'

export default function JobHuntPanel({
  filters,
  jobs,
  stats,
  loading,
  error,
  selectedJobId,
  selectedJob,
  detailLoading,
  actionJobId,
  coverLetterState,
  tailoredSummaryState,
  outreachNoteState,
  resumeBulletsState,
  interviewBriefState,
  talkingPointsState,
  setSelectedJobId,
  setFilter,
  refresh,
  markApplied,
  dismissJob,
  saveNotes,
  reevaluateJob,
  generateDraft,
  generateTailoredSummary,
  generateResumeBullets,
  generateOutreachNote,
  generateInterviewBrief,
  generateTalkingPoints,
}) {
  const [expandedJobId, setExpandedJobId] = useState('')
  const deferredJobs = useDeferredValue(jobs)

  function handleToggle(jobId) {
    setExpandedJobId((current) => (current === jobId ? '' : jobId))
    setSelectedJobId(jobId)
  }

  const hydratedJobs = deferredJobs.map((job) => (
    selectedJob && selectedJob.jobId === job.jobId ? selectedJob : job
  ))

  return (
    <section className="panel-section">
      <div className="panel-heading">
        <div>
          <p className="section-label">Morning lane</p>
          <h2 className="section-title">Job hunt panel</h2>
        </div>
        <button type="button" className="text-button" onClick={refresh} disabled={loading}>
          Refresh data
        </button>
      </div>
      <div className="section-rule" />

      <StatsBar stats={stats} />
      <div className="section-rule" />
      <Filters filters={filters} onChange={setFilter} />

      <div className="jobs-layout">
        <ScoreDistribution distribution={stats?.score_distribution} />

        <div className="job-list-shell">
          <div className="panel-heading compact">
            <div>
              <p className="section-label">Evaluated roles</p>
              <h3 className="card-title">Sorted by fit</h3>
            </div>
            {detailLoading && <span className="meta-text">Loading detail...</span>}
          </div>

          {error && <p className="section-message error">{error}</p>}
          {!loading && hydratedJobs.length === 0 && <p className="section-message">No jobs matched the current filters.</p>}

          <div className="job-list">
            {hydratedJobs.map((job) => (
              <JobCard
                key={job.jobId}
                job={job}
                expanded={expandedJobId === job.jobId}
                selected={selectedJobId === job.jobId}
                busy={actionJobId === job.jobId}
                onToggle={handleToggle}
                onSelect={setSelectedJobId}
                onMarkApplied={markApplied}
                onDismiss={dismissJob}
                onSaveNotes={saveNotes}
                onGenerateDraft={generateDraft}
                onGenerateTailoredSummary={generateTailoredSummary}
                onGenerateResumeBullets={generateResumeBullets}
                onGenerateOutreachNote={generateOutreachNote}
                onGenerateInterviewBrief={generateInterviewBrief}
                onGenerateTalkingPoints={generateTalkingPoints}
                onReevaluate={reevaluateJob}
                coverLetterState={coverLetterState}
                tailoredSummaryState={tailoredSummaryState}
                outreachNoteState={outreachNoteState}
                resumeBulletsState={resumeBulletsState}
                interviewBriefState={interviewBriefState}
                talkingPointsState={talkingPointsState}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
