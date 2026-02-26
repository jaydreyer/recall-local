(function () {
  if (window.__recallGmailCaptureLoaded) {
    return;
  }
  window.__recallGmailCaptureLoaded = true;

  const STORAGE_API_BASE_KEY = "api_base_url";
  const STORAGE_API_KEY = "api_key";
  const STORAGE_PREFILL_KEY = "recall_gmail_prefill";
  const DEFAULT_API_BASE_URL = "http://localhost:8090";

  const STYLE_ID = "recall-gmail-style";
  const BUTTON_ATTR = "data-recall-gmail-button";
  const BUTTON_CLASS = "recall-gmail-button";
  const SCAN_DEBOUNCE_MS = 250;
  const RESCAN_INTERVAL_MS = 3000;
  const MAX_BODY_CHARS = 12000;
  const PREFILL_MAX_AGE_MS = 10 * 60 * 1000;

  const TOOLBAR_SELECTORS = ['div[gh="tm"]', 'div[role="toolbar"]'];
  const SUBJECT_SELECTORS = ["h2.hP", "h2[data-thread-perm-id]", 'h2[role="heading"]'];
  const SENDER_SELECTORS = ["span[email][name]", "span[email]", "h3 span[email]"];
  const BODY_SELECTORS = ["div.a3s.aiL", "div.a3s", "div[data-message-id] div[dir='ltr']"];
  const ATTACHMENT_SELECTORS = ["span.aV3", "div.aQH span", "span[data-tooltip]"];

  const FALLBACK_RULES = {
    email_senders: {
      "job-search": ["@anthropic.com", "@openai.com", "@lever.co", "@greenhouse.io"]
    },
    url_tag_patterns: {
      "anthropic.com": ["anthropic"],
      "openai.com": ["openai"],
      "cohere.com": ["cohere"],
      "cohere.ai": ["cohere"],
      "glean.com": ["glean"],
      "writer.com": ["writer"]
    }
  };

  let scanTimer = null;

  function sanitizeWhitespace(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function sanitizeTag(rawValue) {
    return String(rawValue || "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, "-")
      .replace(/[^a-z0-9-]/g, "");
  }

  function uniqueStrings(values) {
    const seen = new Set();
    const out = [];
    for (const rawValue of values || []) {
      const value = String(rawValue || "").trim();
      if (!value || seen.has(value)) {
        continue;
      }
      seen.add(value);
      out.push(value);
    }
    return out;
  }

  function parseEmail(rawValue) {
    const direct = sanitizeWhitespace(rawValue);
    const directMatch = direct.match(/[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}/i);
    return directMatch ? directMatch[0].toLowerCase() : "";
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

  function setStorage(payload) {
    return new Promise((resolve, reject) => {
      chrome.storage.local.set(payload, () => {
        const runtimeError = chrome.runtime.lastError;
        if (runtimeError) {
          reject(new Error(runtimeError.message));
          return;
        }
        resolve();
      });
    });
  }

  async function loadConfig() {
    const data = await getStorage([STORAGE_API_BASE_KEY, STORAGE_API_KEY]);
    const apiBaseUrl = sanitizeWhitespace(data[STORAGE_API_BASE_KEY]) || DEFAULT_API_BASE_URL;
    const apiKey = sanitizeWhitespace(data[STORAGE_API_KEY]);
    return { apiBaseUrl, apiKey };
  }

  function buildApiUrl(apiBaseUrl, path) {
    const base = String(apiBaseUrl || DEFAULT_API_BASE_URL).trim().replace(/\/+$/, "");
    const suffix = String(path || "").startsWith("/") ? path : `/${String(path || "")}`;
    return `${base}${suffix}`;
  }

  async function fetchAutoTagRules() {
    let config;
    try {
      config = await loadConfig();
    } catch (_error) {
      return FALLBACK_RULES;
    }

    const headers = {};
    if (config.apiKey) {
      headers["X-API-Key"] = config.apiKey;
    }

    const url = buildApiUrl(config.apiBaseUrl, "/v1/auto-tag-rules");
    try {
      const response = await fetch(url, { method: "GET", headers });
      if (!response.ok) {
        return FALLBACK_RULES;
      }
      const payload = await response.json();
      return payload || FALLBACK_RULES;
    } catch (_error) {
      return FALLBACK_RULES;
    }
  }

  function selectFirstText(selectors) {
    for (const selector of selectors) {
      const element = document.querySelector(selector);
      const value = sanitizeWhitespace(element?.textContent || "");
      if (value) {
        return value;
      }
    }
    return "";
  }

  function extractBodyText() {
    let best = "";
    for (const selector of BODY_SELECTORS) {
      const nodes = document.querySelectorAll(selector);
      for (const node of nodes) {
        const value = sanitizeWhitespace(node?.textContent || "");
        if (value.length > best.length) {
          best = value;
        }
      }
    }
    if (best.length > MAX_BODY_CHARS) {
      return best.slice(0, MAX_BODY_CHARS);
    }
    return best;
  }

  function extractSender() {
    for (const selector of SENDER_SELECTORS) {
      const nodes = document.querySelectorAll(selector);
      for (const node of nodes) {
        const emailAttr = sanitizeWhitespace(node.getAttribute("email"));
        const parsedEmail = parseEmail(emailAttr || node.textContent || "");
        if (!parsedEmail) {
          continue;
        }
        const nameAttr = sanitizeWhitespace(node.getAttribute("name"));
        const textValue = sanitizeWhitespace(node.textContent || "");
        const senderName = nameAttr || textValue.replace(parsedEmail, "").replace(/[<>"]/g, "").trim();
        return {
          senderEmail: parsedEmail,
          senderName: senderName || parsedEmail
        };
      }
    }
    return { senderEmail: "", senderName: "" };
  }

  function extractAttachmentNames() {
    const attachments = [];
    for (const selector of ATTACHMENT_SELECTORS) {
      const nodes = document.querySelectorAll(selector);
      for (const node of nodes) {
        const label = sanitizeWhitespace(
          node.getAttribute("data-tooltip") || node.getAttribute("aria-label") || node.textContent || ""
        );
        if (!label || label.length > 120) {
          continue;
        }
        if (!/[.][a-z0-9]{2,6}$/i.test(label)) {
          continue;
        }
        attachments.push(label);
      }
    }
    return uniqueStrings(attachments);
  }

  function hasOpenMessageContext() {
    return Boolean(selectFirstText(SUBJECT_SELECTORS) || extractBodyText());
  }

  function deriveGroupFromSender(senderEmail, rules) {
    const normalized = String(senderEmail || "").toLowerCase();
    if (!normalized) {
      return "reference";
    }

    const senderRules = rules?.email_senders || {};
    for (const [groupId, patterns] of Object.entries(senderRules)) {
      if (!Array.isArray(patterns)) {
        continue;
      }
      for (const patternRaw of patterns) {
        const pattern = String(patternRaw || "").trim().toLowerCase();
        if (!pattern) {
          continue;
        }
        if (pattern.startsWith("@")) {
          if (normalized.endsWith(pattern)) {
            return groupId;
          }
          continue;
        }
        if (normalized.includes(pattern)) {
          return groupId;
        }
      }
    }
    return "reference";
  }

  function deriveTagsFromSender(senderEmail, rules) {
    const normalized = String(senderEmail || "").toLowerCase();
    const domain = normalized.includes("@") ? normalized.split("@")[1] : "";
    const tags = ["gmail", "email"];

    if (domain) {
      for (const [patternRaw, values] of Object.entries(rules?.url_tag_patterns || {})) {
        const pattern = String(patternRaw || "").trim().toLowerCase();
        if (!pattern || !Array.isArray(values)) {
          continue;
        }
        if (domain.endsWith(pattern) || domain.includes(pattern)) {
          tags.push(...values);
        }
      }
      const root = domain.split(".")[0];
      if (root) {
        tags.push(root);
      }
    }

    return uniqueStrings(tags.map(sanitizeTag).filter(Boolean));
  }

  function buildEmailText(context) {
    const lines = [];
    if (context.subject) {
      lines.push(`Subject: ${context.subject}`);
    }
    if (context.senderName || context.senderEmail) {
      const senderLine = context.senderEmail
        ? `${context.senderName || context.senderEmail} <${context.senderEmail}>`
        : context.senderName;
      lines.push(`From: ${senderLine}`);
    }
    if (context.attachments.length) {
      lines.push(`Attachments: ${context.attachments.join(", ")}`);
    }
    if (context.bodyText) {
      lines.push("", context.bodyText);
    }
    return sanitizeWhitespace(lines.join("\n"));
  }

  async function buildPrefillPayload() {
    const subject = selectFirstText(SUBJECT_SELECTORS);
    const { senderEmail, senderName } = extractSender();
    const bodyText = extractBodyText();
    const attachments = extractAttachmentNames();

    if (!subject && !bodyText) {
      throw new Error("No Gmail message context detected.");
    }

    const rules = await fetchAutoTagRules();
    const group = deriveGroupFromSender(senderEmail, rules);
    const tags = deriveTagsFromSender(senderEmail, rules);

    const context = {
      subject,
      senderEmail,
      senderName,
      bodyText,
      attachments
    };

    return {
      createdAt: Date.now(),
      expiresAt: Date.now() + PREFILL_MAX_AGE_MS,
      source: "gmail-content-script",
      url: String(window.location.href || ""),
      group,
      tags,
      subject: subject || "Gmail message",
      senderEmail,
      senderName,
      attachmentNames: attachments,
      bodyText: buildEmailText(context)
    };
  }

  async function requestPopupOpen() {
    return await chrome.runtime.sendMessage({ type: "recall_open_popup_from_gmail" });
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type !== "recall_build_gmail_prefill") {
      return undefined;
    }

    void (async () => {
      try {
        const payload = await buildPrefillPayload();
        sendResponse({ ok: true, payload });
      } catch (error) {
        sendResponse({ ok: false, error: String(error?.message || error || "Unknown error") });
      }
    })();

    return true;
  });

  async function handleCaptureClick(button) {
    const previous = button.textContent;
    button.disabled = true;
    button.textContent = "Saving...";

    try {
      const payload = await buildPrefillPayload();
      await setStorage({ [STORAGE_PREFILL_KEY]: payload });
      await requestPopupOpen();
      button.textContent = "Queued";
    } catch (error) {
      console.warn("Gmail capture prefill failed:", error);
      button.textContent = "Retry";
    } finally {
      setTimeout(() => {
        button.disabled = false;
        button.textContent = previous;
      }, 1200);
    }
  }

  function ensureStyles() {
    if (document.getElementById(STYLE_ID)) {
      return;
    }
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      .${BUTTON_CLASS} {
        margin-left: 8px;
        border: 1px solid rgba(245, 158, 11, 0.55);
        background: linear-gradient(130deg, #d97706, #ea580c);
        color: #fff7eb;
        border-radius: 16px;
        font-size: 12px;
        font-weight: 600;
        line-height: 1;
        padding: 7px 10px;
        cursor: pointer;
      }
      .${BUTTON_CLASS}[disabled] {
        opacity: 0.75;
        cursor: wait;
      }
    `;
    document.documentElement.appendChild(style);
  }

  function createCaptureButton() {
    const button = document.createElement("button");
    button.type = "button";
    button.className = BUTTON_CLASS;
    button.setAttribute(BUTTON_ATTR, "1");
    button.setAttribute("aria-label", "Send current Gmail message to Recall.local");
    button.textContent = "⊡ Recall";
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      void handleCaptureClick(button);
    });
    return button;
  }

  function injectButtons() {
    if (!String(window.location.hostname || "").includes("mail.google.com")) {
      return;
    }
    if (!hasOpenMessageContext()) {
      return;
    }
    ensureStyles();

    for (const selector of TOOLBAR_SELECTORS) {
      const toolbars = document.querySelectorAll(selector);
      for (const toolbar of toolbars) {
        if (toolbar.querySelector(`[${BUTTON_ATTR}]`)) {
          continue;
        }
        toolbar.appendChild(createCaptureButton());
      }
    }
  }

  function scheduleInject() {
    if (scanTimer) {
      clearTimeout(scanTimer);
    }
    scanTimer = setTimeout(() => {
      scanTimer = null;
      injectButtons();
    }, SCAN_DEBOUNCE_MS);
  }

  function startObservers() {
    if (!document.body) {
      return;
    }
    const observer = new MutationObserver(() => {
      scheduleInject();
    });
    observer.observe(document.body, { childList: true, subtree: true });
    window.addEventListener("beforeunload", () => observer.disconnect(), { once: true });
    setInterval(() => {
      injectButtons();
    }, RESCAN_INTERVAL_MS);
  }

  injectButtons();
  startObservers();
})();
