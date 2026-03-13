const FALLBACK_MATCH = 'No evidence-backed match captured yet.'
const FALLBACK_GAP = 'No priority gap captured.'
const FALLBACK_ANGLE = 'Open the dossier for the full evaluation context.'

function normalizeText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim()
}

function clampText(value, maxLength = 120) {
  const normalized = normalizeText(value)
  if (!normalized) {
    return ''
  }
  if (normalized.length <= maxLength) {
    return normalized
  }
  const budget = Math.max(0, maxLength - 3)
  const truncated = normalized.slice(0, budget).trimEnd()
  const lastSpace = truncated.lastIndexOf(' ')
  const safeCut = lastSpace >= Math.max(12, Math.floor(budget * 0.6)) ? truncated.slice(0, lastSpace) : truncated
  return `${safeCut.trimEnd()}...`
}

function firstSentence(value) {
  const normalized = normalizeText(value)
  if (!normalized) {
    return ''
  }
  const match = normalized.match(/.+?[.!?](?=\s|$)/)
  return match ? match[0].trim() : normalized
}

function firstMatchItem(job) {
  const skills = Array.isArray(job?.matching_skills) ? job.matching_skills : []
  return skills[0] || null
}

function firstGapItem(job) {
  const gaps = Array.isArray(job?.gaps) ? job.gaps : []
  return gaps[0] || null
}

export function summarizeTopMatch(job, { includeEvidence = true, maxLength = 96 } = {}) {
  const item = firstMatchItem(job)
  if (!item) {
    return FALLBACK_MATCH
  }
  if (typeof item === 'string') {
    return clampText(item, maxLength) || FALLBACK_MATCH
  }
  const label = normalizeText(item.skill || item.name || item.label)
  const evidence = includeEvidence ? firstSentence(item.evidence) : ''
  const summary = label && evidence ? `${label} from ${evidence}` : label || evidence
  return clampText(summary, maxLength) || FALLBACK_MATCH
}

export function summarizeTopGap(job, { includeSeverity = true, maxLength = 96 } = {}) {
  const item = firstGapItem(job)
  if (!item) {
    return FALLBACK_GAP
  }
  if (typeof item === 'string') {
    return clampText(item, maxLength) || FALLBACK_GAP
  }
  const label = normalizeText(item.gap || item.skill || item.name || item.label)
  const severity = includeSeverity ? normalizeText(item.severity) : ''
  const summary = label && severity ? `${label} (${severity})` : label || severity
  return clampText(summary, maxLength) || FALLBACK_GAP
}

export function summarizeAngle(job, { maxLength = 140 } = {}) {
  const primary = firstSentence(job?.cover_letter_angle)
  const fallback = firstSentence(job?.application_tips) || firstSentence(job?.score_rationale)
  return clampText(primary || fallback, maxLength) || FALLBACK_ANGLE
}

export function summarizeAlertField(value, maxLength = 88) {
  return clampText(firstSentence(value), maxLength)
}
