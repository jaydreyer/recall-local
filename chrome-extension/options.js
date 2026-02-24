import { buildApiUrl, loadExtensionConfig, saveExtensionConfig } from "./shared.js";

const refs = {
  form: document.getElementById("settings-form"),
  apiBaseUrl: document.getElementById("api-base-url"),
  apiKey: document.getElementById("api-key"),
  save: document.getElementById("save-settings"),
  testConnection: document.getElementById("test-connection"),
  status: document.getElementById("options-status")
};

function setStatus(message, level = "muted") {
  refs.status.textContent = message;
  refs.status.className = `status ${level}`;
}

async function hydrateForm() {
  const config = await loadExtensionConfig();
  refs.apiBaseUrl.value = config.apiBaseUrl;
  refs.apiKey.value = config.apiKey;
}

function formConfig() {
  return {
    apiBaseUrl: refs.apiBaseUrl.value.trim(),
    apiKey: refs.apiKey.value.trim()
  };
}

async function testEndpoint(url, headers) {
  const response = await fetch(url, { method: "GET", headers });
  let body = {};
  try {
    body = await response.json();
  } catch (_ignored) {
    body = {};
  }
  if (!response.ok) {
    const detail = body?.error?.message || `status ${response.status}`;
    throw new Error(`${url} -> ${detail}`);
  }
  return body;
}

refs.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  refs.save.disabled = true;
  try {
    await saveExtensionConfig(formConfig());
    setStatus("Settings saved to chrome.storage.local.", "ok");
  } catch (error) {
    setStatus(`Save failed: ${error.message}`, "error");
  } finally {
    refs.save.disabled = false;
  }
});

refs.testConnection.addEventListener("click", async () => {
  refs.testConnection.disabled = true;
  setStatus("Testing bridge health and auto-tag endpoint...", "muted");

  const config = formConfig();
  const headers = {};
  if (config.apiKey) {
    headers["X-API-Key"] = config.apiKey;
  }

  try {
    const healthUrl = buildApiUrl(config.apiBaseUrl, "/v1/healthz");
    const tagRulesUrl = buildApiUrl(config.apiBaseUrl, "/v1/auto-tag-rules");
    await testEndpoint(healthUrl, headers);
    const rules = await testEndpoint(tagRulesUrl, headers);
    const groupCount = Array.isArray(rules.groups) ? rules.groups.length : 0;
    setStatus(`Connection OK. Auto-tag groups available: ${groupCount}.`, "ok");
  } catch (error) {
    setStatus(`Connection check failed: ${error.message}`, "error");
  } finally {
    refs.testConnection.disabled = false;
  }
});

hydrateForm()
  .then(() => setStatus("Settings loaded. Save after edits to update extension behavior.", "muted"))
  .catch((error) => setStatus(`Failed to load settings: ${error.message}`, "error"));

