import { useState, useEffect, useRef } from "react";

const TABS = ["Ingest", "Query", "Activity", "Eval", "Vault"];

// --- Mock data for demo ---
const MOCK_ACTIVITY = [
  { id: 1, type: "url", source: "https://arxiv.org/abs/2401.04088", status: "✓", ts: "2m ago", chunks: 14 },
  { id: 2, type: "pdf", source: "gap_ai_strategy_q4.pdf", status: "✓", ts: "18m ago", chunks: 42 },
  { id: 3, type: "email", source: "recruiter@anthropic.com", status: "✓", ts: "1h ago", chunks: 3 },
  { id: 4, type: "obsidian", source: "vault://daily/2026-02-23.md", status: "✓", ts: "2h ago", chunks: 8 },
  { id: 5, type: "url", source: "https://docs.qdrant.tech/concepts/", status: "⟳", ts: "just now", chunks: null },
];

const MOCK_EVAL = { pass: 44, total: 47, avgLatency: "1.34s", lastRun: "2026-02-23 09:15" };

const MOCK_MESSAGES = [
  { role: "user", text: "What are the key differences between my Gap API governance work and what Anthropic needs?" },
  { role: "assistant", text: "Based on 6 ingested documents: Your Gap API governance focused on enterprise SaaS lifecycle management — vendor evaluation, contract negotiation, and cross-team adoption standards. Anthropic's Solutions Engineer role emphasizes technical integration support, API troubleshooting, and developer experience. The overlap is strongest in your API lifecycle expertise and your experience building internal tooling (the custom GPTs that replaced enterprise tools). Your gap is in developer-facing technical support at scale — your work was more internally focused. Recommend highlighting the chatbot project (75% resolution rate) as evidence of developer-experience thinking.\n\n**Sources:** gap_api_governance_brief.pdf (chunks 4,7), anthropic_se_jd.md (chunks 1-3), linkedin_profile_v3.md (chunk 2)" },
];

const TYPE_ICONS = { url: "🔗", pdf: "📄", email: "✉️", obsidian: "💎", text: "📝", gdoc: "📑" };

// --- Utility Components ---
function StatusPill({ status }) {
  const colors = {
    "✓": { bg: "rgba(34,197,94,0.15)", text: "#22c55e", border: "rgba(34,197,94,0.3)" },
    "⟳": { bg: "rgba(250,204,21,0.15)", text: "#facc15", border: "rgba(250,204,21,0.3)" },
    "✗": { bg: "rgba(239,68,68,0.15)", text: "#ef4444", border: "rgba(239,68,68,0.3)" },
  };
  const c = colors[status] || colors["✓"];
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      width: 24, height: 24, borderRadius: 6, fontSize: 12,
      background: c.bg, color: c.text, border: `1px solid ${c.border}`,
      fontFamily: "monospace"
    }}>{status}</span>
  );
}

function EvalBar({ pass, total }) {
  const pct = Math.round((pass / total) * 100);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div style={{
        flex: 1, height: 6, background: "rgba(255,255,255,0.06)",
        borderRadius: 3, overflow: "hidden"
      }}>
        <div style={{
          width: `${pct}%`, height: "100%", borderRadius: 3,
          background: pct > 90 ? "linear-gradient(90deg, #22c55e, #4ade80)" :
                     pct > 70 ? "linear-gradient(90deg, #facc15, #fde047)" :
                                "linear-gradient(90deg, #ef4444, #f87171)",
          transition: "width 0.6s cubic-bezier(0.16,1,0.3,1)"
        }} />
      </div>
      <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 13, color: "#a3a3a3" }}>
        {pass}/{total} ({pct}%)
      </span>
    </div>
  );
}

