import { useState, useEffect } from "react";

// --- Concept: "ATELIER OPS" ---
// Ultra-clean luxury minimalism. Generous whitespace, razor-thin lines,
// muted earth tones with one bold accent, premium typography, 
// architectural grid, whisper-quiet animations

const TASKS = [
  { text: "Identify 5 AI-focused solutions engineer openings", owner: "Arthur", status: "active" },
  { text: "Draft Mission Control summary for Jay", owner: "Arthur", status: "queued" },
];

const CAPTURES = [
  { type: "Follow-up", text: "Calendar radar error copy reads clearly; swap to success message once OAuth lands.", time: "7:05 AM" },
  { type: "Idea", text: "Morning brief template feels solid—need final wording after live data shows up.", time: "6:55 AM" },
  { type: "Reminder", text: "Still pending Google creds from Jay; prep README snippet so handoff is easy.", time: "6:45 AM" },
];

const MEMORIES = [
  { time: "00:10", text: "Finished YouTube video summary for Greg Isenberg × Orgo talk" },
  { time: "00:12", text: "Noted Mission Control UI + Google Calendar OAuth still outstanding" },
  { time: "00:32", text: "Confirmed YouTube summary project complete" },
  { time: "Late", text: "Proved reliable timer pings via explicit Python sleep script" },
];

const AUTOMATIONS = [
  { title: "Identify 5 AI-focused SE openings", status: "active", owner: "Arthur", desc: "Scan Breakout's curated job list + LinkedIn saved searches." },
  { title: "Draft Mission Control summary", status: "queued", owner: "Arthur", desc: "Highlight quick capture + morning brief features." },
  { title: "Map recurring-revenue experiments", status: "done", owner: "Jay", desc: "Pulled 3 productized-service concepts from yesterday's notes." },
];

const ACCENT = "#E8553A";
const STATUS_LUX = {
  active: { color: ACCENT, label: "Active" },
  queued: { color: "#A0916B", label: "Queued" },
  done: { color: "#6B8F71", label: "Complete" },
};

const TYPE_ACCENT = {
  "Follow-up": ACCENT,
  "Idea": "#A0916B",
  "Reminder": "#6B8F71",
};

function LuxBadge({ status }) {
  const s = STATUS_LUX[status];
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 6,
      fontSize: 10, fontWeight: 500, letterSpacing: 1.5, textTransform: "uppercase",
      color: s.color, fontFamily: "'Manrope', sans-serif",
    }}>
      <span style={{ width: 5, height: 5, borderRadius: "50%", background: s.color }} />
      {s.label}
    </span>
  );
}

function TimeStamp({ children }) {
  return (
    <span style={{
      fontSize: 10, color: "#B8AD9E", fontFamily: "'IBM Plex Mono', monospace",
      fontWeight: 400, letterSpacing: 0.5,
    }}>{children}</span>
  );
}

function ThinRule({ spacing = 24, color = "#E8E2D8" }) {
  return <div style={{ height: 1, background: color, margin: `${spacing}px 0` }} />;
}

function FadeIn({ children, delay = 0, style }) {
  return (
    <div style={{
      animation: `luxFade 0.7s cubic-bezier(0.22, 1, 0.36, 1) ${delay}s both`,
      ...style,
    }}>
      {children}
    </div>
  );
}

