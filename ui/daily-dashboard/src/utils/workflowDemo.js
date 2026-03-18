export const WORKFLOW_STAGES = ['focus', 'review', 'follow_up', 'monitor', 'closed']
export const FOLLOW_UP_STATUSES = ['not_scheduled', 'scheduled', 'completed']

export const WORKFLOW_STAGE_LABELS = {
  focus: 'Focus queue',
  review: 'Needs review',
  follow_up: 'Follow-up',
  monitor: 'Monitor',
  closed: 'Closed',
}

function effectiveStatus(job) {
  if (job?.applied || job?.status === 'applied') {
    return 'applied'
  }
  if (job?.dismissed || job?.status === 'dismissed') {
    return 'dismissed'
  }
  return String(job?.status || 'new').toLowerCase()
}

export function coverLetterArtifact(job = null, coverLetterState = null) {
  if (coverLetterState?.jobId === job?.jobId && coverLetterState?.draft) {
    return {
      draftId: coverLetterState.draft.draft_id || null,
      generatedAt: coverLetterState.draft.generated_at || null,
      provider: coverLetterState.draft.provider || null,
      model: coverLetterState.draft.model || null,
      wordCount: coverLetterState.draft.word_count || null,
      savedToVault: Boolean(coverLetterState.draft.saved_to_vault),
      vaultPath: coverLetterState.draft.vault_path || null,
      available: true,
    }
  }
  const artifact = job?.workflow?.artifacts?.coverLetterDraft
  if (!artifact) {
    return {
      draftId: null,
      generatedAt: null,
      provider: null,
      model: null,
      wordCount: null,
      savedToVault: false,
      vaultPath: null,
      available: false,
    }
  }
  return {
    draftId: artifact.draftId || null,
    generatedAt: artifact.generatedAt || null,
    provider: artifact.provider || null,
    model: artifact.model || null,
    wordCount: artifact.wordCount || null,
    savedToVault: Boolean(artifact.savedToVault),
    vaultPath: artifact.vaultPath || null,
    available: Boolean(artifact.generatedAt || artifact.draftId || artifact.vaultPath),
  }
}

function hasDraft(job, coverLetterState) {
  return coverLetterArtifact(job, coverLetterState).available
}

function packetCompletion(packet = {}) {
  return Object.values(packet).filter(Boolean).length
}

