import { useCallback, useEffect, useMemo, useState } from "react";

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
const QUERY_MODES = ["default", "job-search", "learning"];
const EVAL_SUITES = ["core", "job-search", "learning", "both"];

function parseCsv(raw) {
  return String(raw || "")
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function readStoredSettings() {
  try {
    const raw = localStorage.getItem("recallDashboardSettings");
    if (!raw) {
      return { baseUrl: DEFAULT_BASE_URL, apiKey: "" };
    }
    const parsed = JSON.parse(raw);
    return {
      baseUrl: String(parsed.baseUrl || DEFAULT_BASE_URL),
      apiKey: String(parsed.apiKey || ""),
    };
  } catch {
    return { baseUrl: DEFAULT_BASE_URL, apiKey: "" };
  }
}

function App() {
  const [activeTab, setActiveTab] = useState("ingest");
  const [settings, setSettings] = useState(readStoredSettings);
  const [settingsDraft, setSettingsDraft] = useState(readStoredSettings);
  const [rules, setRules] = useState({ groups: [] });
  const [rulesError, setRulesError] = useState("");
  const [rulesLoading, setRulesLoading] = useState(false);

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

  const groupOptions = useMemo(() => groups.map((group) => group.id), [groups]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="overline">Recall.local</p>
          <h1>Dashboard</h1>
        </div>
        <div className="settings-card">
          <label>
            API Base URL
            <input
              value={settingsDraft.baseUrl}
              onChange={(event) => setSettingsDraft((current) => ({ ...current, baseUrl: event.target.value }))}
              placeholder="http://localhost:8090"
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
          <button type="button" onClick={() => setSettings(settingsDraft)}>
            Apply
          </button>
        </div>
      </header>

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

        {activeTab === "ingest" && <IngestPanel request={request} groups={groups} />}
        {activeTab === "query" && <QueryPanel request={request} groupOptions={groupOptions} />}
        {activeTab === "activity" && <ActivityPanel request={request} groupOptions={groupOptions} />}
        {activeTab === "eval" && <EvalPanel request={request} />}
        {activeTab === "vault" && <VaultPanel request={request} />}
      </main>
    </div>
  );
}

function IngestPanel({ request, groups }) {
  const [channel, setChannel] = useState(INGEST_CHANNELS[0]);
  const [sourceType, setSourceType] = useState(SOURCE_TYPES[0]);
  const [group, setGroup] = useState("reference");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [tags, setTags] = useState("");
  const [dryRun, setDryRun] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (groups.length > 0 && !groups.some((entry) => entry.id === group)) {
      setGroup(groups[0].id);
    }
  }, [groups, group]);

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

  return (
    <section className="panel-grid">
      <form className="card" onSubmit={onSubmit}>
        <h2>Create Ingestion</h2>
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

        <label>
          Title (optional)
          <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Display title" />
        </label>

        <label>
          Content
          <textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder={
              sourceType === "url"
                ? "https://example.com/article"
                : sourceType === "gdoc"
                  ? "Google Doc URL or document id"
                  : sourceType === "email"
                    ? "Email body text"
                    : "Paste text to ingest"
            }
            rows={7}
          />
        </label>

        <div className="field-row">
          <label>
            Group
            <select value={group} onChange={(event) => setGroup(event.target.value)}>
              {groups.map((entry) => (
                <option key={entry.id} value={entry.id}>
                  {entry.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Tags (comma-separated)
            <input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="anthropic, interview-prep" />
          </label>
        </div>

        <label className="checkbox-row">
          <input type="checkbox" checked={dryRun} onChange={(event) => setDryRun(event.target.checked)} />
          Dry run
        </label>

        <div className="button-row">
          <button type="submit" disabled={loading || !content.trim()}>
            {loading ? "Sending..." : "Ingest"}
          </button>
          <button
            type="button"
            className="secondary"
            onClick={async () => {
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
            }}
            disabled={loading}
          >
            Sync Vault
          </button>
        </div>

        {error && <p className="error-text">{error}</p>}
      </form>

      <ResultCard title="Ingestion Response" payload={result} />
    </section>
  );
}

function QueryPanel({ request, groupOptions }) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("default");
  const [filterGroup, setFilterGroup] = useState("");
  const [filterTags, setFilterTags] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const onSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const payload = {
        query,
        mode,
        filter_tags: parseCsv(filterTags),
      };
      if (filterGroup) {
        payload.filter_group = filterGroup;
      }
      const response = await request("/v1/rag-queries", { method: "POST", body: payload });
      setResult(response);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  const answer = result?.result?.answer || "";
  const citations = Array.isArray(result?.result?.citations) ? result.result.citations : [];

  return (
    <section className="panel-grid">
      <form className="card" onSubmit={onSubmit}>
        <h2>RAG Query</h2>
        <label>
          Question
          <textarea
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            rows={6}
            placeholder="Ask a question across your recall memory"
          />
        </label>

        <div className="field-row">
          <label>
            Mode
            <select value={mode} onChange={(event) => setMode(event.target.value)}>
              {QUERY_MODES.map((entry) => (
                <option key={entry} value={entry}>
                  {entry}
                </option>
              ))}
            </select>
          </label>
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
        </div>

        <label>
          Tag Filter (comma-separated)
          <input
            value={filterTags}
            onChange={(event) => setFilterTags(event.target.value)}
            placeholder="job-search,anthropic"
          />
        </label>

        <div className="button-row">
          <button type="submit" disabled={loading || !query.trim()}>
            {loading ? "Running..." : "Run Query"}
          </button>
        </div>

        {error && <p className="error-text">{error}</p>}
      </form>

      <div className="card">
        <h2>Answer</h2>
        {answer ? <p className="answer-copy">{answer}</p> : <p className="muted">No response yet.</p>}
        <h3>Citations</h3>
        {citations.length === 0 ? (
          <p className="muted">No citations returned yet.</p>
        ) : (
          <ul className="list">
            {citations.map((item, index) => (
              <li key={`${item.doc_id || "doc"}-${index}`}>
                <code>{item.doc_id}</code> / <code>{item.chunk_id}</code>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function ActivityPanel({ request, groupOptions }) {
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
    loadActivity();
    const timer = setInterval(loadActivity, 30000);
    return () => clearInterval(timer);
  }, [loadActivity]);

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

function EvalPanel({ request }) {
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
    loadEval();
    const timer = setInterval(loadEval, 30000);
    return () => clearInterval(timer);
  }, [loadEval]);

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

function VaultPanel({ request }) {
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
    loadVault();
  }, [loadVault]);

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

export default App;
