const DEFAULT_BASE_URL = (import.meta.env.VITE_RECALL_API_BASE_URL || "").trim();

function sanitizeBaseUrl(rawUrl) {
  const candidate = String(rawUrl || "").trim().replace(/\/+$/, "");
  if (!candidate || typeof window === "undefined") {
    return candidate;
  }

  const protocol = window.location.protocol === "https:" ? "https:" : "http:";
  const hostname = String(window.location.hostname || "").trim().toLowerCase();
  const port = String(window.location.port || "").trim();
  const legacyTargets = new Set(
    [
      "http://localhost:8090",
      "http://127.0.0.1:8090",
      hostname ? `http://${hostname}:8090` : "",
    ].filter(Boolean),
  );

  // When the dashboard is being served by nginx, these legacy direct-to-bridge
  // URLs cause CORS and connection issues. Same-origin proxying is the correct
  // runtime path, so normalize them to an empty base URL.
  if (legacyTargets.has(candidate) && port && port !== "8090") {
    return "";
  }

  if (candidate === `${protocol}//${hostname}` && port && port !== "8090") {
    return "";
  }

  return candidate;
}

function normalizeBaseUrl(rawUrl) {
  const candidate = sanitizeBaseUrl(rawUrl) || sanitizeBaseUrl(DEFAULT_BASE_URL);
  return candidate.replace(/\/+$/, "");
}

async function parseJsonSafe(response) {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return { raw: text };
  }
}

export async function apiRequest({ baseUrl, apiKey, path, method = "GET", body }) {
  const url = `${normalizeBaseUrl(baseUrl)}${path.startsWith("/") ? path : `/${path}`}`;
  const headers = {};
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  const isMultipartBody = typeof FormData !== "undefined" && body instanceof FormData;
  if (body !== undefined && !isMultipartBody) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(url, {
    method,
    headers,
    body:
      body === undefined
        ? undefined
        : isMultipartBody
          ? body
          : JSON.stringify(body),
  });

  const payload = await parseJsonSafe(response);
  if (!response.ok) {
    const message = payload?.error?.message || `HTTP ${response.status}`;
    const error = new Error(message);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }

  return payload;
}

export { DEFAULT_BASE_URL, normalizeBaseUrl };
