export const DEFAULT_API_BASE_URL = "http://localhost:8090";

export const STORAGE_KEYS = {
  apiBaseUrl: "api_base_url",
  apiKey: "api_key"
};

export const FALLBACK_AUTO_TAG_RULES = {
  groups: [
    { id: "job-search", label: "Job Search", icon: "target", color: "#f59e0b" },
    { id: "learning", label: "Learning", icon: "book", color: "#8b5cf6" },
    { id: "project", label: "Project", icon: "wrench", color: "#22c55e" },
    { id: "reference", label: "Reference", icon: "pin", color: "#6366f1" },
    { id: "meeting", label: "Meeting", icon: "clipboard", color: "#ec4899" }
  ],
  url_patterns: {
    "job-search": [
      "linkedin.com/jobs",
      "lever.co",
      "greenhouse.io",
      "anthropic.com/careers",
      "openai.com/careers",
      "boards.greenhouse.io"
    ],
    learning: [
      "arxiv.org",
      "huggingface.co",
      "docs.qdrant.tech",
      "python.langchain.com",
      "docs.anthropic.com",
      "paperswithcode.com",
      "readthedocs.io"
    ],
    project: ["github.com"]
  },
  url_tag_patterns: {
    "anthropic.com": ["anthropic"],
    "openai.com": ["openai"],
    "cohere.com": ["cohere"],
    "cohere.ai": ["cohere"],
    "glean.com": ["glean"],
    "writer.com": ["writer"],
    "arxiv.org": ["research"],
    "github.com": ["code"]
  },
  title_patterns: {
    "job-search": ["resume", "cv", "cover letter", "job description"],
    meeting: ["meeting", "notes", "transcript", "action items"]
  },
  email_senders: {
    "job-search": ["@anthropic.com", "@openai.com", "@lever.co", "@greenhouse.io"]
  },
  filename_patterns: {},
  vault_folders: {},
  suggested_tags: {
    "job-search": ["anthropic", "openai", "cohere", "glean", "writer", "job-description", "se-role", "interview-prep"],
    learning: ["rag", "vector-db", "llm", "python", "api-design", "mcp"],
    project: ["recall-local", "home-lab"],
    reference: ["article", "tutorial", "bookmark"],
    meeting: ["action-items", "transcript", "follow-up"]
  }
};

export function iconTokenToGlyph(iconToken) {
  const iconMap = {
    target: "TG",
    book: "BK",
    wrench: "WR",
    pin: "PN",
    clipboard: "CB"
  };
  return iconMap[String(iconToken || "").toLowerCase()] || "RG";
}

export function sanitizeTag(rawValue) {
  return String(rawValue || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "");
}

export function uniqueStrings(values) {
  const out = [];
  const seen = new Set();
  for (const rawValue of values || []) {
    const value = String(rawValue || "").trim();
    if (!value) {
      continue;
    }
    if (seen.has(value)) {
      continue;
    }
    seen.add(value);
    out.push(value);
  }
  return out;
}

function matchesAnyPattern(text, patterns) {
  if (!text || !Array.isArray(patterns)) {
    return false;
  }
  const lowered = text.toLowerCase();
  return patterns.some((pattern) => lowered.includes(String(pattern || "").toLowerCase()));
}

export function detectGroupAndTags(context, rules) {
  const safeRules = rules || FALLBACK_AUTO_TAG_RULES;
  const url = String(context?.url || "");
  const title = String(context?.title || "");
  const loweredUrl = url.toLowerCase();
  const loweredTitle = title.toLowerCase();

  let detectedGroup = "reference";
  for (const [groupId, patterns] of Object.entries(safeRules.url_patterns || {})) {
    if (matchesAnyPattern(loweredUrl, patterns)) {
      detectedGroup = groupId;
      break;
    }
  }

  if (detectedGroup === "reference") {
    for (const [groupId, patterns] of Object.entries(safeRules.title_patterns || {})) {
      if (matchesAnyPattern(loweredTitle, patterns)) {
        detectedGroup = groupId;
        break;
      }
    }
  }

  const detectedTags = [];
  for (const [pattern, tags] of Object.entries(safeRules.url_tag_patterns || {})) {
    if (loweredUrl.includes(pattern.toLowerCase())) {
      detectedTags.push(...(tags || []));
    }
  }

  if (/\bsolutions?\s+engineer\b/i.test(title)) {
    detectedTags.push("se-role");
  }

  if (/\binterview\b/i.test(title)) {
    detectedTags.push("interview-prep");
  }

  return {
    group: detectedGroup,
    tags: uniqueStrings(detectedTags.map(sanitizeTag).filter(Boolean))
  };
}

function getStorage(keys) {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get(keys, (result) => {
      const runtimeError = chrome.runtime.lastError;
      if (runtimeError) {
        reject(new Error(runtimeError.message));
        return;
      }
      resolve(result);
    });
  });
}

function setStorage(data) {
  return new Promise((resolve, reject) => {
    chrome.storage.local.set(data, () => {
      const runtimeError = chrome.runtime.lastError;
      if (runtimeError) {
        reject(new Error(runtimeError.message));
        return;
      }
      resolve();
    });
  });
}

export async function loadExtensionConfig() {
  const data = await getStorage([STORAGE_KEYS.apiBaseUrl, STORAGE_KEYS.apiKey]);
  const apiBaseUrlRaw = String(data?.[STORAGE_KEYS.apiBaseUrl] || "").trim();
  const apiKeyRaw = String(data?.[STORAGE_KEYS.apiKey] || "").trim();
  return {
    apiBaseUrl: apiBaseUrlRaw || DEFAULT_API_BASE_URL,
    apiKey: apiKeyRaw
  };
}

export async function saveExtensionConfig(config) {
  const payload = {
    [STORAGE_KEYS.apiBaseUrl]: String(config?.apiBaseUrl || DEFAULT_API_BASE_URL).trim() || DEFAULT_API_BASE_URL,
    [STORAGE_KEYS.apiKey]: String(config?.apiKey || "").trim()
  };
  await setStorage(payload);
}

export function buildApiUrl(apiBaseUrl, path) {
  const base = String(apiBaseUrl || DEFAULT_API_BASE_URL).trim().replace(/\/+$/, "");
  const suffix = String(path || "").startsWith("/") ? path : `/${String(path || "")}`;
  return `${base}${suffix}`;
}

export async function fetchAutoTagRules(config) {
  const url = buildApiUrl(config?.apiBaseUrl, "/v1/auto-tag-rules");
  const headers = {};
  if (config?.apiKey) {
    headers["X-API-Key"] = config.apiKey;
  }

  let response;
  try {
    response = await fetch(url, { method: "GET", headers });
  } catch (error) {
    return {
      rules: FALLBACK_AUTO_TAG_RULES,
      warning: `Auto-tag rules unreachable at ${url}: ${error.message}`
    };
  }

  if (!response.ok) {
    let details = "";
    try {
      const body = await response.json();
      details = body?.error?.message ? ` (${body.error.message})` : "";
    } catch (_ignored) {
      details = "";
    }
    return {
      rules: FALLBACK_AUTO_TAG_RULES,
      warning: `Auto-tag rules request failed (${response.status})${details}`
    };
  }

  try {
    const rules = await response.json();
    return { rules, warning: "" };
  } catch (error) {
    return {
      rules: FALLBACK_AUTO_TAG_RULES,
      warning: `Auto-tag rules parse failed: ${error.message}`
    };
  }
}
