import {
  buildApiUrl,
  detectGroupAndTags,
  fetchAutoTagRules,
  loadExtensionConfig,
  saveExtensionConfig,
  sanitizeTag,
  uniqueStrings
} from "./shared.js";

const MENU_IDS = {
  page: "recall_capture_page",
  link: "recall_capture_link",
  selection: "recall_capture_selection"
};

const BADGE_COLORS = {
  success: "#0f766e",
  error: "#991b1b",
  info: "#1d4ed8"
};

function setBadge(tabId, text, color, timeoutMs = 2400) {
  if (!Number.isInteger(tabId) || tabId < 0) {
    return;
  }
  chrome.action.setBadgeBackgroundColor({ tabId, color }, () => {});
  chrome.action.setBadgeText({ tabId, text }, () => {});
  setTimeout(() => {
    chrome.action.setBadgeText({ tabId, text: "" }, () => {});
  }, timeoutMs);
}

function createContextMenus() {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: MENU_IDS.page,
      title: "Send page to Recall.local",
      contexts: ["page"]
    });
    chrome.contextMenus.create({
      id: MENU_IDS.link,
      title: "Send link to Recall.local",
      contexts: ["link"]
    });
    chrome.contextMenus.create({
      id: MENU_IDS.selection,
      title: "Send selection to Recall.local",
      contexts: ["selection"]
    });
  });
}

async function ensureDefaultConfig() {
  try {
    const config = await loadExtensionConfig();
    await saveExtensionConfig(config);
  } catch (error) {
    console.warn("Failed to initialize extension config:", error);
  }
}

function requestHeaders(config) {
  const headers = { "Content-Type": "application/json" };
  if (config?.apiKey) {
    headers["X-API-Key"] = config.apiKey;
  }
  return headers;
}

async function postIngestion({ url, title, text, sourceLabel }) {
  const config = await loadExtensionConfig();
  const { rules } = await fetchAutoTagRules(config);
  const detected = detectGroupAndTags({ url, title }, rules);

  const payload = {
    channel: "bookmarklet",
    url: url || "",
    title: title || "Untitled page",
    source: sourceLabel || "chrome-extension",
    group: detected.group,
    tags: uniqueStrings((detected.tags || []).map(sanitizeTag).filter(Boolean))
  };

  if (text) {
    payload.text = text;
  }

  const endpoint = buildApiUrl(config.apiBaseUrl, "/v1/ingestions");
  const response = await fetch(endpoint, {
    method: "POST",
    headers: requestHeaders(config),
    body: JSON.stringify(payload)
  });

  let body = null;
  try {
    body = await response.json();
  } catch (_ignored) {
    body = null;
  }

  if (!response.ok) {
    const detail = body?.error?.message || `Request failed with status ${response.status}`;
    throw new Error(detail);
  }

  return body;
}

async function tabById(tabId) {
  if (!Number.isInteger(tabId)) {
    return null;
  }
  return await chrome.tabs.get(tabId);
}

async function handleContextCapture(info, tab) {
  const contextTab = tab || (await tabById(info.tabId));
  const tabId = contextTab?.id;
  const sourceUrl = info.linkUrl || info.pageUrl || contextTab?.url || "";
  const sourceTitle = contextTab?.title || info.selectionText || "Untitled page";
  const selection = info.selectionText ? String(info.selectionText).trim() : "";

  if (!sourceUrl) {
    setBadge(tabId, "ERR", BADGE_COLORS.error);
    return;
  }

  try {
    await postIngestion({
      url: sourceUrl,
      title: sourceTitle,
      text: selection || "",
      sourceLabel: "chrome-context-menu"
    });
    setBadge(tabId, "SENT", BADGE_COLORS.success);
  } catch (error) {
    console.warn("Context capture failed:", error);
    setBadge(tabId, "ERR", BADGE_COLORS.error);
  }
}

chrome.runtime.onInstalled.addListener(async () => {
  createContextMenus();
  await ensureDefaultConfig();
});

chrome.runtime.onStartup.addListener(() => {
  createContextMenus();
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (!Object.values(MENU_IDS).includes(info.menuItemId)) {
    return;
  }
  handleContextCapture(info, tab);
});

chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "open-recall-popup") {
    return;
  }

  try {
    if (chrome.action.openPopup) {
      await chrome.action.openPopup();
      return;
    }
  } catch (error) {
    console.warn("Unable to open popup from command:", error);
  }

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  setBadge(tab?.id, "OPEN", BADGE_COLORS.info);
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "recall_open_popup_from_gmail") {
    return undefined;
  }

  (async () => {
    try {
      if (chrome.action.openPopup) {
        await chrome.action.openPopup();
        sendResponse({ ok: true });
        return;
      }
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      setBadge(tab?.id, "OPEN", BADGE_COLORS.info);
      sendResponse({ ok: true, fallback: true });
    } catch (error) {
      sendResponse({ ok: false, error: String(error?.message || error) });
    }
  })();

  return true;
});
