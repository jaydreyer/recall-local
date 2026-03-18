import { useEffect, useMemo, useState } from 'react'

import { readCachedJson, writeCachedJson } from '../lib/cache'

const WORKFLOW_STATE_CACHE_KEY = 'daily-dashboard-workflow-state-v1'

const DEFAULT_PACKET = {
  tailoredSummary: false,
  resumeBullets: false,
  coverLetterDraft: false,
  outreachNote: false,
  interviewBrief: false,
  talkingPoints: false,
}

function ensureEntry(entry = {}) {
  return {
    nextActionApproval: entry.nextActionApproval || 'pending',
    packetApproval: entry.packetApproval || 'pending',
    packet: {
      ...DEFAULT_PACKET,
      ...(entry.packet || {}),
    },
  }
}

export function useWorkflowDemoState(jobId, coverLetterState) {
  const [allState, setAllState] = useState(() => readCachedJson(WORKFLOW_STATE_CACHE_KEY, {}))

  const entry = useMemo(() => ensureEntry(jobId ? allState?.[jobId] : {}), [allState, jobId])

  useEffect(() => {
    writeCachedJson(WORKFLOW_STATE_CACHE_KEY, allState)
  }, [allState])

  useEffect(() => {
    if (!jobId || coverLetterState?.jobId !== jobId || !coverLetterState?.draft?.draft) {
      return
    }

    setAllState((current) => {
      const existing = ensureEntry(current?.[jobId])
      if (existing.packet.coverLetterDraft) {
        return current
      }
      return {
        ...current,
        [jobId]: {
          ...existing,
          packet: {
            ...existing.packet,
            coverLetterDraft: true,
          },
        },
      }
    })
  }, [jobId, coverLetterState?.jobId, coverLetterState?.draft])

  function updateEntry(updater) {
    if (!jobId) {
      return
    }
    setAllState((current) => {
      const existing = ensureEntry(current?.[jobId])
      return {
        ...current,
        [jobId]: updater(existing),
      }
    })
  }

  return {
    workflowState: entry,
    setNextActionApproval(value) {
      updateEntry((existing) => ({
        ...existing,
        nextActionApproval: value,
      }))
    },
    setPacketApproval(value) {
      updateEntry((existing) => ({
        ...existing,
        packetApproval: value,
      }))
    },
    togglePacketItem(key) {
      updateEntry((existing) => ({
        ...existing,
        packet: {
          ...existing.packet,
          [key]: !existing.packet[key],
        },
      }))
    },
  }
}
