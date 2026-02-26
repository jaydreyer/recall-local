import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { apiRequest, DEFAULT_BASE_URL } from "./api";
import "./App.css";

const TABS = [
  { key: "ingest", label: "Ingest" },
  { key: "query", label: "Query" },
  { key: "activity", label: "Activity" },
  { key: "eval", label: "Eval" },
  { key: "vault", label: "Vault" },
];

const INGEST_CHANNELS = ["bookmarklet", "webhook", "ios-share", "gmail-forward"];
const SOURCE_TYPES = ["url", "text", "gdoc", "email"];
const QUERY_MODES = ["default", "job-search"];
const EVAL_SUITES = ["core", "job-search", "learning", "both"];
const SIMPLE_INGEST_GROUP_IDS = new Set(["job-search", "reference"]);
const FILE_UPLOAD_ACCEPT = ".pdf,.docx,.txt,.md,.html,.eml";
const FILE_UPLOAD_EXTENSIONS = new Set([".pdf", ".docx", ".txt", ".md", ".html", ".eml"]);
const INGEST_QUICK_ACTIONS = [
  { key: "url", icon: "LINK", label: "Capture URL", description: "Fetch and index a web page.", sourceType: "url", channel: "bookmarklet" },
  { key: "text", icon: "TXT", label: "Paste Text", description: "Store raw notes or snippets.", sourceType: "text", channel: "webhook" },
  { key: "gdoc", icon: "DOC", label: "Google Doc", description: "Ingest a doc URL or id.", sourceType: "gdoc", channel: "webhook" },
  { key: "email", icon: "MAIL", label: "Email Body", description: "Ingest copied email content.", sourceType: "email", channel: "gmail-forward" },
];

function inferDefaultBaseUrl() {
  if (typeof window === "undefined") {
    return DEFAULT_BASE_URL;
  }

  const hostname = String(window.location.hostname || "").trim().toLowerCase();
  if (!hostname || hostname === "localhost" || hostname === "127.0.0.1") {
    return DEFAULT_BASE_URL;
  }
  return `http://${hostname}:8090`;
}

function formatClock(date) {
  return date.toLocaleTimeString("en-US", { hour12: false });
}

