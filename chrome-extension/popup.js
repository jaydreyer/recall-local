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
  rulesWarning: ""
};

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
  selectionPreview: document.getElementById("selection-preview"),
  captureButton: document.getElementById("capture-btn"),
  optionsButton: document.getElementById("open-options")
};

function updateStatus(message, level = "muted") {
  refs.status.textContent = message;
  refs.status.className = `status ${level}`;
}

function sanitizeSelection(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
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

function renderContext() {
  const title = state.activeTab?.title || "Untitled page";
  const url = state.activeTab?.url || "No active tab URL";
  refs.pageTitle.textContent = title;
  refs.pageUrl.textContent = url;
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
}

function renderSelectionPreview() {
  if (!state.selectionText) {
    refs.includeSelection.checked = false;
    refs.includeSelection.disabled = true;
    refs.selectionPreview.textContent = "No active text selection detected.";
    return;
  }

  refs.includeSelection.disabled = false;
  refs.includeSelection.checked = true;
  refs.selectionPreview.textContent = state.selectionText;
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
    return;
  }

  refs.captureButton.disabled = true;
  updateStatus("Sending to Recall.local...", "muted");

  const payload = {
    channel: "bookmarklet",
    source: "chrome-extension-popup",
    url: state.activeTab.url,
    title: state.activeTab.title || "Untitled page",
    group: state.group,
    tags: uniqueStrings(state.tags.map(sanitizeTag).filter(Boolean))
  };

  if (refs.includeSelection.checked && state.selectionText) {
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
    updateStatus(`Capture sent successfully (${ingestedCount} item${ingestedCount === 1 ? "" : "s"}).`, "ok");
  } catch (error) {
    updateStatus(error.message, "error");
  } finally {
    refs.captureButton.disabled = false;
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
  refs.optionsButton.addEventListener("click", async () => {
    await chrome.runtime.openOptionsPage();
  });
}

async function initialize() {
  bindEvents();
  state.config = await loadExtensionConfig();
  state.activeTab = await activeTab();
  state.selectionText = await readSelectedText(state.activeTab?.id);
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

  state.group = detected.group || "reference";
  state.tags = uniqueStrings((detected.tags || []).map(sanitizeTag).filter(Boolean));

  renderGroupButtons();
  renderTags();
  renderSuggestedTags();

  if (warning) {
    updateStatus(`${warning}. Using fallback rules.`, "warn");
    return;
  }
  updateStatus(`Connected to ${state.config.apiBaseUrl}`, "ok");
}

initialize().catch((error) => {
  updateStatus(`Popup init failed: ${error.message}`, "error");
});

