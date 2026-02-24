const DEFAULT_BASE_URL = import.meta.env.VITE_RECALL_API_BASE_URL || "http://localhost:8090";

function normalizeBaseUrl(rawUrl) {
  const candidate = String(rawUrl || "").trim() || DEFAULT_BASE_URL;
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
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
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
