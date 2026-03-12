import { useEffect, useState } from 'react'

import { fetchLLMSettings, updateLLMSettings } from '../api'
import { readCachedJson, writeCachedJson } from '../lib/cache'

const SETTINGS_CACHE_KEY = 'daily-dashboard-settings-snapshot-v1'
const SETTINGS_REFRESH_INTERVAL_MS = 300000

export function useSettings({ enabled = false } = {}) {
  const cachedState = readCachedJson(SETTINGS_CACHE_KEY, {})
  const [settings, setSettings] = useState(cachedState.settings || null)
  const [loading, setLoading] = useState(enabled && !cachedState.settings)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [dataSource, setDataSource] = useState(cachedState.settings ? 'cache' : 'live')

  async function loadSettings({ background = false } = {}) {
    if (!background || !settings) {
      setLoading(true)
    }
    setError('')
    try {
      const payload = await fetchLLMSettings()
      const nextSettings = payload.settings || null
      setSettings(nextSettings)
      setDataSource('live')
      writeCachedJson(SETTINGS_CACHE_KEY, { settings: nextSettings })
    } catch (loadError) {
      const message = loadError.message || 'Unable to load settings.'
      if (settings) {
        setDataSource('cache')
        setError(`Showing cached settings. Live refresh failed: ${message}`)
      } else {
        setError(message)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (enabled) {
      loadSettings({ background: Boolean(cachedState.settings) })
    }
  }, [enabled])

  useEffect(() => {
    if (typeof window === 'undefined' || !enabled) {
      return undefined
    }

    const intervalId = window.setInterval(() => {
      if (!document.hidden) {
        loadSettings({ background: true })
      }
    }, SETTINGS_REFRESH_INTERVAL_MS)

    function handleForegroundRefresh() {
      loadSettings({ background: true })
    }

    window.addEventListener('focus', handleForegroundRefresh)
    window.addEventListener('online', handleForegroundRefresh)

    return () => {
      window.clearInterval(intervalId)
      window.removeEventListener('focus', handleForegroundRefresh)
      window.removeEventListener('online', handleForegroundRefresh)
    }
  }, [enabled, settings])

  async function saveSettings(patch) {
    setSaving(true)
    setError('')
    try {
      const payload = await updateLLMSettings(patch)
      const nextSettings = payload.settings || null
      setSettings(nextSettings)
      setDataSource('live')
      writeCachedJson(SETTINGS_CACHE_KEY, { settings: nextSettings })
      return nextSettings
    } catch (saveError) {
      setError(saveError.message || 'Unable to save settings.')
      return null
    } finally {
      setSaving(false)
    }
  }

  return {
    settings,
    loading,
    saving,
    error,
    dataSource,
    refresh: loadSettings,
    saveSettings,
  }
}
