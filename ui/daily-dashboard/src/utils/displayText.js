const SOURCE_LABELS = {
  career_page: 'Career page',
  chrome_extension: 'Chrome extension',
  jobspy: 'JobSpy',
}

export function displayCompanyName(value, fallback = 'Unknown company') {
  const text = String(value || '').trim()
  if (!text) {
    return fallback
  }

  const normalized = text.toLowerCase()
  if (normalized === 'nan' || normalized === 'none' || normalized === 'null' || normalized === 'undefined') {
    return fallback
  }

  return text
}

export function displaySourceLabel(value) {
  const normalized = String(value || '').trim().toLowerCase()
  if (!normalized) {
    return 'Unknown source'
  }

  if (SOURCE_LABELS[normalized]) {
    return SOURCE_LABELS[normalized]
  }

  return normalized
    .split(/[_-]+/g)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}
