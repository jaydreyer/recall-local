import {
  buildApiUrl,
  detectGroupAndTags,
  fetchAutoTagRules,
  iconTokenToGlyph,
  loadExtensionConfig,
  sanitizeTag,
  uniqueStrings
} from "./shared.js";

const state = {
  activeTab: null,
  rules: null,
  config: null,
  group: "reference",
  tags: [],
  selectionText: "",
  rulesWarning: "",
  gmailPrefill: null
};

const GMAIL_PREFILL_STORAGE_KEY = "recall_gmail_prefill";
const GMAIL_PREFILL_MAX_AGE_MS = 10 * 60 * 1000;

const refs = {
  status: document.getElementById("status-message"),
  pageTitle: document.getElementById("page-title"),
  pageUrl: document.getElementById("page-url"),
  groupList: document.getElementById("group-list"),
  tagList: document.getElementById("tag-list"),
  tagInput: document.getElementById("tag-input"),
  addTag: document.getElementById("add-tag"),
  suggestedTags: document.getElementById("suggested-tags"),
  includeSelection: document.getElementById("include-selection"),
  saveToVault: document.getElementById("save-to-vault"),
  selectionPreview: document.getElementById("selection-preview"),
  captureButton: document.getElementById("capture-btn"),
  captureFeedback: document.getElementById("capture-feedback"),
  cancelButton: document.getElementById("cancel-btn"),
  optionsButton: document.getElementById("open-options")
};

let popupFitTimer = null;
let captureFeedbackClearTimer = null;

function updateStatus(message, level = "muted") {
  refs.status.textContent = message;
  refs.status.className = `status ${level}`;
  schedulePopupFit();
}

function sanitizeSelection(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function setCaptureFeedback(message, level = "muted", { clearAfterMs = 0 } = {}) {
  if (!refs.captureFeedback) {
    return;
  }
  refs.captureFeedback.textContent = String(message || "");
  refs.captureFeedback.className = `capture-feedback ${level}`;

  if (captureFeedbackClearTimer) {
    clearTimeout(captureFeedbackClearTimer);
    captureFeedbackClearTimer = null;
  }
  if (clearAfterMs > 0) {
    captureFeedbackClearTimer = setTimeout(() => {
      refs.captureFeedback.textContent = "";
      refs.captureFeedback.className = "capture-feedback muted";
      captureFeedbackClearTimer = null;
      schedulePopupFit();
    }, clearAfterMs);
  }
  schedulePopupFit();
}

function fitPopupHeight() {
  const panel = document.querySelector(".panel");
  if (!panel) {
    return;
  }

  const minHeight = 520;
  const maxHeight = Math.max(560, Math.min(920, window.screen.availHeight - 72));
  const targetHeight = Math.min(maxHeight, Math.max(minHeight, panel.scrollHeight + 2));
  document.documentElement.style.height = `${targetHeight}px`;
  document.body.style.height = `${targetHeight}px`;
}

function schedulePopupFit() {
  if (popupFitTimer) {
    clearTimeout(popupFitTimer);
  }
  popupFitTimer = setTimeout(() => {
    popupFitTimer = null;
    fitPopupHeight();
  }, 0);
}

async function activeTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs?.[0] || null;
}

async function readSelectedText(tabId) {
  if (!Number.isInteger(tabId)) {
    return "";
  }

  try {
    const [result] = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => String(window.getSelection()?.toString() || "")
    });
  return sanitizeSelection(result?.result || "");
  } catch (_error) {
    return "";
  }
}

function isGmailTab(url) {
  try {
    const parsed = new URL(String(url || ""));
    return parsed.hostname === "mail.google.com";
  } catch (_error) {
    return false;
  }
}

function getStorage(keys) {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get(keys, (result) => {
      const runtimeError = chrome.runtime.lastError;
      if (runtimeError) {
        reject(new Error(runtimeError.message));
        return;
      }
      resolve(result || {});
    });
  });
}