export default function LuxuryDashboard() {
  const [captureText, setCaptureText] = useState("");
  const [selectedType, setSelectedType] = useState("Idea");
  const [time, setTime] = useState(new Date());
  useEffect(() => { const t = setInterval(() => setTime(new Date()), 1000); return () => clearInterval(t); }, []);

  const dateStr = time.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700;800&family=Playfair+Display:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&family=IBM+Plex+Mono:wght@300;400;500&display=swap');
        
        @keyframes luxFade {
          from { opacity: 0; transform: translateY(16px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes breathe {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #FAFAF7; }
        ::selection { background: ${ACCENT}20; color: ${ACCENT}; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #D8D0C4; border-radius: 2px; }
      `}</style>

      <div style={{
        minHeight: "100vh",
        background: "#FAFAF7",
        fontFamily: "'Manrope', sans-serif",
        color: "#2A2520",
      }}>
        {/* Subtle top accent bar */}
        <div style={{ height: 2, background: `linear-gradient(90deg, transparent, ${ACCENT}, transparent)` }} />

        <div style={{ maxWidth: 1160, margin: "0 auto", padding: "56px 40px 100px" }}>
          
          {/* Header */}
          <FadeIn>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 48 }}>
              <div>
                <div style={{
                  display: "flex", alignItems: "center", gap: 10, marginBottom: 14,
                }}>
                  <div style={{
                    width: 8, height: 8, borderRadius: "50%", background: ACCENT,
                    animation: "breathe 3s ease-in-out infinite",
                  }} />
                  <span style={{
                    fontSize: 10, fontWeight: 600, letterSpacing: 3,
                    textTransform: "uppercase", color: "#B8AD9E",
                  }}>Mission Control · Alpha</span>
                </div>
                <h1 style={{
                  fontSize: 48, fontWeight: 400,
                  fontFamily: "'Playfair Display', Georgia, serif",
                  lineHeight: 1.05, color: "#1A1815",
                  letterSpacing: -0.5,
                }}>
                  Jay's Ops<br />Console
                </h1>
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{
                  fontSize: 28, fontWeight: 300, color: "#1A1815",
                  fontFamily: "'Playfair Display', Georgia, serif",
                  letterSpacing: -0.5, lineHeight: 1,
                }}>
                  {time.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}
                </div>
                <div style={{ fontSize: 11, color: "#B8AD9E", marginTop: 4, fontWeight: 500, letterSpacing: 1 }}>
                  {dateStr}
                </div>
              </div>
            </div>
          </FadeIn>

          <ThinRule color="#E8E2D8" spacing={0} />

          {/* Tagline */}
          <FadeIn delay={0.05}>
            <p style={{
              fontSize: 14, color: "#8F8578", lineHeight: 1.7, margin: "24px 0 32px",
              maxWidth: 500, fontWeight: 400,
            }}>
              One page to capture sparks, surface yesterday's context, and remind us what to push forward today.
            </p>
          </FadeIn>

          {/* Main Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 60, alignItems: "start" }}>
            
            {/* Left */}
            <div>
              {/* Morning Brief */}
              <FadeIn delay={0.1}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <h2 style={{
                    fontSize: 12, fontWeight: 700, letterSpacing: 3,
                    textTransform: "uppercase", color: "#2A2520",
                  }}>Morning Brief</h2>
                  <TimeStamp>10:58 AM</TimeStamp>
                </div>
                <ThinRule spacing={14} />
              </FadeIn>

              {/* Focus Tasks */}
              <FadeIn delay={0.15}>
                <div style={{ marginBottom: 40 }}>
                  <span style={{
                    fontSize: 10, fontWeight: 600, letterSpacing: 2,
                    textTransform: "uppercase", color: ACCENT,
                  }}>Focus Tasks</span>
                  <div style={{ marginTop: 16 }}>
                    {TASKS.map((t, i) => (
                      <div key={i}>
                        <div style={{
                          display: "flex", justifyContent: "space-between", alignItems: "center",
                          padding: "16px 0",
                        }}>
                          <div style={{ flex: 1 }}>
                            <p style={{ fontSize: 15, lineHeight: 1.5, color: "#2A2520", fontWeight: 400, margin: 0 }}>
                              {t.text}
                            </p>
                            <span style={{
                              fontSize: 10, color: "#B8AD9E", fontFamily: "'IBM Plex Mono', monospace",
                              marginTop: 4, display: "block",
                            }}>Assigned to {t.owner}</span>
                          </div>
                          <LuxBadge status={t.status} />
                        </div>
                        {i < TASKS.length - 1 && <ThinRule spacing={0} />}
                      </div>
                    ))}
                  </div>
                </div>
              </FadeIn>

              {/* Fresh Captures */}
              <FadeIn delay={0.2}>
                <div style={{ marginBottom: 40 }}>
                  <span style={{
                    fontSize: 10, fontWeight: 600, letterSpacing: 2,
                    textTransform: "uppercase", color: "#A0916B",
                  }}>Fresh Captures</span>
                  <div style={{ marginTop: 16 }}>
                    {CAPTURES.map((c, i) => (
                      <div key={i}>
                        <div style={{ padding: "16px 0", display: "flex", gap: 20 }}>
                          <div style={{
                            width: 3, borderRadius: 2, flexShrink: 0,
                            background: TYPE_ACCENT[c.type],
                          }} />
                          <div style={{ flex: 1 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                              <span style={{
                                fontSize: 10, fontWeight: 600, letterSpacing: 1.5,
                                textTransform: "uppercase", color: TYPE_ACCENT[c.type],
                              }}>{c.type}</span>
                              <TimeStamp>{c.time}</TimeStamp>
                            </div>
                            <p style={{ fontSize: 14, lineHeight: 1.6, color: "#4A4540", margin: 0 }}>
                              {c.text}
                            </p>
                          </div>
                        </div>
                        {i < CAPTURES.length - 1 && <ThinRule spacing={0} />}
                      </div>
                    ))}
                  </div>
                </div>
              </FadeIn>

              {/* Memory Highlights */}
              <FadeIn delay={0.25}>
                <div style={{ marginBottom: 40 }}>
                  <span style={{
                    fontSize: 10, fontWeight: 600, letterSpacing: 2,
                    textTransform: "uppercase", color: "#6B8F71",
                  }}>Memory Highlights</span>
                  <div style={{ marginTop: 16 }}>
                    {MEMORIES.map((m, i) => (
                      <div key={i} style={{
                        display: "flex", gap: 20, padding: "12px 0",
                        borderBottom: i < MEMORIES.length - 1 ? "1px solid #F0EBE2" : "none",
                      }}>
                        <TimeStamp>{m.time}</TimeStamp>
                        <p style={{ fontSize: 14, lineHeight: 1.6, color: "#4A4540", margin: 0, flex: 1 }}>{m.text}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </FadeIn>

              {/* Memory Explorer */}
              <FadeIn delay={0.3}>
                <ThinRule spacing={8} />
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6, marginTop: 24 }}>
                  <h2 style={{
                    fontSize: 12, fontWeight: 700, letterSpacing: 3,
                    textTransform: "uppercase", color: "#2A2520",
                  }}>Memory Explorer</h2>
                  <span style={{ fontSize: 11, color: "#B8AD9E" }}>2 files</span>
                </div>
                <ThinRule spacing={14} />
                <input
                  type="text"
                  placeholder="Search memories…"
                  style={{
                    width: "100%", maxWidth: 400, padding: "12px 0",
                    background: "transparent", border: "none",
                    borderBottom: "1px solid #E8E2D8",
                    color: "#2A2520", fontSize: 14,
                    fontFamily: "'Manrope', sans-serif",
                    outline: "none", transition: "border-color 0.3s",
                  }}
                  onFocus={(e) => e.target.style.borderBottomColor = ACCENT}
                  onBlur={(e) => e.target.style.borderBottomColor = "#E8E2D8"}
                />
              </FadeIn>
            </div>

            {/* Right Column */}
            <div style={{ display: "flex", flexDirection: "column", gap: 40 }}>
              
              {/* Quick Capture */}
              <FadeIn delay={0.15}>
                <div>
                  <h2 style={{
                    fontSize: 12, fontWeight: 700, letterSpacing: 3,
                    textTransform: "uppercase", color: "#2A2520", marginBottom: 6,
                  }}>Quick Capture</h2>
                  <ThinRule spacing={14} />
                  <textarea
                    value={captureText}
                    onChange={(e) => setCaptureText(e.target.value)}
                    placeholder="Jay mentioned a recruiter at Company X..."
                    style={{
                      width: "100%", minHeight: 100, padding: 16,
                      background: "#FFFFFF", border: "1px solid #E8E2D8",
                      borderRadius: 2, color: "#2A2520", fontSize: 14,
                      fontFamily: "'Manrope', sans-serif",
                      resize: "vertical", outline: "none",
                      boxSizing: "border-box", lineHeight: 1.6,
                      transition: "border-color 0.3s",
                    }}
                    onFocus={(e) => e.target.style.borderColor = ACCENT}
                    onBlur={(e) => e.target.style.borderColor = "#E8E2D8"}
                  />
                  <div style={{ display: "flex", gap: 6, margin: "14px 0", flexWrap: "wrap" }}>
                    {["Idea", "Reminder", "Errand", "Follow-up"].map(t => (
                      <button key={t} onClick={() => setSelectedType(t)} style={{
                        padding: "6px 16px", fontSize: 11, fontWeight: 500,
                        background: selectedType === t ? "#2A2520" : "transparent",
                        border: `1px solid ${selectedType === t ? "#2A2520" : "#D8D0C4"}`,
                        borderRadius: 2, color: selectedType === t ? "#FAFAF7" : "#8F8578",
                        fontFamily: "'Manrope', sans-serif",
                        cursor: "pointer", transition: "all 0.2s",
                        letterSpacing: 0.5,
                      }}>{t}</button>
                    ))}
                  </div>
                  <button style={{
                    width: "100%", padding: "12px 0", borderRadius: 2,
                    background: ACCENT, border: "none",
                    color: "#fff", fontWeight: 600, fontSize: 12,
                    fontFamily: "'Manrope', sans-serif",
                    letterSpacing: 1.5, textTransform: "uppercase",
                    cursor: "pointer", transition: "all 0.2s",
                  }}
                  onMouseEnter={(e) => e.target.style.background = "#D04830"}
                  onMouseLeave={(e) => e.target.style.background = ACCENT}
                  >
                    Save to Mission Control
                  </button>
                </div>
              </FadeIn>

              {/* Automation Board */}
              <FadeIn delay={0.25}>
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                    <h2 style={{
                      fontSize: 12, fontWeight: 700, letterSpacing: 3,
                      textTransform: "uppercase", color: "#2A2520",
                    }}>Automation Board</h2>
                    <span style={{ fontSize: 11, color: "#B8AD9E" }}>3 tracked</span>
                  </div>
                  <ThinRule spacing={14} />
                  {AUTOMATIONS.map((a, i) => (
                    <div key={i}>
                      <div style={{ padding: "16px 0" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                          <span style={{ fontSize: 14, fontWeight: 500, color: "#2A2520" }}>{a.title}</span>
                          <LuxBadge status={a.status} />
                        </div>
                        <p style={{ fontSize: 13, color: "#8F8578", lineHeight: 1.55, margin: 0 }}>{a.desc}</p>
                        <span style={{
                          fontSize: 10, color: "#B8AD9E", fontFamily: "'IBM Plex Mono', monospace",
                          marginTop: 6, display: "block",
                        }}>{a.owner}</span>
                      </div>
                      {i < AUTOMATIONS.length - 1 && <ThinRule spacing={0} />}
                    </div>
                  ))}
                </div>
              </FadeIn>

              {/* Calendar */}
              <FadeIn delay={0.35}>
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                    <h2 style={{
                      fontSize: 12, fontWeight: 700, letterSpacing: 3,
                      textTransform: "uppercase", color: "#2A2520",
                    }}>Calendar Radar</h2>
                    <TimeStamp>Next 48h</TimeStamp>
                  </div>
                  <ThinRule spacing={14} />
                  <div style={{
                    padding: "48px 24px", textAlign: "center",
                    border: "1px dashed #E8E2D8", borderRadius: 2,
                  }}>
                    <div style={{
                      width: 40, height: 40, borderRadius: "50%",
                      border: `1px solid #E8E2D8`, margin: "0 auto 14px",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 18, color: "#D8D0C4",
                    }}>◎</div>
                    <p style={{ fontSize: 14, fontWeight: 500, color: "#8F8578", marginBottom: 4 }}>Nothing scheduled</p>
                    <p style={{ fontSize: 12, color: "#B8AD9E", lineHeight: 1.5, maxWidth: 220, margin: "0 auto" }}>
                      Events will appear here once OAuth tokens are connected.
                    </p>
                  </div>
                </div>
              </FadeIn>
            </div>
          </div>
        </div>

        {/* Bottom accent */}
        <div style={{ height: 2, background: `linear-gradient(90deg, transparent, ${ACCENT}40, transparent)` }} />
      </div>
    </>
  );
}
