import { useEffect, useState } from 'react'

import { fetchLLMSettings, updateLLMSettings } from '../api'

export function useSettings() {
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function loadSettings() {
    setLoading(true)
    setError('')
    try {
      const payload = await fetchLLMSettings()
      setSettings(payload.settings || null)
    } catch (loadError) {
      setError(loadError.message || 'Unable to load settings.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSettings()
  }, [])

  async function saveSettings(patch) {
    setSaving(true)
    setError('')
    try {
      const payload = await updateLLMSettings(patch)
      setSettings(payload.settings || null)
      return payload.settings || null
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