function removeStorage(keys) {
  return new Promise((resolve, reject) => {
    chrome.storage.local.remove(keys, () => {
      const runtimeError = chrome.runtime.lastError;
      if (runtimeError) {
        reject(new Error(runtimeError.message));
        return;
      }
      resolve();
    });
  });
}

async function loadAndConsumeGmailPrefill() {
  if (!isGmailTab(state.activeTab?.url)) {
    return null;
  }

  const data = await getStorage([GMAIL_PREFILL_STORAGE_KEY]);
  const prefill = data?.[GMAIL_PREFILL_STORAGE_KEY];
  if (!prefill || typeof prefill !== "object") {
    return null;
  }

  const createdAt = Number(prefill.createdAt || 0);
  const now = Date.now();
  if (!createdAt || now - createdAt > GMAIL_PREFILL_MAX_AGE_MS) {
    await removeStorage([GMAIL_PREFILL_STORAGE_KEY]);
    return null;
  }

  await removeStorage([GMAIL_PREFILL_STORAGE_KEY]);
  return prefill;
}

function sendMessageToTab(tabId, message) {
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, message, (response) => {
      const runtimeError = chrome.runtime.lastError;
      if (runtimeError) {
        resolve({ ok: false, runtimeError: runtimeError.message, response: null });
        return;
      }
      resolve({ ok: true, runtimeError: "", response: response || null });
    });
  });
}

function injectGmailContentScript(tabId) {
  return new Promise((resolve) => {
    chrome.scripting.executeScript(
      {
        target: { tabId },
        files: ["gmail.js"]
      },
      () => {
        const runtimeError = chrome.runtime.lastError;
        if (runtimeError) {
          resolve({ ok: false, error: runtimeError.message });
          return;
        }
        resolve({ ok: true, error: "" });
      }
    );
  });
}

async function requestGmailPrefillFromTab(tabId) {
  if (!Number.isInteger(tabId)) {
    return null;
  }

  const firstAttempt = await sendMessageToTab(tabId, { type: "recall_build_gmail_prefill" });
  const firstResponse = firstAttempt.response;
  if (firstAttempt.ok && firstResponse?.ok === true && firstResponse.payload && typeof firstResponse.payload === "object") {
    return firstResponse.payload;
  }

  if (!firstAttempt.ok) {
    await injectGmailContentScript(tabId);
    const secondAttempt = await sendMessageToTab(tabId, { type: "recall_build_gmail_prefill" });
    const secondResponse = secondAttempt.response;
    if (secondAttempt.ok && secondResponse?.ok === true && secondResponse.payload && typeof secondResponse.payload === "object") {
      return secondResponse.payload;
    }
  }

  return null;
}

function renderContext() {
  const title = state.activeTab?.title || "Untitled page";
  const url = state.activeTab?.url || "No active tab URL";
  refs.pageTitle.textContent = title;
  refs.pageUrl.textContent = url;
  schedulePopupFit();
}

function selectedGroupStyle(group) {
  if (state.group !== group.id) {
    return "";
  }
  const color = group.color || "#f59e0b";
  return `background: ${color}2a; border-color: ${color}88;`;
}

function renderGroupButtons() {
  const groups = Array.isArray(state.rules?.groups) ? state.rules.groups : [];
  refs.groupList.innerHTML = "";

  for (const group of groups) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "group-button" + (state.group === group.id ? " active" : "");
    button.setAttribute("style", selectedGroupStyle(group));

    const glyph = document.createElement("span");
    glyph.className = "group-glyph";
    glyph.textContent = iconTokenToGlyph(group.icon);
    if (group.color) {
      glyph.style.background = `${group.color}2a`;
      glyph.style.color = group.color;
    }

    const label = document.createElement("span");
    label.textContent = group.label || group.id;

    button.appendChild(glyph);
    button.appendChild(label);
    button.addEventListener("click", () => {
      state.group = group.id;
      renderGroupButtons();
      renderSuggestedTags();
    });
    refs.groupList.appendChild(button);
  }
  schedulePopupFit();
}

function removeTag(tagToRemove) {
  state.tags = state.tags.filter((tag) => tag !== tagToRemove);
  renderTags();
  renderSuggestedTags();
}

