import { useEffect, useState } from 'react'

import { fetchLLMSettings, updateLLMSettings } from '../api'
import { readCachedJson, writeCachedJson } from '../lib/cache'

const SETTINGS_CACHE_KEY = 'daily-dashboard-settings-snapshot-v1'

export function useSettings({ enabled = false } = {}) {
  const cachedState = readCachedJson(SETTINGS_CACHE_KEY, {})
  const [settings, setSettings] = useState(cachedState.settings || null)
  const [loading, setLoading] = useState(enabled && !cachedState.settings)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function loadSettings() {
    setLoading(true)
    setError('')
    try {
      const payload = await fetchLLMSettings()
      const nextSettings = payload.settings || null
      setSettings(nextSettings)
      writeCachedJson(SETTINGS_CACHE_KEY, { settings: nextSettings })
    } catch (loadError) {
      const message = loadError.message || 'Unable to load settings.'
      if (settings) {
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
      loadSettings()
    }
  }, [enabled])

  async function saveSettings(patch) {
    setSaving(true)
    setError('')
    try {
      const payload = await updateLLMSettings(patch)
      const nextSettings = payload.settings || null
      setSettings(nextSettings)
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
    refresh: loadSettings,
    saveSettings,
  }
}