// --- Tab Panels ---
function IngestPanel() {
  const [url, setUrl] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef(null);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* URL Ingest */}
      <div>
        <label style={styles.label}>Paste URL</label>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://arxiv.org/abs/2401.04088"
            style={styles.input}
          />
          <button style={styles.btnPrimary} onClick={() => setUrl("")}>
            Ingest →
          </button>
        </div>
      </div>

      {/* File Drop Zone */}
      <div>
        <label style={styles.label}>Upload Files</label>
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); }}
          onClick={() => fileRef.current?.click()}
          style={{
            ...styles.dropzone,
            borderColor: dragOver ? "#f59e0b" : "rgba(255,255,255,0.1)",
            background: dragOver ? "rgba(245,158,11,0.05)" : "rgba(255,255,255,0.02)",
          }}
        >
          <input ref={fileRef} type="file" multiple accept=".pdf,.docx,.txt,.md,.html,.eml" style={{ display: "none" }} />
          <div style={{ fontSize: 28, marginBottom: 8, opacity: 0.5 }}>📂</div>
          <div style={{ color: "#737373", fontSize: 14 }}>
            Drop PDF, DOCX, Markdown, or email files here
          </div>
          <div style={{ color: "#525252", fontSize: 12, marginTop: 4 }}>
            or click to browse
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div>
        <label style={styles.label}>Quick Ingest</label>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {[
            { icon: "✉️", label: "Check Email", desc: "Poll IMAP inbox" },
            { icon: "💎", label: "Sync Vault", desc: "Obsidian vault" },
            { icon: "📑", label: "Google Doc", desc: "Paste doc URL" },
            { icon: "📋", label: "Paste Text", desc: "Raw text input" },
          ].map((a) => (
            <button key={a.label} style={styles.quickAction}>
              <span style={{ fontSize: 18 }}>{a.icon}</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: "#e5e5e5" }}>{a.label}</span>
              <span style={{ fontSize: 11, color: "#737373" }}>{a.desc}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function QueryPanel() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState(MOCK_MESSAGES);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Mode selector */}
      <div style={{ display: "flex", gap: 6, marginBottom: 16 }}>
        {["Default", "Job Search", "Learning"].map((m, i) => (
          <button key={m} style={{
            ...styles.modeBtn,
            background: i === 0 ? "rgba(245,158,11,0.15)" : "transparent",
            color: i === 0 ? "#f59e0b" : "#737373",
            borderColor: i === 0 ? "rgba(245,158,11,0.3)" : "rgba(255,255,255,0.08)",
          }}>{m}</button>
        ))}
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 16, minHeight: 0 }}>
        {messages.map((m, i) => (
          <div key={i} style={{
            padding: "12px 16px", borderRadius: 10,
            background: m.role === "user" ? "rgba(245,158,11,0.08)" : "rgba(255,255,255,0.03)",
            border: `1px solid ${m.role === "user" ? "rgba(245,158,11,0.2)" : "rgba(255,255,255,0.06)"}`,
            fontSize: 14, lineHeight: 1.65, color: "#d4d4d4",
            whiteSpace: "pre-wrap",
          }}>
            <div style={{
              fontSize: 11, fontWeight: 700, textTransform: "uppercase",
              letterSpacing: "0.08em", marginBottom: 6,
              color: m.role === "user" ? "#f59e0b" : "#737373",
              fontFamily: "'IBM Plex Mono', monospace"
            }}>
              {m.role === "user" ? "You" : "Recall"}
            </div>
            {m.text}
          </div>
        ))}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && input.trim()) {
              setMessages([...messages, { role: "user", text: input }]);
              setInput("");
            }
          }}
          placeholder="Ask your knowledge base..."
          style={{ ...styles.input, flex: 1 }}
        />
        <button style={styles.btnPrimary} onClick={() => {
          if (input.trim()) {
            setMessages([...messages, { role: "user", text: input }]);
            setInput("");
          }
        }}>Send</button>
      </div>
    </div>
  );
}

