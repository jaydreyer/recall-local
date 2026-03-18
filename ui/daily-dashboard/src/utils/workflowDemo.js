function effectiveStatus(job) {
  if (job?.applied || job?.status === 'applied') {
    return 'applied'
  }
  if (job?.dismissed || job?.status === 'dismissed') {
    return 'dismissed'
  }
  return String(job?.status || 'new').toLowerCase()
}

function hasDraft(job, coverLetterState) {
  if (coverLetterState?.jobId === job?.jobId && coverLetterState?.draft?.draft) {
    return true
  }
  return Boolean(job?.cover_letter_angle)
}

function packetCompletion(packet = {}) {
  return Object.values(packet).filter(Boolean).length
}

export function deriveWorkflow(job, coverLetterState, workflowState = null) {
  const status = effectiveStatus(job)
  const fitScore = Number(job?.fit_score ?? -1)
  const draftGenerated = hasDraft(job, coverLetterState) || Boolean(workflowState?.packet?.coverLetterDraft)
  const highFit = fitScore >= 75
  const evaluated = fitScore >= 0 && status !== 'new'
  const packetDone = packetCompletion(workflowState?.packet) > 0
  const nextActionApproval = workflowState?.nextActionApproval || 'pending'
  const packetApproval = workflowState?.packetApproval || 'pending'

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
    }
  }

  if (status === 'applied') {
    return {
      state: 'applied',
      stateLabel: 'Applied',
      nextAction: 'follow_up',
      nextActionLabel: 'Prepare follow-up',
      blocker: 'Follow-up not scheduled',
      blockerTone: 'warning',
      packetStatus: draftGenerated ? 'draft_generated' : 'not_started',
      packetLabel: draftGenerated ? 'Draft generated' : 'Not started',
      approvalLabel: packetApproval === 'approved' ? 'Packet approved' : 'Application recorded',
      priorityLabel: 'Keep momentum',
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
  }
}

function buildEvent(type, label, value) {
  if (!value) {
    return null
  }
  const parsed = new Date(value)
  return {
    type,
    label,
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
  const events = [
    buildEvent('discovered', 'Role discovered', job?.discovered_at || job?.date_posted),
    buildEvent('evaluated', 'Role evaluated', job?.evaluated_at),
    job?.applied || job?.status === 'applied' ? buildEvent('applied', 'Moved to applied', job?.applied_at || job?.evaluated_at) : null,
    hasDraft(job, coverLetterState)
      ? buildEvent('draft', 'Cover letter draft available', coverLetterState?.draft?.generated_at || new Date().toISOString())
      : null,
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
        },
      ]
}