function renderTags() {
  refs.tagList.innerHTML = "";
  if (!state.tags.length) {
    const empty = document.createElement("span");
    empty.className = "section-note";
    empty.textContent = "No tags selected";
    refs.tagList.appendChild(empty);
    return;
  }

  for (const tag of state.tags) {
    const chip = document.createElement("span");
    chip.className = "tag-chip";
    chip.textContent = tag;

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "tag-remove";
    remove.textContent = "x";
    remove.setAttribute("aria-label", `Remove ${tag}`);
    remove.addEventListener("click", () => removeTag(tag));

    chip.appendChild(remove);
    refs.tagList.appendChild(chip);
  }
  schedulePopupFit();
}

function addTag(rawValue) {
  const normalized = sanitizeTag(rawValue);
  if (!normalized) {
    return;
  }
  state.tags = uniqueStrings([...state.tags, normalized]);
  refs.tagInput.value = "";
  renderTags();
  renderSuggestedTags();
}

function renderSuggestedTags() {
  refs.suggestedTags.innerHTML = "";
  const suggestions = state.rules?.suggested_tags?.[state.group] || [];
  const filtered = suggestions
    .map((tag) => sanitizeTag(tag))
    .filter((tag) => tag && !state.tags.includes(tag))
    .slice(0, 8);

  for (const tag of filtered) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "suggested-button";
    button.textContent = `+ ${tag}`;
    button.addEventListener("click", () => addTag(tag));
    refs.suggestedTags.appendChild(button);
  }
  schedulePopupFit();
}

function renderSelectionPreview() {
  if (!state.selectionText) {
    refs.includeSelection.checked = false;
    refs.includeSelection.disabled = true;
    refs.selectionPreview.textContent = "No active text selection detected.";
    schedulePopupFit();
    return;
  }

  refs.includeSelection.disabled = false;
  refs.includeSelection.checked = true;
  refs.selectionPreview.textContent = state.selectionText;
  schedulePopupFit();
}

function requestHeaders() {
  const headers = { "Content-Type": "application/json" };
  if (state.config?.apiKey) {
    headers["X-API-Key"] = state.config.apiKey;
  }
  return headers;
}

async function submitCapture() {
  if (!state.activeTab?.url) {
    updateStatus("No active URL available for capture.", "error");
    setCaptureFeedback("No active URL available for capture.", "error");
    return;
  }

  const originalButtonLabel = refs.captureButton.textContent;
  refs.captureButton.disabled = true;
  refs.captureButton.textContent = "Sending...";
  updateStatus("Sending to Recall.local...", "muted");
  setCaptureFeedback("Sending capture...", "muted");

  const payload = {
    channel: state.gmailPrefill ? "gmail-forward" : "bookmarklet",
    source: state.gmailPrefill ? "chrome-extension-gmail" : "chrome-extension-popup",
    url: state.activeTab.url,
    title: state.activeTab.title || "Untitled page",
    group: state.group,
    tags: uniqueStrings(state.tags.map(sanitizeTag).filter(Boolean)),
    save_to_vault: Boolean(refs.saveToVault?.checked)
  };

  if (state.gmailPrefill) {
    payload.subject = state.gmailPrefill.subject || state.activeTab.title || "";
    payload.from = state.gmailPrefill.senderEmail || "";
    payload.text = state.selectionText || state.gmailPrefill.bodyText || "";
    payload.metadata = {
      email_from_name: state.gmailPrefill.senderName || "",
      attachment_names: Array.isArray(state.gmailPrefill.attachmentNames) ? state.gmailPrefill.attachmentNames : []
    };
  } else if (refs.includeSelection.checked && state.selectionText) {
    payload.text = state.selectionText;
  }

  try {
    const endpoint = buildApiUrl(state.config.apiBaseUrl, "/v1/ingestions");
    const response = await fetch(endpoint, {
      method: "POST",
      headers: requestHeaders(),
      body: JSON.stringify(payload)
    });
    let body = {};
    try {
      body = await response.json();
    } catch (_ignored) {
      body = {};
    }

    if (!response.ok) {
      const detail = body?.error?.message || `Capture failed (${response.status})`;
      throw new Error(detail);
    }

    const ingestedCount = Array.isArray(body.ingested) ? body.ingested.length : 0;
    refs.captureButton.textContent = "Sent";
    updateStatus(`Capture sent successfully (${ingestedCount} item${ingestedCount === 1 ? "" : "s"}).`, "ok");
    setCaptureFeedback(
      `Ingested ${ingestedCount} item${ingestedCount === 1 ? "" : "s"} successfully.`,
      "ok",
      { clearAfterMs: 6000 }
    );
  } catch (error) {
    refs.captureButton.textContent = "Retry";
    updateStatus(error.message, "error");
    setCaptureFeedback(error.message, "error");
  } finally {
    setTimeout(() => {
      refs.captureButton.textContent = originalButtonLabel || "Ingest";
      refs.captureButton.disabled = false;
      schedulePopupFit();
    }, 900);
  }
}