function ActivityPanel() {
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <label style={{ ...styles.label, margin: 0 }}>Recent Ingestions</label>
        <span style={{ fontSize: 12, color: "#525252", fontFamily: "'IBM Plex Mono', monospace" }}>
          {MOCK_ACTIVITY.length} items
        </span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {MOCK_ACTIVITY.map((item) => (
          <div key={item.id} style={styles.activityRow}>
            <span style={{ fontSize: 16, width: 28, textAlign: "center" }}>
              {TYPE_ICONS[item.type] || "📄"}
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontSize: 13, color: "#d4d4d4", whiteSpace: "nowrap",
                overflow: "hidden", textOverflow: "ellipsis"
              }}>{item.source}</div>
              <div style={{ fontSize: 11, color: "#525252", marginTop: 2 }}>
                {item.type} · {item.ts}
                {item.chunks && ` · ${item.chunks} chunks`}
              </div>
            </div>
            <StatusPill status={item.status} />
          </div>
        ))}
      </div>
    </div>
  );
}

function EvalPanel() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div>
        <label style={styles.label}>Last Eval Run</label>
        <div style={{
          padding: 20, borderRadius: 12,
          background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)"
        }}>
          <EvalBar pass={MOCK_EVAL.pass} total={MOCK_EVAL.total} />
          <div style={{ display: "flex", gap: 32, marginTop: 16 }}>
            {[
              { label: "Pass Rate", value: `${Math.round((MOCK_EVAL.pass / MOCK_EVAL.total) * 100)}%` },
              { label: "Avg Latency", value: MOCK_EVAL.avgLatency },
              { label: "Test Cases", value: MOCK_EVAL.total },
              { label: "Last Run", value: MOCK_EVAL.lastRun },
            ].map((s) => (
              <div key={s.label}>
                <div style={{ fontSize: 11, color: "#525252", textTransform: "uppercase", letterSpacing: "0.08em", fontFamily: "'IBM Plex Mono', monospace" }}>{s.label}</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: "#e5e5e5", marginTop: 4, fontFamily: "'IBM Plex Mono', monospace" }}>{s.value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div>
        <label style={styles.label}>Suite Breakdown</label>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[
            { name: "Core RAG Retrieval", pass: 18, total: 19 },
            { name: "Job Search Grounding", pass: 14, total: 15 },
            { name: "Learning Mode Synthesis", pass: 12, total: 13 },
          ].map((s) => (
            <div key={s.name} style={{
              display: "flex", alignItems: "center", gap: 12,
              padding: "10px 14px", borderRadius: 8,
              background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)"
            }}>
              <div style={{ flex: 1, fontSize: 13, color: "#a3a3a3" }}>{s.name}</div>
              <EvalBar pass={s.pass} total={s.total} />
            </div>
          ))}
        </div>
      </div>

      <button style={{ ...styles.btnPrimary, alignSelf: "flex-start" }}>
        ▶ Run Eval Suite
      </button>
    </div>
  );
}

function VaultPanel() {
  const vaultTree = [
    { name: "📁 daily/", children: ["2026-02-23.md", "2026-02-22.md", "2026-02-21.md"] },
    { name: "📁 projects/", children: ["recall-local.md", "tone-poet-tracker.md", "job-search.md"] },
    { name: "📁 career/", children: ["target-companies.md", "interview-prep.md", "se-role-research.md"] },
    { name: "📁 learning/", children: ["rag-patterns.md", "vector-databases.md", "prompt-engineering.md"] },
    { name: "📁 references/", children: ["api-governance-notes.md", "gap-chatbot-metrics.md"] },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <label style={{ ...styles.label, margin: 0 }}>Obsidian Vault</label>
        <button style={styles.btnSecondary}>⟳ Sync Now</button>
      </div>

      <div style={{
        padding: 16, borderRadius: 12,
        background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)",
        fontFamily: "'IBM Plex Mono', monospace", fontSize: 13
      }}>
        {vaultTree.map((folder) => (
          <div key={folder.name} style={{ marginBottom: 12 }}>
            <div style={{ color: "#f59e0b", fontWeight: 600, marginBottom: 4 }}>{folder.name}</div>
            {folder.children.map((f) => (
              <div key={f} style={{ color: "#737373", paddingLeft: 20, lineHeight: 1.8 }}>
                ├─ {f}
              </div>
            ))}
          </div>
        ))}
      </div>

      <div style={{
        padding: 14, borderRadius: 10,
        background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.15)",
        fontSize: 13, color: "#a3a3a3", lineHeight: 1.6
      }}>
        <strong style={{ color: "#f59e0b" }}>Vault ↔ Recall sync:</strong> New and modified .md files are auto-ingested into the RAG pipeline via file watcher. Recall query results can be saved back as vault notes.
      </div>
    </div>
  );
}

