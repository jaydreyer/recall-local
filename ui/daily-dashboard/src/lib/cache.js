export function readCachedJson(key, fallback = null) {
  if (typeof window === 'undefined') {
    return fallback
  }
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) {
      return fallback
    }
    return JSON.parse(raw)
  } catch {
    return fallback
  }
}

export function writeCachedJson(key, value) {
  if (typeof window === 'undefined') {
    return
  }
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Ignore quota and serialization failures for non-critical UI cache data.
  }
}