function parseCsv(raw) {
  return String(raw || "")
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function dedupeStrings(values) {
  const seen = new Set();
  const output = [];
  for (const raw of values || []) {
    const value = String(raw || "").trim();
    if (!value || seen.has(value.toLowerCase())) {
      continue;
    }
    seen.add(value.toLowerCase());
    output.push(value);
  }
  return output;
}

function normalizeWhitespace(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function parseUrl(value) {
  try {
    const candidate = new URL(String(value || "").trim());
    if (candidate.protocol === "http:" || candidate.protocol === "https:") {
      return candidate;
    }
    return null;
  } catch {
    return null;
  }
}

function formatSourceBadge(sourceValue, parsedUrl) {
  if (parsedUrl) {
    return parsedUrl.hostname.replace(/^www\./, "");
  }
  const raw = String(sourceValue || "").trim();
  if (!raw) {
    return "";
  }
  if (raw.startsWith("/")) {
    return "local file";
  }
  return "source";
}

function formatSourceDisplay(sourceValue, parsedUrl) {
  if (parsedUrl) {
    const pathname = parsedUrl.pathname === "/" ? "" : parsedUrl.pathname;
    return `${parsedUrl.hostname.replace(/^www\./, "")}${pathname}`;
  }
  const raw = String(sourceValue || "").trim();
  if (!raw) {
    return "";
  }
  if (raw.startsWith("/")) {
    const segments = raw.split("/").filter(Boolean);
    return segments.length > 0 ? segments[segments.length - 1] : raw;
  }
  return raw;
}

function formatChunkLabel(chunkId) {
  const normalized = String(chunkId || "").trim();
  if (!normalized) {
    return "unknown chunk";
  }
  if (/^\d+$/.test(normalized)) {
    return `chunk ${Number.parseInt(normalized, 10)}`;
  }
  return `chunk ${normalized}`;
}

function clampExcerpt(excerpt, maxLength = 320) {
  const normalized = normalizeWhitespace(excerpt);
  if (!normalized) {
    return "";
  }
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, maxLength).trimEnd()}...`;
}

function formatReferenceList(values, maxItems = 6) {
  const cleaned = dedupeStrings((values || []).map((value) => String(value || "").trim()).filter(Boolean));
  if (cleaned.length === 0) {
    return "";
  }
  if (cleaned.length <= maxItems) {
    return cleaned.join(", ");
  }
  const displayed = cleaned.slice(0, maxItems);
  return `${displayed.join(", ")} (+${cleaned.length - maxItems} more)`;
}

function dedupeCitationCards(cards) {
  const grouped = new Map();
  const ordered = [];
  (cards || []).forEach((card, index) => {
    if (!card || typeof card !== "object") {
      return;
    }
    const dedupeKey = String(
      card.sourceHref || card.sourceValue || card.title || card.technicalId || `${index}`,
    )
      .trim()
      .toLowerCase();
    const chunkRef = {
      chunkLabel: String(card.chunkLabel || "").trim() || "unknown chunk",
      technicalId: String(card.technicalId || "").trim() || "unknown-doc/unknown-chunk",
      sourceValue: String(card.sourceValue || "").trim(),
    };
    const existing = grouped.get(dedupeKey);
    if (!existing) {
      const initial = {
        ...card,
        key: `${card.key}-grouped`,
        chunkCount: 1,
        chunkRefs: [chunkRef],
      };
      grouped.set(dedupeKey, initial);
      ordered.push(initial);
      return;
    }
    existing.chunkCount += 1;
    if (!existing.excerpt && card.excerpt) {
      existing.excerpt = card.excerpt;
    }
    if (
      existing.title &&
      existing.title.startsWith("Citation ") &&
      card.title &&
      !card.title.startsWith("Citation ")
    ) {
      existing.title = card.title;
    }
    if (!existing.sourceHref && card.sourceHref) {
      existing.sourceHref = card.sourceHref;
    }
    if (!existing.sourceDisplay && card.sourceDisplay) {
      existing.sourceDisplay = card.sourceDisplay;
    }
    if (!existing.sourceBadge && card.sourceBadge) {
      existing.sourceBadge = card.sourceBadge;
    }
    const existingIds = new Set(existing.chunkRefs.map((ref) => ref.technicalId));
    if (!existingIds.has(chunkRef.technicalId)) {
      existing.chunkRefs.push(chunkRef);
    }
  });
  return ordered;
}

function inferGroupByPatterns(candidate, patternMap) {
  const normalized = String(candidate || "").trim().toLowerCase();
  if (!normalized || !patternMap || typeof patternMap !== "object") {
    return "";
  }
  for (const [groupId, patterns] of Object.entries(patternMap)) {
    if (!Array.isArray(patterns)) {
      continue;
    }
    if (patterns.some((pattern) => normalized.includes(String(pattern || "").trim().toLowerCase()))) {
      return String(groupId || "").trim();
    }
  }
  return "";
}

function inferUrlTags(urlObj, urlTagPatterns) {
  const host = String(urlObj?.hostname || "").trim().toLowerCase();
  if (!host || !urlTagPatterns || typeof urlTagPatterns !== "object") {
    return [];
  }
  const inferred = [];
  for (const [hostPattern, tags] of Object.entries(urlTagPatterns)) {
    const normalizedPattern = String(hostPattern || "").trim().toLowerCase();
    if (!normalizedPattern || !Array.isArray(tags)) {
      continue;
    }
    if (host === normalizedPattern || host.endsWith(`.${normalizedPattern}`)) {
      inferred.push(...tags.map((tag) => String(tag || "").trim()).filter(Boolean));
    }
  }
  return dedupeStrings(inferred);
}

function inferKeywordTags(candidate) {
  const normalized = String(candidate || "").toLowerCase();
  if (!normalized) {
    return [];
  }
  const tagRules = [
    { test: /\bopenai\b/, tag: "openai" },
    { test: /\banthropic\b/, tag: "anthropic" },
    { test: /\bmistral\b/, tag: "mistral" },
    { test: /\btransformer|attention is all you need\b/, tag: "transformers" },
    { test: /\brag\b|retrieval[- ]augmented/, tag: "rag" },
    { test: /\bgpt[- ]?4\b/, tag: "gpt-4" },
    { test: /\binterview\b|\bstar\b/, tag: "interview-prep" },
    { test: /\bresume\b|\bcv\b/, tag: "resume" },
  ];
  return dedupeStrings(
    tagRules.filter((rule) => rule.test.test(normalized)).map((rule) => rule.tag),
  );
}

function pickDefaultGroup(groupOptions) {
  if (!Array.isArray(groupOptions) || groupOptions.length === 0) {
    return "reference";
  }
  const reference = groupOptions.find((group) => group.id === "reference");
  return reference ? reference.id : groupOptions[0].id;
}

function inferQuickCaptureDefaults({ sourceType, content, title, rules, groups }) {
  const defaultGroup = pickDefaultGroup(groups);
  const allowedGroups = new Set((groups || []).map((group) => group.id));
  const candidateText = `${title || ""} ${content || ""}`.trim();
  const parsedUrl = sourceType === "url" || sourceType === "gdoc" ? parseUrl(content) : null;
  const urlPatternTarget = parsedUrl ? `${parsedUrl.hostname}${parsedUrl.pathname}` : "";

  let inferredGroup = inferGroupByPatterns(urlPatternTarget, rules?.url_patterns);
  if (!inferredGroup) {
    inferredGroup = inferGroupByPatterns(candidateText, rules?.title_patterns);
  }
  if (!allowedGroups.has(inferredGroup)) {
    inferredGroup = defaultGroup;
  }

  const inferredTags = dedupeStrings([
    ...inferUrlTags(parsedUrl, rules?.url_tag_patterns),
    ...inferKeywordTags(candidateText),
  ]);

  return {
    group: inferredGroup,
    tags: inferredTags,
    reason: parsedUrl ? "URL and title patterns" : "title/content patterns",
  };
}

function inferUploadDefaults({ pendingFiles, rules, groups }) {
  const defaultGroup = pickDefaultGroup(groups);
  const allowedGroups = new Set((groups || []).map((group) => group.id));
  const names = (pendingFiles || []).map((file) => String(file?.name || "")).filter(Boolean);
  const nameBlob = names.join(" ").toLowerCase();

  let inferredGroup = inferGroupByPatterns(nameBlob, rules?.filename_patterns);
  if (!allowedGroups.has(inferredGroup)) {
    inferredGroup = defaultGroup;
  }
  const inferredTags = inferKeywordTags(nameBlob);
  return {
    group: inferredGroup,
    tags: inferredTags,
    reason: "filename patterns",
  };
}

function buildCitationCards(citations, sources) {
  const sourceRows = Array.isArray(sources) ? sources : [];
  const index = new Map();
  sourceRows.forEach((row, rowIndex) => {
    if (!row || typeof row !== "object") {
      return;
    }
    const docId = String(row.doc_id || "").trim();
    const chunkId = String(row.chunk_id || "").trim();
    const key = `${docId}/${chunkId}`;
    if (docId && chunkId && !index.has(key)) {
      index.set(key, { row, rowIndex });
    }
  });

  const citationRows = Array.isArray(citations) ? citations : [];
  if (citationRows.length === 0 && sourceRows.length > 0) {
    const cards = sourceRows.map((row, rowIndex) => {
      const docId = String(row.doc_id || "").trim();
      const chunkId = String(row.chunk_id || "").trim();
      const sourceValue = String(row.source || "").trim();
      const parsed = parseUrl(sourceValue);
      const title = String(row.title || "").trim() || (parsed ? parsed.hostname.replace(/^www\./, "") : "Retrieved source");
      return {
        key: `${docId || "doc"}-${chunkId || "chunk"}-${rowIndex}`,
        docId,
        chunkId,
        chunkLabel: formatChunkLabel(chunkId),
        technicalId: `${docId || "unknown-doc"}/${chunkId || "unknown-chunk"}`,
        title,
        sourceValue,
        sourceHref: parsed ? parsed.toString() : "",
        sourceBadge: formatSourceBadge(sourceValue, parsed),
        sourceDisplay: formatSourceDisplay(sourceValue, parsed),
        excerpt: clampExcerpt(row.excerpt),
      };
    });
    return dedupeCitationCards(cards);
  }

  const cards = citationRows.map((citation, citationIndex) => {
    const docId = String(citation?.doc_id || "").trim();
    const chunkId = String(citation?.chunk_id || "").trim();
    const lookup = index.get(`${docId}/${chunkId}`);
    const row = lookup?.row || null;
    const sourceValue = String(row?.source || "").trim();
    const parsed = parseUrl(sourceValue);
    const title = String(row?.title || "").trim() || (parsed ? parsed.hostname.replace(/^www\./, "") : `Citation ${citationIndex + 1}`);
    return {
      key: `${docId || "doc"}-${chunkId || "chunk"}-${citationIndex}`,
      docId,
      chunkId,
      chunkLabel: formatChunkLabel(chunkId),
      technicalId: `${docId || "unknown-doc"}/${chunkId || "unknown-chunk"}`,
      title,
      sourceValue,
      sourceHref: parsed ? parsed.toString() : "",
      sourceBadge: formatSourceBadge(sourceValue, parsed),
      sourceDisplay: formatSourceDisplay(sourceValue, parsed),
      excerpt: clampExcerpt(row?.excerpt),
    };
  });
  return dedupeCitationCards(cards);
}

function readStoredSettings() {
  const fallbackBaseUrl = inferDefaultBaseUrl();
  try {
    const raw = localStorage.getItem("recallDashboardSettings");
    if (!raw) {
      return { baseUrl: fallbackBaseUrl, apiKey: "" };
    }
    const parsed = JSON.parse(raw);
    return {
      baseUrl: String(parsed.baseUrl || fallbackBaseUrl),
      apiKey: String(parsed.apiKey || ""),
    };
  } catch {
    return { baseUrl: fallbackBaseUrl, apiKey: "" };
  }
}

function App() {
  const [activeTab, setActiveTab] = useState("ingest");
  const [settings, setSettings] = useState(readStoredSettings);
  const [settingsDraft, setSettingsDraft] = useState(readStoredSettings);
  const [rules, setRules] = useState({ groups: [] });
  const [rulesError, setRulesError] = useState("");
  const [rulesLoading, setRulesLoading] = useState(false);
  const [bridgeHealthy, setBridgeHealthy] = useState(false);
  const [clock, setClock] = useState(() => new Date());

  const request = useCallback(
    (path, options = {}) =>
      apiRequest({
        baseUrl: settings.baseUrl,
        apiKey: settings.apiKey,
        path,
        ...options,
      }),
    [settings.baseUrl, settings.apiKey],
  );

  useEffect(() => {
    localStorage.setItem("recallDashboardSettings", JSON.stringify(settings));
  }, [settings]);

  useEffect(() => {
    let cancelled = false;
    async function loadRules() {
      setRulesLoading(true);
      setRulesError("");
      try {
        const payload = await request("/v1/auto-tag-rules");
        if (!cancelled) {
          setRules(payload || { groups: [] });
        }
      } catch (error) {
        if (!cancelled) {
          setRulesError(error.message);
          setRules({ groups: [] });
        }
      } finally {
        if (!cancelled) {
          setRulesLoading(false);
        }
      }
    }

    loadRules();
    return () => {
      cancelled = true;
    };
  }, [request]);

  useEffect(() => {
    const timer = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function checkBridge() {
      try {
        await request("/v1/healthz");
        if (!cancelled) {
          setBridgeHealthy(true);
        }
      } catch (_error) {
        if (!cancelled) {
          setBridgeHealthy(false);
        }
      }
    }

    checkBridge();
    const timer = setInterval(checkBridge, 30000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [request]);

  const groups = useMemo(() => {
    if (Array.isArray(rules.groups) && rules.groups.length > 0) {
      return rules.groups;
    }
    return [
      { id: "job-search", label: "Job Search", color: "#ef9f2f", icon: "target" },
      { id: "learning", label: "Learning", color: "#26a89a", icon: "book" },
      { id: "project", label: "Project", color: "#7ebd59", icon: "tool" },
      { id: "reference", label: "Reference", color: "#6f8eff", icon: "pin" },
      { id: "meeting", label: "Meeting", color: "#d36ec8", icon: "note" },
    ];
  }, [rules.groups]);

  const ingestGroups = useMemo(() => {
    const filtered = groups.filter((group) => SIMPLE_INGEST_GROUP_IDS.has(group.id));
    return filtered.length > 0 ? filtered : groups;
  }, [groups]);

  const groupOptions = useMemo(() => groups.map((group) => group.id), [groups]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-wrap">
          <div className="brand-logo">⊡</div>
          <div>
            <p className="overline">privacy-first ai operations agent</p>
            <h1>Recall<span className="brand-dot">.local</span></h1>
          </div>
        </div>
        <div className="header-status">
          <span className={bridgeHealthy ? "health-pill ok" : "health-pill"}>
            <span className="health-dot" />
            {bridgeHealthy ? "all systems nominal" : "bridge unavailable"}
          </span>
          <span className="clock-text">{formatClock(clock)}</span>
        </div>
      </header>

      <section className="settings-card">
        <div className="settings-grid">
          <label>
            API Base URL
            <input
              value={settingsDraft.baseUrl}
              onChange={(event) => setSettingsDraft((current) => ({ ...current, baseUrl: event.target.value }))}
              placeholder={inferDefaultBaseUrl()}
            />
          </label>
          <label>
            API Key (optional)
            <input
              value={settingsDraft.apiKey}
              onChange={(event) => setSettingsDraft((current) => ({ ...current, apiKey: event.target.value }))}
              placeholder="X-API-Key"
              type="password"
            />
          </label>
        </div>
        <div className="settings-actions">
          <button type="button" onClick={() => setSettings(settingsDraft)}>
            Apply
          </button>
        </div>
      </section>

      <section className="stats-bar">
        <HeaderStat label="Bridge" value={bridgeHealthy ? "ONLINE" : "OFFLINE"} tone={bridgeHealthy ? "good" : "bad"} />
        <HeaderStat label="Auto-Tag Groups" value={String(groups.length)} />
        <HeaderStat label="API Base" value={settings.baseUrl.replace(/^https?:\/\//, "")} />
        <HeaderStat label="Active Tab" value={TABS.find((tab) => tab.key === activeTab)?.label || "Ingest"} />
      </section>

      <nav className="tab-row" aria-label="Dashboard tabs">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={tab.key === activeTab ? "tab active" : "tab"}
            onClick={() => setActiveTab(tab.key)}
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main className="panel-frame">
        {rulesLoading && <p className="banner">Loading auto-tag rules...</p>}
        {rulesError && <p className="banner error">Auto-tag rules unavailable: {rulesError}</p>}

        <section className="tab-panel" hidden={activeTab !== "ingest"}>
          <IngestPanel request={request} groups={ingestGroups} rules={rules} />
        </section>
        <section className="tab-panel" hidden={activeTab !== "query"}>
          <QueryPanel request={request} groupOptions={groupOptions} />
        </section>
        <section className="tab-panel" hidden={activeTab !== "activity"}>
          <ActivityPanel request={request} groupOptions={groupOptions} isActive={activeTab === "activity"} />
        </section>
        <section className="tab-panel" hidden={activeTab !== "eval"}>
          <EvalPanel request={request} isActive={activeTab === "eval"} />
        </section>
        <section className="tab-panel" hidden={activeTab !== "vault"}>
          <VaultPanel request={request} isActive={activeTab === "vault"} />
        </section>
      </main>
    </div>
  );
}

function IngestPanel({ request, groups, rules }) {
  const [channel, setChannel] = useState(INGEST_CHANNELS[0]);
  const [sourceType, setSourceType] = useState(SOURCE_TYPES[0]);
  const [group, setGroup] = useState("reference");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [tags, setTags] = useState("");
  const [saveToVault, setSaveToVault] = useState(false);
  const [dryRun, setDryRun] = useState(false);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [pendingFiles, setPendingFiles] = useState([]);
  const [uploadGroup, setUploadGroup] = useState("reference");
  const [uploadTags, setUploadTags] = useState("");
  const [uploadSaveToVault, setUploadSaveToVault] = useState(false);
  const [uploadDryRun, setUploadDryRun] = useState(false);
  const [uploadRows, setUploadRows] = useState([]);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [ingestAdvancedOpen, setIngestAdvancedOpen] = useState(true);
  const [groupManuallySet, setGroupManuallySet] = useState(false);
  const [tagsManuallySet, setTagsManuallySet] = useState(false);
  const [uploadGroupManuallySet, setUploadGroupManuallySet] = useState(false);
  const [uploadTagsManuallySet, setUploadTagsManuallySet] = useState(false);
  const fileInputRef = useRef(null);
  const lastQuickSourceSignatureRef = useRef("");

  const quickDefaults = useMemo(
    () => inferQuickCaptureDefaults({ sourceType, content, title, rules, groups }),
    [content, groups, rules, sourceType, title],
  );
  const uploadDefaults = useMemo(
    () => inferUploadDefaults({ pendingFiles, rules, groups }),
    [groups, pendingFiles, rules],
  );

  useEffect(() => {
    if (groups.length > 0 && !groups.some((entry) => entry.id === group)) {
      setGroup(pickDefaultGroup(groups));
    }
  }, [groups, group]);

  useEffect(() => {
    if (groups.length > 0 && !groups.some((entry) => entry.id === uploadGroup)) {
      setUploadGroup(pickDefaultGroup(groups));
    }
  }, [groups, uploadGroup]);

  useEffect(() => {
    if (!groupManuallySet) {
      setGroup(quickDefaults.group);
    }
  }, [groupManuallySet, quickDefaults.group]);

  useEffect(() => {
    if (!tagsManuallySet) {
      setTags(quickDefaults.tags.join(","));
    }
  }, [quickDefaults.tags, tagsManuallySet]);

  useEffect(() => {
    const normalizedType = String(sourceType || "").trim().toLowerCase();
    if (normalizedType !== "url" && normalizedType !== "gdoc") {
      return;
    }
    const normalizedContent = String(content || "").trim();
    if (!normalizedContent) {
      return;
    }
    const signature = `${normalizedType}|${normalizedContent}`;
    if (lastQuickSourceSignatureRef.current === signature) {
      return;
    }
    lastQuickSourceSignatureRef.current = signature;
    setGroupManuallySet(false);
    setTagsManuallySet(false);
  }, [sourceType, content]);

  useEffect(() => {
    if (!uploadGroupManuallySet) {
      setUploadGroup(uploadDefaults.group);
    }
  }, [uploadDefaults.group, uploadGroupManuallySet]);

  useEffect(() => {
    if (!uploadTagsManuallySet) {
      setUploadTags(uploadDefaults.tags.join(","));
    }
  }, [uploadDefaults.tags, uploadTagsManuallySet]);

  const setUploadState = useCallback((uploadId, patch) => {
    setUploadRows((current) =>
      current.map((row) => (row.id === uploadId ? { ...row, ...patch } : row)),
    );
  }, []);

  const queueFiles = useCallback((fileList) => {
    const files = Array.from(fileList || []);
    if (files.length === 0) {
      return;
    }
    setPendingFiles((current) => {
      const seen = new Set(current.map((file) => `${file.name}:${file.size}:${file.lastModified}`));
      const next = [...current];
      for (const file of files) {
        const signature = `${file.name}:${file.size}:${file.lastModified}`;
        if (seen.has(signature)) {
          continue;
        }
        seen.add(signature);
        next.push(file);
      }
      return next;
    });
  }, []);

  const uploadFiles = useCallback(
    async () => {
      if (pendingFiles.length === 0) {
        return;
      }

      setUploading(true);
      setError("");
      for (const file of pendingFiles) {
        const uploadId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        const extension = (() => {
          const parts = file.name.toLowerCase().split(".");
          if (parts.length <= 1) {
            return "";
          }
          return `.${parts.pop()}`;
        })();

        setUploadRows((current) => [
          { id: uploadId, name: file.name, status: "uploading", message: "Uploading..." },
          ...current,
        ]);

        if (!FILE_UPLOAD_EXTENSIONS.has(extension)) {
          setUploadState(uploadId, {
            status: "error",
            message: "Unsupported file type",
          });
          continue;
        }

        const body = new FormData();
        body.append("file", file);
        body.append("group", uploadGroup);
        body.append("tags", uploadTags);
        body.append("save_to_vault", uploadSaveToVault ? "true" : "false");

        try {
          const response = await request(`/v1/ingestions/files?dry_run=${uploadDryRun}`, {
            method: "POST",
            body,
          });
          setUploadState(uploadId, {
            status: "success",
            message: `Accepted: ${response.filename || file.name}`,
          });
          setResult(response);
        } catch (requestError) {
          setUploadState(uploadId, {
            status: "error",
            message: requestError.message || "Upload failed",
          });
          setError(requestError.message || "Upload failed");
        }
      }
      setPendingFiles([]);
      setUploadTags("");
      setUploadGroupManuallySet(false);
      setUploadTagsManuallySet(false);
      setUploading(false);
    },
    [pendingFiles, request, setUploadState, uploadDryRun, uploadGroup, uploadSaveToVault, uploadTags],
  );

  const onSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const payload = {
        channel,
        type: sourceType,
        content,
        title: title || undefined,
        group,
        tags: parseCsv(tags),
        source: "dashboard",
      };
      const response = await request(`/v1/ingestions?dry_run=${dryRun}`, {
        method: "POST",
        body: payload,
      });
      setResult(response);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  const onDropFiles = (event) => {
    event.preventDefault();
    setDragOver(false);
    queueFiles(event.dataTransfer?.files);
  };

  const syncVault = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const response = await request("/v1/vault-syncs", { method: "POST", body: { dry_run: dryRun } });
      setResult(response);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  const isSingleLineContent = sourceType === "url" || sourceType === "gdoc";
  const contentLabel = sourceType === "url"
    ? "Paste URL"
    : sourceType === "gdoc"
      ? "Google Doc URL or id"
      : sourceType === "email"
        ? "Email Body"
        : "Text Content";
  const contentPlaceholder = sourceType === "url"
    ? "https://example.com/article"
    : sourceType === "gdoc"
      ? "https://docs.google.com/document/d/<id>/edit"
      : sourceType === "email"
        ? "Paste the email body text here"
        : "Paste text to ingest";

  return (
    <section className="panel-grid">
      <form className="card ingest-main-card" onSubmit={onSubmit}>
        <h2>Quick Capture</h2>

        <div className="quick-action-grid">
          {INGEST_QUICK_ACTIONS.map((action) => {
            const selected = sourceType === action.sourceType;
            return (
              <button
                key={action.key}
                type="button"
                className={selected ? "quick-action-btn active" : "quick-action-btn"}
                onClick={() => {
                  setSourceType(action.sourceType);
                  setChannel(action.channel);
                }}
              >
                <span className="quick-action-icon">{action.icon}</span>
                <span className="quick-action-label">{action.label}</span>
                <span className="quick-action-desc">{action.description}</span>
              </button>
            );
          })}
        </div>

        <label>
          {contentLabel}
          {isSingleLineContent ? (
            <input
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder={contentPlaceholder}
            />
          ) : (
            <textarea
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder={contentPlaceholder}
              rows={8}
            />
          )}
        </label>

        <label>
          Title (optional)
          <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Display title" />
        </label>

        <details
          className="advanced-panel"
          open={ingestAdvancedOpen}
          onToggle={(event) => setIngestAdvancedOpen(event.currentTarget.open)}
        >
          <summary>Advanced options</summary>
          <div className="advanced-panel-content">
            <div className="field-row">
              <label>
                Channel
                <select value={channel} onChange={(event) => setChannel(event.target.value)}>
                  {INGEST_CHANNELS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Source Type
                <select value={sourceType} onChange={(event) => setSourceType(event.target.value)}>
                  {SOURCE_TYPES.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="field-row">
              <label>
                Group
                <select
                  value={group}
                  onChange={(event) => {
                    setGroupManuallySet(true);
                    setGroup(event.target.value);
                  }}
                >
                  {groups.map((entry) => (
                    <option key={entry.id} value={entry.id}>
                      {entry.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Tags (comma-separated)
                <input
                  value={tags}
                  onChange={(event) => {
                    setTagsManuallySet(true);
                    setTags(event.target.value);
                  }}
                  placeholder="openai, foundation"
                />
              </label>
            </div>
            <p className="muted">
              Simplified ingest groups are enabled: use <code>reference</code> for docs/articles and use query <code>mode</code> for tone.
            </p>
            <p className="muted">
              Auto-detected from {quickDefaults.reason}. Edit Group/Tags to override.
            </p>

            <div className="advanced-checks">
              <label className="checkbox-row">
                <input type="checkbox" checked={dryRun} onChange={(event) => setDryRun(event.target.checked)} />
                Dry run
              </label>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={saveToVault}
                  onChange={(event) => setSaveToVault(event.target.checked)}
                />
                Save uploads to vault
              </label>
            </div>
          </div>
        </details>

        <div className="button-row">
          <button type="submit" disabled={loading || uploading || !content.trim()}>
            {loading ? "Sending..." : "Ingest"}
          </button>
          <button
            type="button"
            className="secondary"
            onClick={syncVault}
            disabled={loading || uploading}
          >
            Sync Vault
          </button>
        </div>

        {error && <p className="error-text">{error}</p>}
      </form>

      <div className="card ingest-upload-card">
        <h2>Upload Files</h2>
        <p className="muted">
          Drop PDF, DOCX, Markdown, text, HTML, or EML files into a queue, then upload with explicit metadata.
        </p>
        <p className="muted upload-metadata-note">
          Upload metadata is separate from Quick Capture advanced options.
        </p>
        <input
          ref={fileInputRef}
          className="file-input-hidden"
          type="file"
          multiple
          accept={FILE_UPLOAD_ACCEPT}
          onChange={(event) => {
            queueFiles(event.target.files);
            event.target.value = "";
          }}
        />
        <div
          className={dragOver ? "dropzone drag-over" : "dropzone"}
          onDragOver={(event) => {
            event.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDropFiles}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              fileInputRef.current?.click();
            }
          }}
        >
          <p className="dropzone-icon">UPLOAD</p>
          <p className="dropzone-copy">Drop files here or click to browse</p>
          <p className="dropzone-note">Accepted: .pdf .docx .txt .md .html .eml</p>
        </div>

        <div className="field-row upload-metadata-grid">
          <label>
            Upload Group
            <select
              value={uploadGroup}
              onChange={(event) => {
                setUploadGroupManuallySet(true);
                setUploadGroup(event.target.value);
              }}
            >
              {groups.map((entry) => (
                <option key={entry.id} value={entry.id}>
                  {entry.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Upload Tags (comma-separated)
            <input
              value={uploadTags}
              onChange={(event) => {
                setUploadTagsManuallySet(true);
                setUploadTags(event.target.value);
              }}
              placeholder="mistral,paper,research"
            />
          </label>
        </div>
        <p className="muted">Upload defaults inferred from {uploadDefaults.reason}. Edit to override.</p>

        <div className="advanced-checks">
          <label className="checkbox-row compact">
            <input
              type="checkbox"
              checked={uploadDryRun}
              onChange={(event) => setUploadDryRun(event.target.checked)}
            />
            Dry run uploads
          </label>
          <label className="checkbox-row compact">
            <input
              type="checkbox"
              checked={uploadSaveToVault}
              onChange={(event) => setUploadSaveToVault(event.target.checked)}
            />
            Save uploads to vault
          </label>
        </div>

        <div className="button-row">
          <button type="button" disabled={uploading || pendingFiles.length === 0} onClick={uploadFiles}>
            {uploading ? "Uploading..." : `Upload Selected (${pendingFiles.length})`}
          </button>
          <button
            type="button"
            className="secondary"
            disabled={uploading || pendingFiles.length === 0}
            onClick={() => setPendingFiles([])}
          >
            Clear Queue
          </button>
        </div>

        {pendingFiles.length > 0 && (
          <ul className="upload-list pending-list">
            {pendingFiles.map((file) => (
              <li key={`${file.name}:${file.size}:${file.lastModified}`} className="upload-row pending">
                <span>{file.name}</span>
                <span>{Math.max(1, Math.round(file.size / 1024))} KB</span>
              </li>
            ))}
          </ul>
        )}

        {uploadRows.length > 0 && (
          <ul className="upload-list">
            {uploadRows.slice(0, 8).map((row) => (
              <li key={row.id} className={`upload-row ${row.status}`}>
                <span>{row.name}</span>
                <span>{row.message}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <ResultCard title="Ingestion Response" payload={result} />
    </section>
  );
}

function QueryPanel({ request, groupOptions }) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("default");
  const [filterGroup, setFilterGroup] = useState("");
  const [filterTags, setFilterTags] = useState("");
  const [filterTagMode, setFilterTagMode] = useState("any");
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const threadEndRef = useRef(null);

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [history, loading]);

  const onSubmit = async (event) => {
    event.preventDefault();
    const question = query.trim();
    if (!question) {
      return;
    }

    setLoading(true);
    setError("");
    setNotice("");
    const activeTagFilters = parseCsv(filterTags);
    const normalizedGroup = String(filterGroup || "").trim().toLowerCase();
    const redundantTags = normalizedGroup
      ? activeTagFilters.filter((tag) => String(tag || "").trim().toLowerCase() === normalizedGroup)
      : [];
    const effectiveTagFilters = normalizedGroup
      ? activeTagFilters.filter((tag) => String(tag || "").trim().toLowerCase() !== normalizedGroup)
      : activeTagFilters;
    if (redundantTags.length > 0) {
      setNotice(`Ignored redundant tag filter "${filterGroup}" because Group Filter is already set to that value.`);
    }
    try {
      const payload = {
        query: question,
        mode,
        filter_tags: effectiveTagFilters,
        filter_tag_mode: filterTagMode,
      };
      if (filterGroup) {
        payload.filter_group = filterGroup;
      }
      const response = await request("/v1/rag-queries", { method: "POST", body: payload });
      const answer = String(response?.result?.answer || "").trim() || "No answer returned.";
      const citations = Array.isArray(response?.result?.citations) ? response.result.citations : [];
      const sources = Array.isArray(response?.result?.sources) ? response.result.sources : [];
      const audit = response?.result?.audit && typeof response.result.audit === "object" ? response.result.audit : {};
      const retrievedCount = Number.isFinite(Number(audit?.retrieved_count)) ? Number(audit.retrieved_count) : null;
      const fallbackReason = String(audit?.fallback_reason || "").trim();
      const effectiveMode = String(audit?.mode || mode).trim() || mode;
      const effectiveFilterTagMode = String(audit?.filter_tag_mode || filterTagMode).trim().toLowerCase() || filterTagMode;
      setHistory((current) => [
        ...current,
        {
          id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
          question,
          answer,
          citations,
          sources,
          mode,
          effectiveMode,
          filterGroup,
          filterTags: effectiveTagFilters,
          filterTagMode: effectiveFilterTagMode,
          retrievedCount,
          fallbackReason,
        },
      ]);
      setQuery("");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="query-layout">
      <div className="card query-chat-card">
        <div className="query-header">
          <h2>Recall Chat</h2>
          <p className="query-subtitle">Ask your indexed memory and review citations.</p>
        </div>

        <div className="mode-chip-row">
          {QUERY_MODES.map((entry) => (
            <button
              key={entry}
              type="button"
              className={mode === entry ? "mode-chip active" : "mode-chip"}
              onClick={() => setMode(entry)}
            >
              {entry}
            </button>
          ))}
        </div>

        <details className="advanced-panel query-filter-panel">
          <summary>Filters</summary>
          <div className="advanced-panel-content">
            <div className="field-row">
              <label>
                Group Filter
                <select value={filterGroup} onChange={(event) => setFilterGroup(event.target.value)}>
                  <option value="">none</option>
                  {groupOptions.map((entry) => (
                    <option key={entry} value={entry}>
                      {entry}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Tag Filter (comma-separated)
                <input
                  value={filterTags}
                  onChange={(event) => setFilterTags(event.target.value)}
                  placeholder="job-search,anthropic"
                />
              </label>
              <label>
                Tag Match
                <select value={filterTagMode} onChange={(event) => setFilterTagMode(event.target.value)}>
                  <option value="any">any (OR)</option>
                  <option value="all">all (AND)</option>
                </select>
              </label>
            </div>
            <p className="muted">
              Tip: if a tag equals Group Filter, it is ignored as redundant.
            </p>
          </div>
        </details>

        <div className="query-thread">
          {history.length === 0 && !loading ? (
            <div className="thread-placeholder">
              <p>Ask a question to start the thread.</p>
              <p className="muted">Responses include source-linked citations from retrieved chunks.</p>
            </div>
          ) : (
            history.map((item) => {
              const citationCards = buildCitationCards(item.citations, item.sources);
              return (
                <div key={item.id} className="chat-turn">
                  <article className="chat-bubble user">
                    <p className="chat-role">You</p>
                    <p className="chat-text">{item.question}</p>
                    <p className="chat-meta">
                      mode={item.effectiveMode}
                      {item.filterGroup ? ` • group=${item.filterGroup}` : ""}
                      {item.filterTags.length ? ` • tag-mode=${item.filterTagMode || "any"}` : ""}
                      {item.filterTags.length ? ` • tags=${item.filterTags.join(",")}` : ""}
                    </p>
                  </article>

                  <article className="chat-bubble assistant">
                    <p className="chat-role">Recall</p>
                    <p className="chat-text">{item.answer}</p>
                    {item.retrievedCount === 0 && (
                      <p className="chat-diagnostic">
                        No chunks matched your current filters.
                        {item.filterTags.length > 0 ? " Try clearing Tag Filter or using tags from the ingested item." : " Try clearing filters."}
                        {item.fallbackReason ? ` (${item.fallbackReason})` : ""}
                      </p>
                    )}
                    {citationCards.length > 0 ? (
                      <ul className="citation-cards">
                        {citationCards.map((citation) => (
                          <li key={citation.key} className="citation-card">
                            <div className="citation-head">
                              <p className="citation-title">{citation.title}</p>
                              <div className="citation-meta-row">
                                {citation.sourceBadge ? <span className="citation-badge">{citation.sourceBadge}</span> : null}
                                {Number(citation.chunkCount || 1) > 1 ? (
                                  <span className="citation-count">{citation.chunkCount} chunks</span>
                                ) : null}
                              </div>
                            </div>
                            {citation.sourceHref ? (
                              <a className="citation-link" href={citation.sourceHref} target="_blank" rel="noreferrer">
                                {citation.sourceDisplay || citation.sourceHref}
                              </a>
                            ) : citation.sourceDisplay ? (
                              <p className="citation-link">{citation.sourceDisplay}</p>
                            ) : null}
                            {citation.excerpt ? <p className="citation-excerpt">{citation.excerpt}</p> : null}
                            <details className="citation-details">
                              <summary>Technical details</summary>
                              <div className="citation-detail-grid">
                                <p>
                                  <span>{Number(citation.chunkCount || 1) > 1 ? "Chunks" : "Chunk"}</span>
                                  {formatReferenceList((citation.chunkRefs || []).map((ref) => ref.chunkLabel))}
                                </p>
                                <p>
                                  <span>{Number(citation.chunkCount || 1) > 1 ? "IDs" : "ID"}</span>
                                  {formatReferenceList((citation.chunkRefs || []).map((ref) => ref.technicalId), 4)}
                                </p>
                                {citation.sourceValue ? <p><span>Raw source</span>{citation.sourceValue}</p> : null}
                              </div>
                            </details>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="muted">No citations returned.</p>
                    )}
                  </article>
                </div>
              );
            })
          )}

          {loading && (
            <article className="chat-bubble assistant chat-loading">
              <p className="chat-role">Recall</p>
              <p className="chat-text">Running retrieval and synthesis...</p>
            </article>
          )}
          <div ref={threadEndRef} />
        </div>

        <form className="query-composer" onSubmit={onSubmit}>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Ask your knowledge base..."
          />
          <button type="submit" disabled={loading || !query.trim()}>
            {loading ? "Running..." : "Send"}
          </button>
        </form>
        {notice && <p className="notice-text">{notice}</p>}

        {error && <p className="error-text">{error}</p>}
      </div>
    </section>
  );
}

function ActivityPanel({ request, groupOptions, isActive }) {
  const [items, setItems] = useState([]);
  const [groupFilter, setGroupFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadActivity = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({ limit: "50" });
      if (groupFilter) {
        query.set("group", groupFilter);
      }
      const response = await request(`/v1/activities?${query.toString()}`);
      setItems(Array.isArray(response?.items) ? response.items : []);
    } catch (requestError) {
      setError(requestError.message);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [groupFilter, request]);

  useEffect(() => {
    if (!isActive) {
      return undefined;
    }
    loadActivity();
    const timer = setInterval(loadActivity, 30000);
    return () => clearInterval(timer);
  }, [isActive, loadActivity]);

  return (
    <section className="card">
      <div className="header-row">
        <h2>Recent Activity</h2>
        <div className="inline-actions">
          <select value={groupFilter} onChange={(event) => setGroupFilter(event.target.value)}>
            <option value="">all groups</option>
            {groupOptions.map((entry) => (
              <option key={entry} value={entry}>
                {entry}
              </option>
            ))}
          </select>
          <button type="button" className="secondary" onClick={loadActivity}>
            Refresh
          </button>
        </div>
      </div>

      {loading && <p className="muted">Loading activity...</p>}
      {error && <p className="error-text">{error}</p>}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Source</th>
              <th>Channel</th>
              <th>Group</th>
              <th>Tags</th>
              <th>Status</th>
              <th>Chunks</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={7} className="muted">
                  No activity rows.
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr key={item.ingest_id}>
                  <td>{item.timestamp}</td>
                  <td>{item.source_ref || item.source_type}</td>
                  <td>{item.channel}</td>
                  <td>{item.group}</td>
                  <td>{Array.isArray(item.tags) ? item.tags.join(", ") : ""}</td>
                  <td>{item.status}</td>
                  <td>{item.chunks_created}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function EvalPanel({ request, isActive }) {
  const [latest, setLatest] = useState(null);
  const [activeRuns, setActiveRuns] = useState([]);
  const [suite, setSuite] = useState("core");
  const [wait, setWait] = useState(false);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  const loadEval = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await request("/v1/evaluations?latest=true");
      setLatest(response?.latest || null);
      setActiveRuns(Array.isArray(response?.active_runs) ? response.active_runs : []);
    } catch (requestError) {
      setError(requestError.message);
      setLatest(null);
      setActiveRuns([]);
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => {
    if (!isActive) {
      return undefined;
    }
    loadEval();
    const timer = setInterval(loadEval, 30000);
    return () => clearInterval(timer);
  }, [isActive, loadEval]);

  const runEval = async () => {
    setRunning(true);
    setError("");
    try {
      await request("/v1/evaluation-runs", {
        method: "POST",
        body: {
          suite,
          backend: "webhook",
          wait,
        },
      });
      await loadEval();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <section className="card">
      <div className="header-row">
        <h2>Eval Status</h2>
        <div className="inline-actions">
          <select value={suite} onChange={(event) => setSuite(event.target.value)}>
            {EVAL_SUITES.map((entry) => (
              <option key={entry} value={entry}>
                {entry}
              </option>
            ))}
          </select>
          <label className="checkbox-row compact">
            <input type="checkbox" checked={wait} onChange={(event) => setWait(event.target.checked)} />
            wait
          </label>
          <button type="button" onClick={runEval} disabled={running}>
            {running ? "Running..." : "Run Eval"}
          </button>
          <button type="button" className="secondary" onClick={loadEval}>
            Refresh
          </button>
        </div>
      </div>

      {loading && <p className="muted">Loading eval summary...</p>}
      {error && <p className="error-text">{error}</p>}

      {latest ? (
        <div className="stats-grid">
          <Stat label="Run Date" value={latest.run_date} />
          <Stat label="Pass Rate" value={`${Math.round((latest.pass_rate || 0) * 100)}%`} />
          <Stat label="Passed" value={`${latest.passed}/${latest.total}`} />
          <Stat label="Avg Latency" value={latest.avg_latency_ms ? `${latest.avg_latency_ms} ms` : "-"} />
        </div>
      ) : (
        <p className="muted">No eval results found yet.</p>
      )}

      <h3>Active Runs</h3>
      {activeRuns.length === 0 ? (
        <p className="muted">No active eval runs.</p>
      ) : (
        <ul className="list">
          {activeRuns.map((run) => (
            <li key={run.run_id}>
              <code>{run.run_id}</code> - {run.suite} ({run.status})
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function VaultPanel({ request, isActive }) {
  const [payload, setPayload] = useState(null);
  const [syncResult, setSyncResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");

  const loadVault = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await request("/v1/vault-files");
      setPayload(response);
    } catch (requestError) {
      setError(requestError.message);
      setPayload(null);
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => {
    if (!isActive) {
      return;
    }
    loadVault();
  }, [isActive, loadVault]);

  const syncVault = async () => {
    setSyncing(true);
    setError("");
    setSyncResult(null);
    try {
      const response = await request("/v1/vault-syncs", {
        method: "POST",
        body: { dry_run: false },
      });
      setSyncResult(response);
      await loadVault();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSyncing(false);
    }
  };

  const files = Array.isArray(payload?.files) ? payload.files : [];

  return (
    <section className="panel-grid">
      <div className="card">
        <div className="header-row">
          <h2>Vault Files</h2>
          <div className="inline-actions">
            <button type="button" onClick={syncVault} disabled={syncing}>
              {syncing ? "Syncing..." : "Sync Now"}
            </button>
            <button type="button" className="secondary" onClick={loadVault}>
              Refresh
            </button>
          </div>
        </div>

        {loading && <p className="muted">Loading vault tree...</p>}
        {error && <p className="error-text">{error}</p>}

        <p className="muted">{payload ? `${payload.file_count} file(s)` : "No vault payload yet."}</p>
        <ul className="list dense">
          {files.map((file) => (
            <li key={file.path}>
              <code>{file.path}</code> - {file.group}
            </li>
          ))}
        </ul>
      </div>

      <ResultCard title="Sync Response" payload={syncResult} />
    </section>
  );
}

function ResultCard({ title, payload }) {
  return (
    <div className="card">
      <h2>{title}</h2>
      {!payload ? <p className="muted">No response yet.</p> : <pre>{JSON.stringify(payload, null, 2)}</pre>}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="stat-card">
      <p>{label}</p>
      <strong>{value}</strong>
    </div>
  );
}

function HeaderStat({ label, value, tone = "default" }) {
  const className = tone === "good" ? "header-stat value-good" : tone === "bad" ? "header-stat value-bad" : "header-stat";
  return (
    <div className={className}>
      <p>{label}</p>
      <strong>{value}</strong>
    </div>
  );
}

export default App;