// --- Main App ---
export default function RecallDashboard() {
  const [tab, setTab] = useState("Ingest");
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const panels = { Ingest: IngestPanel, Query: QueryPanel, Activity: ActivityPanel, Eval: EvalPanel, Vault: VaultPanel };
  const Panel = panels[tab];

  return (
    <div style={styles.root}>
      <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Instrument+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />

      {/* Header */}
      <header style={styles.header}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={styles.logo}>⊡</div>
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "#f5f5f5", fontFamily: "'IBM Plex Mono', monospace", letterSpacing: "-0.02em" }}>
              Recall<span style={{ color: "#f59e0b" }}>.local</span>
            </div>
            <div style={{ fontSize: 11, color: "#525252", fontFamily: "'IBM Plex Mono', monospace" }}>
              privacy-first ai operations agent
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {/* Health indicator */}
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#22c55e", boxShadow: "0 0 8px rgba(34,197,94,0.5)" }} />
            <span style={{ fontSize: 11, color: "#525252", fontFamily: "'IBM Plex Mono', monospace" }}>
              all systems nominal
            </span>
          </div>
          <div style={{ fontSize: 12, color: "#404040", fontFamily: "'IBM Plex Mono', monospace" }}>
            {time.toLocaleTimeString("en-US", { hour12: false })}
          </div>
        </div>
      </header>

      {/* Stats bar */}
      <div style={styles.statsBar}>
        {[
          { label: "Documents", value: "47" },
          { label: "Chunks", value: "1,284" },
          { label: "Vectors", value: "1,284" },
          { label: "Eval Score", value: "93.6%" },
          { label: "Avg Latency", value: "1.34s" },
        ].map((s) => (
          <div key={s.label} style={styles.stat}>
            <div style={styles.statLabel}>{s.label}</div>
            <div style={styles.statValue}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <nav style={styles.tabs}>
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              ...styles.tab,
              color: tab === t ? "#f59e0b" : "#525252",
              borderBottom: tab === t ? "2px solid #f59e0b" : "2px solid transparent",
              background: tab === t ? "rgba(245,158,11,0.05)" : "transparent",
            }}
          >{t}</button>
        ))}
      </nav>

      {/* Panel */}
      <main style={styles.main}>
        <Panel />
      </main>

      {/* Footer */}
      <footer style={styles.footer}>
        <span>recall.local v0.4.0</span>
        <span>ollama: qwen2.5:14b</span>
        <span>qdrant: 1,284 vectors</span>
        <span>ubuntu 24.04 · rtx 2060</span>
      </footer>
    </div>
  );
}