function bindEvents() {
  refs.addTag.addEventListener("click", () => addTag(refs.tagInput.value));
  refs.tagInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      addTag(refs.tagInput.value);
    }
  });
  refs.captureButton.addEventListener("click", submitCapture);
  refs.cancelButton?.addEventListener("click", () => {
    window.close();
  });
  refs.optionsButton.addEventListener("click", async () => {
    await chrome.runtime.openOptionsPage();
  });
}

async function initialize() {
  bindEvents();
  state.config = await loadExtensionConfig();
  state.activeTab = await activeTab();
  state.selectionText = await readSelectedText(state.activeTab?.id);
  state.gmailPrefill = await loadAndConsumeGmailPrefill();
  if (!state.gmailPrefill && isGmailTab(state.activeTab?.url)) {
    state.gmailPrefill = await requestGmailPrefillFromTab(state.activeTab?.id);
  }
  if (state.gmailPrefill) {
    if (state.gmailPrefill.url) {
      state.activeTab = {
        ...(state.activeTab || {}),
        url: state.gmailPrefill.url
      };
    }
    if (state.gmailPrefill.subject) {
      state.activeTab = {
        ...(state.activeTab || {}),
        title: state.gmailPrefill.subject
      };
    }
    if (state.gmailPrefill.bodyText) {
      state.selectionText = sanitizeSelection(state.gmailPrefill.bodyText);
    }
  }
  renderContext();
  renderSelectionPreview();

  const { rules, warning } = await fetchAutoTagRules(state.config);
  state.rules = rules;
  state.rulesWarning = warning;

  const detected = detectGroupAndTags(
    {
      url: state.activeTab?.url || "",
      title: state.activeTab?.title || ""
    },
    rules
  );

  const prefillGroup = sanitizeTag(state.gmailPrefill?.group || "");
  const prefillTags = Array.isArray(state.gmailPrefill?.tags) ? state.gmailPrefill.tags : [];
  state.group = prefillGroup || detected.group || "reference";
  state.tags = uniqueStrings(
    [...(detected.tags || []), ...prefillTags]
      .map(sanitizeTag)
      .filter(Boolean)
  );

  renderGroupButtons();
  renderTags();
  renderSuggestedTags();

  if (state.gmailPrefill) {
    updateStatus(`Gmail prefill loaded for ${state.gmailPrefill.senderEmail || "message sender"}.`, "ok");
    setCaptureFeedback("Ready to ingest this Gmail message.", "muted");
    schedulePopupFit();
    return;
  }

  if (warning) {
    updateStatus(`${warning}. Using fallback rules.`, "warn");
    setCaptureFeedback("Ready to ingest with fallback auto-tag rules.", "warn");
    schedulePopupFit();
    return;
  }
  updateStatus(`Connected to ${state.config.apiBaseUrl}`, "ok");
  setCaptureFeedback("Ready to ingest.", "muted");
  schedulePopupFit();
}

initialize().catch((error) => {
  updateStatus(`Popup init failed: ${error.message}`, "error");
});