function parseDate(value) {
  if (!value) {
    return null
  }
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

function formatDateTime(value, fallback = 'Not set') {
  const parsed = parseDate(value)
  if (!parsed) {
    return fallback
  }
  return parsed.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function followUpState(job, workflowState) {
  const raw = workflowState?.followUp || {}
  const status = FOLLOW_UP_STATUSES.includes(raw.status) ? raw.status : 'not_scheduled'
  const dueAt = raw.dueAt || null
  const lastCompletedAt = raw.lastCompletedAt || null
  const dueDate = parseDate(dueAt)
  const isDue = status !== 'completed' && Boolean(dueDate) && dueDate.getTime() <= Date.now()
  const activeFollowUp = effectiveStatus(job) === 'applied' || workflowState?.stage === 'follow_up'
  const needsAttention = activeFollowUp && (status === 'not_scheduled' || isDue)

  let label = 'Not scheduled'
  if (status === 'completed') {
    label = lastCompletedAt ? `Completed ${formatDateTime(lastCompletedAt, 'recently')}` : 'Completed'
  } else if (status === 'scheduled' && dueAt) {
    label = isDue ? `Due ${formatDateTime(dueAt, 'now')}` : `Scheduled for ${formatDateTime(dueAt, 'soon')}`
  }

  return {
    status,
    dueAt,
    lastCompletedAt,
    isDue,
    activeFollowUp,
    needsAttention,
    label,
    dueLabel: dueAt ? formatDateTime(dueAt, 'Not set') : 'Not set',
    completedLabel: lastCompletedAt ? formatDateTime(lastCompletedAt, 'Not completed') : 'Not completed',
  }
}

function inferWorkflowStage(job) {
  const status = effectiveStatus(job)
  const fitScore = Number(job?.fit_score ?? -1)
  if (status === 'dismissed' || status === 'expired') {
    return 'closed'
  }
  if (status === 'applied') {
    return 'follow_up'
  }
  if (status === 'new' || fitScore < 0) {
    return 'review'
  }
  if (fitScore >= 75) {
    return 'focus'
  }
  return 'monitor'
}

export function defaultWorkflowState(job = null) {
  const stage = WORKFLOW_STAGES.includes(job?.workflow?.stage) ? job.workflow.stage : inferWorkflowStage(job)
  return {
    stage,
    nextActionApproval: job?.workflow?.nextActionApproval || 'pending',
    packetApproval: job?.workflow?.packetApproval || 'pending',
    packet: {
      tailoredSummary: Boolean(job?.workflow?.packet?.tailoredSummary),
      resumeBullets: Boolean(job?.workflow?.packet?.resumeBullets),
      coverLetterDraft: Boolean(job?.workflow?.packet?.coverLetterDraft),
      outreachNote: Boolean(job?.workflow?.packet?.outreachNote),
      interviewBrief: Boolean(job?.workflow?.packet?.interviewBrief),
      talkingPoints: Boolean(job?.workflow?.packet?.talkingPoints),
    },
    artifacts: {
      coverLetterDraft: coverLetterArtifact(job, null),
    },
    followUp: {
      status: FOLLOW_UP_STATUSES.includes(job?.workflow?.followUp?.status) ? job.workflow.followUp.status : 'not_scheduled',
      dueAt: job?.workflow?.followUp?.dueAt || null,
      lastCompletedAt: job?.workflow?.followUp?.lastCompletedAt || null,
    },
    updatedAt: job?.workflow?.updatedAt || null,
  }
}

export function deriveWorkflow(job, coverLetterState, workflowState = null) {
  const effectiveWorkflow = workflowState || defaultWorkflowState(job)
  const stage = effectiveWorkflow?.stage || inferWorkflowStage(job)
  const status = effectiveStatus(job)
  const fitScore = Number(job?.fit_score ?? -1)
  const draftGenerated = hasDraft(job, coverLetterState) || Boolean(effectiveWorkflow?.packet?.coverLetterDraft)
  const highFit = fitScore >= 75
  const evaluated = fitScore >= 0 && status !== 'new'
  const packetDone = packetCompletion(effectiveWorkflow?.packet) > 0
  const nextActionApproval = effectiveWorkflow?.nextActionApproval || 'pending'
  const packetApproval = effectiveWorkflow?.packetApproval || 'pending'
  const followUp = followUpState(job, effectiveWorkflow)
  const draftArtifact = coverLetterArtifact(job, coverLetterState)
  const draftArtifactLabel = draftArtifact.available
    ? draftArtifact.savedToVault && draftArtifact.vaultPath
      ? 'Draft saved to vault'
      : draftArtifact.generatedAt
        ? `Draft generated ${formatDateTime(draftArtifact.generatedAt, 'recently')}`
        : 'Draft generated'
    : 'No draft artifact yet'

  if (status === 'dismissed' || status === 'expired') {
    return {
      state: 'closed',
      stateLabel: 'Closed',
      nextAction: 'none',
      nextActionLabel: 'Closed out',
      blocker: 'Role archived for reference',
      blockerTone: 'muted',
      packetStatus: draftGenerated ? 'draft_generated' : 'not_started',
      packetLabel: draftGenerated ? 'Draft generated' : 'Not started',
      approvalLabel: 'No approval needed',
      priorityLabel: 'Archive lane',
      stage,
      stageLabel: WORKFLOW_STAGE_LABELS[stage] || 'Closed',
      followUpLabel: followUp.label,
      followUpStatus: followUp.status,
      followUpDueLabel: followUp.dueLabel,
      coverLetterArtifactLabel: draftArtifactLabel,
      coverLetterArtifact: draftArtifact,
    }
  }

  if (status === 'applied') {
    return {
      state: 'applied',
      stateLabel: 'Applied',
      nextAction: followUp.status === 'completed' ? 'monitor_response' : 'follow_up',
      nextActionLabel:
        followUp.status === 'completed'
          ? 'Monitor response'
          : followUp.isDue
            ? 'Send follow-up'
            : followUp.status === 'scheduled'
              ? 'Hold until follow-up date'
              : 'Schedule follow-up',
      blocker:
        followUp.status === 'completed'
          ? 'Waiting for response'
          : followUp.isDue
            ? `Follow-up due ${followUp.dueLabel}`
            : followUp.status === 'scheduled'
              ? `Follow-up scheduled for ${followUp.dueLabel}`
              : 'Follow-up not scheduled',
      blockerTone:
        followUp.status === 'completed'
          ? 'muted'
          : followUp.isDue || followUp.status === 'not_scheduled'
            ? 'warning'
            : 'pending',
      packetStatus: draftGenerated ? 'draft_generated' : 'not_started',
      packetLabel: draftGenerated ? 'Draft generated' : 'Not started',
      approvalLabel: packetApproval === 'approved' ? 'Packet approved' : 'Application recorded',
      priorityLabel: followUp.needsAttention ? 'Needs touchpoint' : 'Keep momentum',
      stage,
      stageLabel: WORKFLOW_STAGE_LABELS[stage] || 'Follow-up',
      followUpLabel: followUp.label,
      followUpStatus: followUp.status,
      followUpDueLabel: followUp.dueLabel,
      followUpCompletedLabel: followUp.completedLabel,
      coverLetterArtifactLabel: draftArtifactLabel,
      coverLetterArtifact: draftArtifact,
    }
  }

  if (status === 'new' || !evaluated) {
    return {
      state: 'new',
      stateLabel: 'New',
      nextAction: 'review_role',
      nextActionLabel: 'Review role',
      blocker: 'Needs evaluation',
      blockerTone: 'warning',
      packetStatus: 'not_started',
      packetLabel: 'Not started',
      approvalLabel: 'Awaiting review',
      priorityLabel: 'Fresh intake',
      stage,
      stageLabel: WORKFLOW_STAGE_LABELS[stage] || 'Needs review',
      followUpLabel: followUp.label,
      followUpStatus: followUp.status,
      followUpDueLabel: followUp.dueLabel,
      coverLetterArtifactLabel: draftArtifactLabel,
      coverLetterArtifact: draftArtifact,
    }
  }

  if (highFit) {
    return {
      state: 'target',
      stateLabel: 'Target',
      nextAction: 'tailor_resume',
      nextActionLabel: 'Tailor resume',
      blocker:
        packetApproval === 'approved'
          ? 'Ready to move forward'
          : draftGenerated || packetDone
            ? 'Waiting on packet review'
            : nextActionApproval === 'approved'
              ? 'Tailored packet missing'
              : 'Next action not approved',
      blockerTone: packetApproval === 'approved' ? 'pending' : draftGenerated || packetDone ? 'pending' : 'warning',
      packetStatus: packetApproval === 'approved' ? 'approved' : draftGenerated || packetDone ? 'draft_generated' : 'not_started',
      packetLabel: packetApproval === 'approved' ? 'Approved' : draftGenerated || packetDone ? 'Draft generated' : 'Not started',
      approvalLabel:
        packetApproval === 'approved'
          ? 'Packet approved'
          : nextActionApproval === 'approved'
            ? 'Next action approved'
            : 'Needs approval',
      priorityLabel: 'Focus now',
      stage,
      stageLabel: WORKFLOW_STAGE_LABELS[stage] || 'Focus queue',
      followUpLabel: followUp.label,
      followUpStatus: followUp.status,
      followUpDueLabel: followUp.dueLabel,
      coverLetterArtifactLabel: draftArtifactLabel,
      coverLetterArtifact: draftArtifact,
    }
  }

  return {
    state: 'reviewed',
    stateLabel: 'Reviewed',
    nextAction: fitScore >= 50 ? 'hold' : 'skip',
    nextActionLabel: fitScore >= 50 ? 'Hold for later' : 'Skip for now',
    blocker: 'Fit threshold not met',
    blockerTone: 'muted',
    packetStatus: 'not_started',
    packetLabel: 'Not started',
    approvalLabel: 'No packet needed yet',
    priorityLabel: 'Monitor',
    stage,
    stageLabel: WORKFLOW_STAGE_LABELS[stage] || 'Monitor',
    followUpLabel: followUp.label,
    followUpStatus: followUp.status,
    followUpDueLabel: followUp.dueLabel,
    coverLetterArtifactLabel: draftArtifactLabel,
    coverLetterArtifact: draftArtifact,
  }
}

function buildEvent(type, label, value, detail = '') {
  if (!value) {
    return null
  }
  const parsed = new Date(value)
  return {
    type,
    label,
    detail,
    value,
    timestamp: Number.isNaN(parsed.getTime()) ? 0 : parsed.getTime(),
    dateLabel: Number.isNaN(parsed.getTime())
      ? String(value)
      : parsed.toLocaleString('en-US', {
          month: 'short',
          day: 'numeric',
          hour: 'numeric',
          minute: '2-digit',
        }),
  }
}

export function buildWorkflowTimeline(job, coverLetterState) {
  const persistedEvents = Array.isArray(job?.workflowTimeline)
    ? job.workflowTimeline.map((event) => buildEvent(event.type, event.label, event.at, event.detail || '')).filter(Boolean)
    : []
  const events = [
    buildEvent('discovered', 'Role discovered', job?.discovered_at || job?.date_posted),
    buildEvent('evaluated', 'Role evaluated', job?.evaluated_at),
    job?.applied || job?.status === 'applied' ? buildEvent('applied', 'Moved to applied', job?.applied_at || job?.evaluated_at) : null,
    hasDraft(job, coverLetterState)
      ? buildEvent('draft', 'Cover letter draft available', coverLetterState?.draft?.generated_at || new Date().toISOString())
      : null,
    ...persistedEvents,
  ]
    .filter(Boolean)
    .sort((left, right) => right.timestamp - left.timestamp)

  return events.length > 0
    ? events
    : [
        {
          type: 'pending',
          label: 'Workflow history will appear here',
          value: '',
          timestamp: 0,
          dateLabel: 'No timeline data yet',
          detail: '',
        },
      ]
}

export function isFollowUpDue(job) {
  return followUpState(job, defaultWorkflowState(job)).needsAttention
}

function demoNarrativeScore(job) {
  if (!job) {
    return -1
  }

  let score = Number(job.fit_score ?? -1)
  if (job.score_rationale) {
    score += 8
  }
  if (job.application_tips) {
    score += 6
  }
  if (job.cover_letter_angle) {
    score += 6
  }
  if (Array.isArray(job.gaps) && job.gaps.length > 0) {
    score += 5
  }
  if (Array.isArray(job.matching_skills) && job.matching_skills.length > 0) {
    score += 5
  }
  if (job.dismissed || job.status === 'dismissed') {
    score -= 100
  }
  if (job.applied || job.status === 'applied') {
    score -= 10
  }
  return score
}

export function preferredDemoJob(jobs = []) {
  return [...jobs]
    .filter(Boolean)
    .sort((left, right) => demoNarrativeScore(right) - demoNarrativeScore(left))[0] || null
}