// --- Styles ---
const styles = {
  root: {
    minHeight: "100vh",
    background: "#0a0a0a",
    color: "#d4d4d4",
    fontFamily: "'Instrument Sans', -apple-system, sans-serif",
    display: "flex",
    flexDirection: "column",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "16px 24px",
    borderBottom: "1px solid rgba(255,255,255,0.06)",
    background: "rgba(255,255,255,0.02)",
  },
  logo: {
    width: 36, height: 36, borderRadius: 8,
    background: "linear-gradient(135deg, rgba(245,158,11,0.2), rgba(245,158,11,0.05))",
    border: "1px solid rgba(245,158,11,0.3)",
    display: "flex", alignItems: "center", justifyContent: "center",
    fontSize: 18, color: "#f59e0b", fontWeight: 700,
  },
  statsBar: {
    display: "flex",
    gap: 0,
    borderBottom: "1px solid rgba(255,255,255,0.06)",
    background: "rgba(255,255,255,0.01)",
  },
  stat: {
    flex: 1,
    padding: "12px 24px",
    borderRight: "1px solid rgba(255,255,255,0.04)",
  },
  statLabel: {
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    color: "#404040",
    fontFamily: "'IBM Plex Mono', monospace",
    fontWeight: 600,
  },
  statValue: {
    fontSize: 17,
    fontWeight: 700,
    color: "#e5e5e5",
    fontFamily: "'IBM Plex Mono', monospace",
    marginTop: 2,
  },
  tabs: {
    display: "flex",
    gap: 0,
    borderBottom: "1px solid rgba(255,255,255,0.06)",
    paddingLeft: 16,
  },
  tab: {
    padding: "12px 20px",
    fontSize: 13,
    fontWeight: 600,
    fontFamily: "'IBM Plex Mono', monospace",
    letterSpacing: "0.02em",
    border: "none",
    cursor: "pointer",
    transition: "all 0.2s",
    background: "transparent",
  },
  main: {
    flex: 1,
    padding: 24,
    overflowY: "auto",
  },
  footer: {
    display: "flex",
    gap: 24,
    padding: "10px 24px",
    borderTop: "1px solid rgba(255,255,255,0.04)",
    fontSize: 11,
    color: "#2a2a2a",
    fontFamily: "'IBM Plex Mono', monospace",
  },
  label: {
    display: "block",
    fontSize: 11,
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    color: "#525252",
    fontFamily: "'IBM Plex Mono', monospace",
    marginBottom: 10,
  },
  input: {
    flex: 1,
    padding: "10px 14px",
    fontSize: 14,
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: 8,
    color: "#e5e5e5",
    outline: "none",
    fontFamily: "'IBM Plex Mono', monospace",
  },
  btnPrimary: {
    padding: "10px 20px",
    fontSize: 13,
    fontWeight: 700,
    background: "rgba(245,158,11,0.15)",
    color: "#f59e0b",
    border: "1px solid rgba(245,158,11,0.3)",
    borderRadius: 8,
    cursor: "pointer",
    fontFamily: "'IBM Plex Mono', monospace",
    letterSpacing: "0.02em",
    transition: "all 0.2s",
  },
  btnSecondary: {
    padding: "6px 14px",
    fontSize: 12,
    fontWeight: 600,
    background: "rgba(255,255,255,0.04)",
    color: "#737373",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 6,
    cursor: "pointer",
    fontFamily: "'IBM Plex Mono', monospace",
  },
  dropzone: {
    padding: "32px 24px",
    borderRadius: 12,
    border: "1.5px dashed rgba(255,255,255,0.1)",
    textAlign: "center",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  quickAction: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 4,
    padding: "14px 20px",
    borderRadius: 10,
    background: "rgba(255,255,255,0.02)",
    border: "1px solid rgba(255,255,255,0.06)",
    cursor: "pointer",
    transition: "all 0.2s",
    minWidth: 100,
  },
  modeBtn: {
    padding: "6px 14px",
    fontSize: 12,
    fontWeight: 600,
    borderRadius: 6,
    border: "1px solid",
    cursor: "pointer",
    fontFamily: "'IBM Plex Mono', monospace",
    background: "transparent",
  },
  activityRow: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "10px 14px",
    borderRadius: 8,
    background: "rgba(255,255,255,0.02)",
    border: "1px solid rgba(255,255,255,0.04)",
  },
};
