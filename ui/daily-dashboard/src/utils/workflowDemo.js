export const WORKFLOW_STAGES = ['focus', 'review', 'follow_up', 'monitor', 'closed']
export const FOLLOW_UP_STATUSES = ['not_scheduled', 'scheduled', 'completed']
export const NEXT_ACTIONS = ['none', 'review_role', 'tailor_resume', 'hold', 'skip', 'follow_up', 'monitor_response', 'schedule_follow_up', 'send_follow_up']

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

function titleCaseAction(value) {
  return String(value || '')
    .split('_')
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(' ')
}

function nextActionState(job, workflowState, fallback) {
  const raw = workflowState?.nextAction || {}
  const action = NEXT_ACTIONS.includes(raw.action) ? raw.action : fallback.action
  const rationale = raw.rationale || fallback.rationale || null
  const confidence = raw.confidence || fallback.confidence || null
  const dueAt = raw.dueAt || fallback.dueAt || null

  return {
    action,
    label: fallback.action === action ? fallback.label : titleCaseAction(action),
    rationale,
    confidence,
    dueAt,
    dueLabel: dueAt ? formatDateTime(dueAt, 'Not set') : 'Not set',
  }
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
    nextAction: {
      action: job?.workflow?.nextAction?.action || null,
      rationale: job?.workflow?.nextAction?.rationale || null,
      confidence: job?.workflow?.nextAction?.confidence || null,
      dueAt: job?.workflow?.nextAction?.dueAt || null,
    },
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
    const nextActionStateValue = nextActionState(job, effectiveWorkflow, {
      action: 'none',
      label: 'Closed out',
      rationale: 'This role is archived, so no further workflow action is needed.',
      confidence: 'high',
      dueAt: null,
    })
    return {
      state: 'closed',
      stateLabel: 'Closed',
      nextAction: nextActionStateValue.action,
      nextActionLabel: nextActionStateValue.label,
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
      nextActionRationale: nextActionStateValue.rationale,
      nextActionConfidence: nextActionStateValue.confidence,
      nextActionDueLabel: nextActionStateValue.dueLabel,
      nextActionDueAt: nextActionStateValue.dueAt,
    }
  }

  if (status === 'applied') {
    const nextActionStateValue = nextActionState(job, effectiveWorkflow, {
      action:
        followUp.status === 'completed'
          ? 'monitor_response'
          : followUp.isDue
            ? 'send_follow_up'
            : followUp.status === 'scheduled'
              ? 'follow_up'
              : 'schedule_follow_up',
      label:
        followUp.status === 'completed'
          ? 'Monitor response'
          : followUp.isDue
            ? 'Send follow-up'
            : followUp.status === 'scheduled'
              ? 'Hold until follow-up date'
              : 'Schedule follow-up',
      rationale:
        followUp.status === 'completed'
          ? 'The follow-up was already sent, so the next step is to watch for a response.'
          : followUp.isDue
            ? 'The role is already in follow-up and the due date has arrived.'
            : followUp.status === 'scheduled'
              ? 'A follow-up is already planned, so the best move is to wait until it is due.'
              : 'The application is recorded, but there is no follow-up date scheduled yet.',
      confidence: followUp.isDue || followUp.status === 'completed' ? 'high' : 'medium',
      dueAt: followUp.dueAt || null,
    })
    return {
      state: 'applied',
      stateLabel: 'Applied',
      nextAction: nextActionStateValue.action,
      nextActionLabel: nextActionStateValue.label,
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
      nextActionRationale: nextActionStateValue.rationale,
      nextActionConfidence: nextActionStateValue.confidence,
      nextActionDueLabel: nextActionStateValue.dueLabel,
      nextActionDueAt: nextActionStateValue.dueAt,
    }
  }

  if (status === 'new' || !evaluated) {
    const nextActionStateValue = nextActionState(job, effectiveWorkflow, {
      action: 'review_role',
      label: 'Review role',
      rationale: 'This role still needs evaluation before packet work or approvals should begin.',
      confidence: 'high',
      dueAt: null,
    })
    return {
      state: 'new',
      stateLabel: 'New',
      nextAction: nextActionStateValue.action,
      nextActionLabel: nextActionStateValue.label,
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
      nextActionRationale: nextActionStateValue.rationale,
      nextActionConfidence: nextActionStateValue.confidence,
      nextActionDueLabel: nextActionStateValue.dueLabel,
      nextActionDueAt: nextActionStateValue.dueAt,
    }
  }

  if (highFit) {
    const nextActionStateValue = nextActionState(job, effectiveWorkflow, {
      action: 'tailor_resume',
      label: 'Tailor resume',
      rationale:
        nextActionApproval === 'approved'
          ? 'This role is a strong fit and is ready for packet work before application.'
          : 'This role is a strong fit, but the next step should be reviewed before packet work moves forward.',
      confidence: 'high',
      dueAt: null,
    })
    return {
      state: 'target',
      stateLabel: 'Target',
      nextAction: nextActionStateValue.action,
      nextActionLabel: nextActionStateValue.label,
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
      nextActionRationale: nextActionStateValue.rationale,
      nextActionConfidence: nextActionStateValue.confidence,
      nextActionDueLabel: nextActionStateValue.dueLabel,
      nextActionDueAt: nextActionStateValue.dueAt,
    }
  }

  const nextActionStateValue = nextActionState(job, effectiveWorkflow, {
    action: fitScore >= 50 ? 'hold' : 'skip',
    label: fitScore >= 50 ? 'Hold for later' : 'Skip for now',
    rationale:
      fitScore >= 50
        ? 'The role is viable but not strong enough to move into the focus queue right now.'
        : 'The fit score is below the current threshold, so this role should not take priority.',
    confidence: fitScore >= 50 ? 'medium' : 'high',
    dueAt: null,
  })
  return {
    state: 'reviewed',
    stateLabel: 'Reviewed',
    nextAction: nextActionStateValue.action,
    nextActionLabel: nextActionStateValue.label,
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
    nextActionRationale: nextActionStateValue.rationale,
    nextActionConfidence: nextActionStateValue.confidence,
    nextActionDueLabel: nextActionStateValue.dueLabel,
    nextActionDueAt: nextActionStateValue.dueAt,
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
