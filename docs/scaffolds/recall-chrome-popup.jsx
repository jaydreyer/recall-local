import { useState, useEffect } from "react";

// Auto-detection rules (would live in config in production)
const URL_RULES = [
  { pattern: /linkedin\.com\/jobs|lever\.co|greenhouse\.io|\/careers/i, group: "job-search" },
  { pattern: /anthropic\.com/i, group: "job-search", tags: ["anthropic"] },
  { pattern: /openai\.com/i, group: "job-search", tags: ["openai"] },
  { pattern: /cohere\.(com|ai)/i, group: "job-search", tags: ["cohere"] },
  { pattern: /glean\.com/i, group: "job-search", tags: ["glean"] },
  { pattern: /writer\.com/i, group: "job-search", tags: ["writer"] },
  { pattern: /arxiv\.org|huggingface\.co|paperswithcode/i, group: "learning", tags: ["research"] },
  { pattern: /docs\.|documentation|readthedocs/i, group: "learning", tags: ["docs"] },
  { pattern: /github\.com/i, group: "project", tags: ["code"] },
];

const GROUPS = [
  { id: "job-search", label: "Job Search", icon: "🎯", color: "#f59e0b" },
  { id: "learning", label: "Learning", icon: "📚", color: "#8b5cf6" },
  { id: "project", label: "Project", icon: "🔧", color: "#22c55e" },
  { id: "reference", label: "Reference", icon: "📌", color: "#6366f1" },
  { id: "meeting", label: "Meeting", icon: "📋", color: "#ec4899" },
];

const QUICK_TAGS = {
  "job-search": ["anthropic", "openai", "cohere", "glean", "writer", "job-description", "se-role", "recruiter", "interview-prep"],
  "learning": ["rag", "vector-db", "prompt-engineering", "llm", "python", "api-design", "mcp"],
  "project": ["recall-local", "tone-poet", "myrsdlist", "home-lab"],
  "reference": ["article", "blog-post", "tutorial", "bookmark"],
  "meeting": ["action-items", "transcript", "follow-up"],
};

function autoDetect(url, title) {
  let group = "reference";
  let tags = [];
  for (const rule of URL_RULES) {
    if (rule.pattern.test(url)) {
      group = rule.group;
      if (rule.tags) tags = [...tags, ...rule.tags];
    }
  }
  // Title-based hints
  if (/resume|cv|cover.letter/i.test(title)) { group = "job-search"; tags.push("resume"); }
  if (/solutions?.engineer|SE\b/i.test(title)) { tags.push("se-role"); }
  return { group, tags: [...new Set(tags)] };
}

export default function IngestPopup() {
  // Simulate a page the user is on
  const [pageUrl] = useState("https://anthropic.com/careers/solutions-engineer");
  const [pageTitle] = useState("Solutions Engineer - Anthropic Careers");

  const detected = autoDetect(pageUrl, pageTitle);
  const [group, setGroup] = useState(detected.group);
  const [tags, setTags] = useState(detected.tags);
  const [tagInput, setTagInput] = useState("");
  const [sent, setSent] = useState(false);
  const [sending, setSending] = useState(false);

  const addTag = (t) => {
    const clean = t.toLowerCase().trim().replace(/\s+/g, "-");
    if (clean && !tags.includes(clean)) setTags([...tags, clean]);
    setTagInput("");
  };

  const removeTag = (t) => setTags(tags.filter((x) => x !== t));

  const handleSend = () => {
    setSending(true);
    setTimeout(() => { setSending(false); setSent(true); }, 800);
  };

  const groupData = GROUPS.find((g) => g.id === group);
  const suggestedTags = (QUICK_TAGS[group] || []).filter((t) => !tags.includes(t));

  if (sent) {
    return (
      <div style={styles.root}>
        <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Instrument+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
        <div style={styles.popup}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "32px 20px", gap: 12 }}>
            <div style={{ fontSize: 36, lineHeight: 1 }}>✓</div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#22c55e" }}>Sent to Recall</div>
            <div style={{ fontSize: 12, color: "#525252", textAlign: "center", lineHeight: 1.5 }}>
              {pageTitle}
            </div>
            <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
              <span style={{ ...styles.groupBadge, background: `${groupData.color}20`, color: groupData.color, borderColor: `${groupData.color}40` }}>
                {groupData.icon} {groupData.label}
              </span>
              {tags.slice(0, 3).map((t) => (
                <span key={t} style={styles.tagSmall}>{t}</span>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.root}>
      <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Instrument+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />

      <div style={styles.popup}>
        {/* Header */}
        <div style={styles.header}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={styles.logo}>⊡</div>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#f5f5f5", fontFamily: "'IBM Plex Mono', monospace" }}>
              Recall<span style={{ color: "#f59e0b" }}>.local</span>
            </span>
          </div>
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#22c55e", boxShadow: "0 0 6px rgba(34,197,94,0.5)" }} />
        </div>

        {/* Page being ingested */}
        <div style={styles.pagePreview}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#e5e5e5", lineHeight: 1.4, marginBottom: 4 }}>
            {pageTitle}
          </div>
          <div style={{ fontSize: 11, color: "#404040", fontFamily: "'IBM Plex Mono', monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {pageUrl}
          </div>
        </div>

        {/* Group selector */}
        <div style={styles.section}>
          <label style={styles.label}>Group</label>
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {GROUPS.map((g) => {
              const active = group === g.id;
              return (
                <button
                  key={g.id}
                  onClick={() => {
                    setGroup(g.id);
                    // Reset tags to auto-detected ones for new group
                    const newDetected = autoDetect(pageUrl, pageTitle);
                    setTags(g.id === newDetected.group ? newDetected.tags : []);
                  }}
                  style={{
                    display: "flex", alignItems: "center", gap: 5,
                    padding: "6px 10px", borderRadius: 6, fontSize: 12, fontWeight: 600,
                    border: `1px solid ${active ? g.color + "50" : "rgba(255,255,255,0.08)"}`,
                    background: active ? g.color + "18" : "transparent",
                    color: active ? g.color : "#525252",
                    cursor: "pointer", fontFamily: "'IBM Plex Mono', monospace",
                    transition: "all 0.15s",
                  }}
                >
                  <span style={{ fontSize: 13 }}>{g.icon}</span>
                  {g.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Tags */}
        <div style={styles.section}>
          <label style={styles.label}>
            Tags
            {detected.tags.length > 0 && (
              <span style={{ fontWeight: 400, color: "#404040", marginLeft: 6 }}>auto-detected</span>
            )}
          </label>

          {/* Active tags */}
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap", minHeight: 28, marginBottom: 8 }}>
            {tags.map((t) => (
              <span key={t} style={styles.tag}>
                {t}
                <span onClick={() => removeTag(t)} style={styles.tagRemove}>×</span>
              </span>
            ))}
            {tags.length === 0 && (
              <span style={{ fontSize: 12, color: "#2a2a2a", fontStyle: "italic" }}>no tags</span>
            )}
          </div>

          {/* Tag input */}
          <input
            value={tagInput}
            onChange={(e) => setTagInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && tagInput.trim()) addTag(tagInput);
              if (e.key === "Backspace" && !tagInput && tags.length) removeTag(tags[tags.length - 1]);
            }}
            placeholder="+ type to add tag"
            style={styles.tagInput}
          />

          {/* Suggested tags */}
          {suggestedTags.length > 0 && (
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 8 }}>
              {suggestedTags.slice(0, 6).map((t) => (
                <button key={t} onClick={() => addTag(t)} style={styles.suggestedTag}>
                  + {t}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Also ingest options */}
        <div style={styles.section}>
          <div style={{ display: "flex", gap: 12 }}>
            <label style={styles.checkbox}>
              <input type="checkbox" defaultChecked style={{ accentColor: "#f59e0b" }} />
              <span style={{ fontSize: 12, color: "#737373" }}>Extract full page text</span>
            </label>
            <label style={styles.checkbox}>
              <input type="checkbox" style={{ accentColor: "#f59e0b" }} />
              <span style={{ fontSize: 12, color: "#737373" }}>Save to vault</span>
            </label>
          </div>
        </div>

        {/* Actions */}
        <div style={styles.actions}>
          <button style={styles.btnCancel}>Cancel</button>
          <button style={styles.btnSend} onClick={handleSend} disabled={sending}>
            {sending ? "Sending..." : `Ingest → ${groupData.icon}`}
          </button>
        </div>
      </div>

      {/* Caption */}
      <div style={{ textAlign: "center", marginTop: 16, fontSize: 12, color: "#2a2a2a", fontFamily: "'IBM Plex Mono', monospace" }}>
        ↑ This is what appears when you click the extension button in Chrome
      </div>
    </div>
  );
}

const styles = {
  root: {
    minHeight: "100vh",
    background: "#0a0a0a",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    fontFamily: "'Instrument Sans', -apple-system, sans-serif",
    padding: 24,
  },
  popup: {
    width: 360,
    background: "#141414",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 14,
    overflow: "hidden",
    boxShadow: "0 20px 60px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04)",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "12px 16px",
    borderBottom: "1px solid rgba(255,255,255,0.06)",
  },
  logo: {
    width: 24, height: 24, borderRadius: 5,
    background: "linear-gradient(135deg, rgba(245,158,11,0.25), rgba(245,158,11,0.08))",
    border: "1px solid rgba(245,158,11,0.3)",
    display: "flex", alignItems: "center", justifyContent: "center",
    fontSize: 12, color: "#f59e0b", fontWeight: 700,
  },
  pagePreview: {
    padding: "14px 16px",
    background: "rgba(255,255,255,0.02)",
    borderBottom: "1px solid rgba(255,255,255,0.04)",
  },
  section: {
    padding: "12px 16px",
  },
  label: {
    display: "block",
    fontSize: 10,
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    color: "#404040",
    fontFamily: "'IBM Plex Mono', monospace",
    marginBottom: 8,
  },
  tag: {
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
    padding: "3px 8px",
    borderRadius: 5,
    fontSize: 12,
    fontWeight: 600,
    background: "rgba(245,158,11,0.12)",
    color: "#f59e0b",
    border: "1px solid rgba(245,158,11,0.25)",
    fontFamily: "'IBM Plex Mono', monospace",
  },
  tagRemove: {
    cursor: "pointer",
    opacity: 0.5,
    fontSize: 14,
    lineHeight: 1,
    marginLeft: 2,
  },
  tagSmall: {
    padding: "2px 6px",
    borderRadius: 4,
    fontSize: 11,
    background: "rgba(255,255,255,0.06)",
    color: "#525252",
    fontFamily: "'IBM Plex Mono', monospace",
  },
  tagInput: {
    width: "100%",
    padding: "6px 10px",
    fontSize: 12,
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.06)",
    borderRadius: 6,
    color: "#a3a3a3",
    outline: "none",
    fontFamily: "'IBM Plex Mono', monospace",
    boxSizing: "border-box",
  },
  suggestedTag: {
    padding: "3px 8px",
    borderRadius: 5,
    fontSize: 11,
    background: "transparent",
    color: "#333",
    border: "1px dashed rgba(255,255,255,0.08)",
    cursor: "pointer",
    fontFamily: "'IBM Plex Mono', monospace",
    transition: "all 0.15s",
  },
  checkbox: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    cursor: "pointer",
  },
  groupBadge: {
    padding: "2px 8px",
    borderRadius: 5,
    fontSize: 11,
    fontWeight: 600,
    border: "1px solid",
    fontFamily: "'IBM Plex Mono', monospace",
  },
  actions: {
    display: "flex",
    gap: 8,
    padding: "12px 16px",
    borderTop: "1px solid rgba(255,255,255,0.06)",
    justifyContent: "flex-end",
  },
  btnCancel: {
    padding: "8px 16px",
    fontSize: 12,
    fontWeight: 600,
    background: "transparent",
    color: "#525252",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 7,
    cursor: "pointer",
    fontFamily: "'IBM Plex Mono', monospace",
  },
  btnSend: {
    padding: "8px 20px",
    fontSize: 12,
    fontWeight: 700,
    background: "rgba(245,158,11,0.15)",
    color: "#f59e0b",
    border: "1px solid rgba(245,158,11,0.3)",
    borderRadius: 7,
    cursor: "pointer",
    fontFamily: "'IBM Plex Mono', monospace",
    transition: "all 0.15s",
  },
};
