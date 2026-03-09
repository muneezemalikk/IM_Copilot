import { useState, useEffect, useRef, useCallback } from "react";
import {
  BookOpen, GraduationCap, BarChart2, Calendar,
  Send, Bot, User, AlertTriangle, CheckCircle,
  TrendingUp, Clock, ChevronRight, Loader2,
  LogOut, Bell, Shield, Zap, Database, Search,
  ChevronDown, X, Menu, Lock, Eye, EyeOff
} from "lucide-react";
import {
  RadialBarChart, RadialBar, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip, Cell
} from "recharts";

// ─── Config ────────────────────────────────────────────────
const API_BASE = "http://localhost:8000";

// ─── Helpers ───────────────────────────────────────────────
const gradeColor = (gp) => {
  if (gp >= 4.0) return "#22c55e";
  if (gp >= 3.5) return "#84cc16";
  if (gp >= 3.0) return "#eab308";
  if (gp >= 2.5) return "#f97316";
  if (gp >= 2.0) return "#ef4444";
  return "#dc2626";
};

const attColor = (pct) => {
  if (pct >= 85) return "#22c55e";
  if (pct >= 80) return "#eab308";
  return "#ef4444";
};

const intentBadge = {
  academic: { label: "Academic Data",   color: "#6366f1", icon: Database },
  policy:   { label: "Policy Query",    color: "#0ea5e9", icon: BookOpen  },
  hybrid:   { label: "Hybrid Analysis", color: "#a855f7", icon: Zap       },
  greeting: { label: "Greeting",        color: "#22c55e", icon: Bot       },
};

// ─── Google Fonts ──────────────────────────────────────────
const FontLoader = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,600;1,9..144,300&display=swap');

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg:        #0a0c10;
      --surface:   #111318;
      --surface2:  #181c24;
      --border:    #1e2330;
      --border2:   #252d3d;
      --accent:    #4f8ef7;
      --accent2:   #7c3aed;
      --accent3:   #0ea5e9;
      --text:      #e8eaf0;
      --text2:     #8892a4;
      --text3:     #4a5568;
      --success:   #22c55e;
      --warn:      #f59e0b;
      --danger:    #ef4444;
      --radius:    12px;
      --radius-lg: 18px;
    }

    html, body, #root {
      height: 100%;
      background: var(--bg);
      color: var(--text);
      font-family: 'DM Sans', sans-serif;
      font-size: 14px;
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
    }

    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 4px; }

    .mono { font-family: 'DM Mono', monospace; }
    .serif { font-family: 'Fraunces', serif; }

    @keyframes fadeUp {
      from { opacity: 0; transform: translateY(12px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeIn {
      from { opacity: 0; }
      to   { opacity: 1; }
    }
    @keyframes pulse-soft {
      0%, 100% { opacity: 1; }
      50%       { opacity: 0.4; }
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    @keyframes slideIn {
      from { opacity: 0; transform: translateX(-8px); }
      to   { opacity: 1; transform: translateX(0); }
    }
    @keyframes typingDot {
      0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
      40%            { transform: scale(1);   opacity: 1;   }
    }
    @keyframes shakeX {
      0%, 100% { transform: translateX(0); }
      20%       { transform: translateX(-6px); }
      40%       { transform: translateX(6px); }
      60%       { transform: translateX(-4px); }
      80%       { transform: translateX(4px); }
    }

    .fade-up   { animation: fadeUp  0.35s ease both; }
    .fade-in   { animation: fadeIn  0.25s ease both; }
    .slide-in  { animation: slideIn 0.3s  ease both; }
    .shake     { animation: shakeX 0.4s ease both; }

    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 20px;
    }
    .card-sm {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 14px 16px;
    }

    button { cursor: pointer; border: none; outline: none; font-family: inherit; }

    .btn-primary {
      background: var(--accent);
      color: #fff;
      border-radius: 10px;
      padding: 8px 18px;
      font-size: 13px;
      font-weight: 600;
      transition: opacity 0.15s, transform 0.1s;
    }
    .btn-primary:hover  { opacity: 0.88; transform: translateY(-1px); }
    .btn-primary:active { transform: translateY(0); }
    .btn-primary:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }

    .chip {
      display: inline-flex; align-items: center; gap: 5px;
      padding: 3px 10px;
      border-radius: 20px;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.03em;
    }

    /* Login input focus glow */
    .login-input:focus {
      border-color: var(--accent) !important;
      box-shadow: 0 0 0 3px rgba(79,142,247,0.15);
    }
  `}</style>
);

// ─── Role Badge ─────────────────────────────────────────────
function RoleBadge({ role }) {
  const isAdmin = role === "admin";
  return (
    <span className="chip" style={{
      background: isAdmin ? "#7c3aed20" : "#4f8ef720",
      color: isAdmin ? "#a78bfa" : "var(--accent)",
      border: `1px solid ${isAdmin ? "#7c3aed40" : "#4f8ef740"}`,
      fontSize: 10,
      textTransform: "uppercase",
      letterSpacing: "0.08em",
    }}>
      {isAdmin ? <Shield size={9} /> : <GraduationCap size={9} />}
      {isAdmin ? "Admin" : "Student"}
    </span>
  );
}

// ─── Login Screen ───────────────────────────────────────────
function LoginScreen({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPw,   setShowPw]   = useState(false);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState("");
  const [shake,    setShake]    = useState(false);

  const triggerShake = () => {
    setShake(true);
    setTimeout(() => setShake(false), 450);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) return;
    setError("");
    setLoading(true);

    try {
      const res  = await fetch(`${API_BASE}/login`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ username: username.trim(), password: password.trim() }),
      });
      const data = await res.json();

      if (data.success) {
        onLogin(data); // { username, role, student_id }
      } else {
        setError("Invalid username or password.");
        triggerShake();
      }
    } catch {
      setError("Cannot reach server — is the backend running on :8000?");
      triggerShake();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center",
      justifyContent: "center", padding: 24,
      background: "radial-gradient(ellipse 80% 60% at 50% -10%, #1a2340 0%, var(--bg) 70%)"
    }}>
      <div className="fade-up" style={{ width: "100%", maxWidth: 400 }}>

        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 36 }}>
          <div style={{
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            width: 64, height: 64, borderRadius: 18,
            background: "linear-gradient(135deg, #4f8ef7 0%, #7c3aed 100%)",
            marginBottom: 20, boxShadow: "0 8px 32px rgba(79,142,247,0.3)"
          }}>
            <GraduationCap size={30} color="#fff" />
          </div>
          <h1 className="serif" style={{ fontSize: 32, fontWeight: 600, color: "var(--text)", letterSpacing: "-0.02em" }}>
            IM<span style={{ color: "var(--accent)" }}>|</span>Copilot
          </h1>
          <p style={{ color: "var(--text2)", marginTop: 6, fontSize: 13 }}>
            AI-Powered Academic Assistant · IMSciences Peshawar
          </p>
        </div>

        {/* Card */}
        <div className={`card ${shake ? "shake" : ""}`} style={{ padding: 28 }}>
          <p style={{
            fontSize: 12, fontWeight: 600, letterSpacing: "0.08em",
            color: "var(--text3)", textTransform: "uppercase", marginBottom: 20
          }}>
            Sign in to your account
          </p>

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>

            {/* Username */}
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: "var(--text2)" }}>
                Username
              </label>
              <input
                className="login-input"
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="e.g. S001 or admin"
                autoFocus
                required
                style={{
                  padding: "11px 14px",
                  background: "var(--surface2)",
                  border: "1px solid var(--border2)",
                  borderRadius: 10,
                  color: "var(--text)",
                  fontSize: 14,
                  outline: "none",
                  transition: "border-color 0.15s, box-shadow 0.15s",
                  fontFamily: "DM Mono, monospace",
                }}
              />
            </div>

            {/* Password */}
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: "var(--text2)" }}>
                Password
              </label>
              <div style={{ position: "relative" }}>
                <input
                  className="login-input"
                  type={showPw ? "text" : "password"}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                  style={{
                    width: "100%",
                    padding: "11px 42px 11px 14px",
                    background: "var(--surface2)",
                    border: "1px solid var(--border2)",
                    borderRadius: 10,
                    color: "var(--text)",
                    fontSize: 14,
                    outline: "none",
                    transition: "border-color 0.15s, box-shadow 0.15s",
                    fontFamily: "DM Sans, sans-serif",
                  }}
                />
                <button
                  type="button"
                  onClick={() => setShowPw(v => !v)}
                  style={{
                    position: "absolute", right: 12, top: "50%",
                    transform: "translateY(-50%)",
                    background: "none", color: "var(--text3)",
                    display: "flex", alignItems: "center",
                    padding: 2,
                  }}
                >
                  {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="fade-in" style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "10px 14px",
                background: "#ef444412",
                border: "1px solid #ef444430",
                borderRadius: 9,
                color: "#f87171",
                fontSize: 13,
              }}>
                <AlertTriangle size={14} />
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              className="btn-primary"
              disabled={loading || !username.trim() || !password.trim()}
              style={{
                width: "100%", padding: "12px",
                fontSize: 14, marginTop: 4,
                display: "flex", alignItems: "center",
                justifyContent: "center", gap: 8,
                background: "linear-gradient(135deg, #4f8ef7, #7c3aed)",
              }}
            >
              {loading
                ? <><Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} /> Signing in…</>
                : <><Lock size={15} /> Sign In</>
              }
            </button>
          </form>
        </div>

        {/* Credentials hint */}
        <div style={{
          marginTop: 16,
          padding: "14px 16px",
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 10,
          fontSize: 12,
          color: "var(--text3)",
          lineHeight: 1.8,
        }}>
          <div style={{ fontWeight: 600, color: "var(--text2)", marginBottom: 6 }}>
            Demo credentials
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>Students</span>
              <span className="mono" style={{ color: "var(--text2)" }}>S001 / ali123 &nbsp;·&nbsp; S002 / fatima123</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>Admin</span>
              <span className="mono" style={{ color: "#a78bfa" }}>admin / admin123</span>
            </div>
          </div>
        </div>

        <p style={{ textAlign: "center", marginTop: 16, fontSize: 11, color: "var(--text3)" }}>
          Demo build · FYP-1 · Institute of Management Sciences
        </p>
      </div>
    </div>
  );
}

// ─── Stat Card ──────────────────────────────────────────────
function StatCard({ label, value, sub, accent, icon: Icon, delay = 0 }) {
  return (
    <div className="card fade-up" style={{
      animationDelay: `${delay}ms`, flex: 1,
      borderLeft: `3px solid ${accent}`,
      display: "flex", flexDirection: "column", gap: 8
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <p style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.07em", color: "var(--text2)", textTransform: "uppercase" }}>
          {label}
        </p>
        <div style={{
          width: 30, height: 30, borderRadius: 8, display: "flex", alignItems: "center",
          justifyContent: "center", background: `${accent}18`
        }}>
          <Icon size={15} color={accent} />
        </div>
      </div>
      <p style={{ fontSize: 28, fontWeight: 700, color: "var(--text)", fontFamily: "DM Mono", letterSpacing: "-0.02em" }}>
        {value}
      </p>
      {sub && <p style={{ fontSize: 12, color: "var(--text2)" }}>{sub}</p>}
    </div>
  );
}

// ─── Attendance Bar ─────────────────────────────────────────
function AttBar({ course_name, attendance_pct, status, attended_classes, total_classes }) {
  const pct = attendance_pct ?? 0;
  const col = attColor(pct);
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
        <span style={{ fontSize: 13, color: "var(--text)", fontWeight: 500 }}
          title={course_name}>
          {course_name?.length > 28 ? course_name.slice(0, 26) + "…" : course_name}
        </span>
        <span style={{ fontSize: 12, fontFamily: "DM Mono", color: col, fontWeight: 600 }}>
          {pct.toFixed(1)}%
        </span>
      </div>
      <div style={{ height: 5, borderRadius: 4, background: "var(--surface2)", overflow: "hidden" }}>
        <div style={{
          height: "100%", width: `${Math.min(pct, 100)}%`,
          background: col, borderRadius: 4, transition: "width 0.8s ease"
        }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 3 }}>
        <span style={{ fontSize: 11, color: "var(--text3)" }}>{attended_classes}/{total_classes} classes</span>
        {status === "XF Risk" && (
          <span className="chip" style={{ background: "#ef444418", color: "#ef4444" }}>
            <AlertTriangle size={10} /> XF Risk
          </span>
        )}
        {status === "Warning" && (
          <span className="chip" style={{ background: "#f59e0b18", color: "#f59e0b" }}>
            <AlertTriangle size={10} /> Warning
          </span>
        )}
      </div>
    </div>
  );
}

// ─── Grade Table ────────────────────────────────────────────
function GradeTable({ grades }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--border)" }}>
            {["Course", "Mid (30)", "Final (50)", "Assign (20)", "Total", "Grade", "GP"].map(h => (
              <th key={h} style={{
                padding: "6px 10px", textAlign: "left",
                fontSize: 11, fontWeight: 600, color: "var(--text3)",
                letterSpacing: "0.06em", textTransform: "uppercase"
              }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {grades.map((g, i) => (
            <tr key={i} style={{
              borderBottom: "1px solid var(--border)",
              transition: "background 0.1s"
            }}
              onMouseEnter={e => e.currentTarget.style.background = "var(--surface2)"}
              onMouseLeave={e => e.currentTarget.style.background = "transparent"}
            >
              <td style={{ padding: "10px 10px", color: "var(--text)", fontWeight: 500, maxWidth: 180 }}>
                <div title={g.course_name} style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {g.course_name}
                </div>
                <div style={{ fontSize: 11, color: "var(--text3)", fontFamily: "DM Mono" }}>{g.course_id}</div>
              </td>
              {[g.midterm_marks, g.final_marks, g.assignment_marks, g.total_marks].map((v, j) => (
                <td key={j} style={{ padding: "10px", fontFamily: "DM Mono", fontSize: 13, color: "var(--text2)" }}>
                  {v?.toFixed(1)}
                </td>
              ))}
              <td style={{ padding: "10px" }}>
                <span className="chip" style={{
                  background: `${gradeColor(g.grade_points)}20`,
                  color: gradeColor(g.grade_points)
                }}>{g.letter_grade}</span>
              </td>
              <td style={{ padding: "10px", fontFamily: "DM Mono", color: gradeColor(g.grade_points), fontWeight: 600 }}>
                {g.grade_points?.toFixed(1)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── CGPA Radial ────────────────────────────────────────────
function CGPARadial({ cgpa }) {
  const pct = (cgpa / 4) * 100;
  const col = gradeColor(cgpa);
  const data = [{ value: pct, fill: col }, { value: 100 - pct, fill: "var(--surface2)" }];
  return (
    <div style={{ position: "relative", width: 120, height: 120 }}>
      <ResponsiveContainer width="100%" height="100%">
        <RadialBarChart
          innerRadius="70%" outerRadius="100%"
          data={data} startAngle={90} endAngle={-270} barSize={10}
        >
          <RadialBar dataKey="value" cornerRadius={6} background={false}>
            {data.map((_, i) => <Cell key={i} fill={data[i].fill} />)}
          </RadialBar>
        </RadialBarChart>
      </ResponsiveContainer>
      <div style={{
        position: "absolute", inset: 0, display: "flex",
        flexDirection: "column", alignItems: "center", justifyContent: "center"
      }}>
        <span style={{ fontSize: 22, fontWeight: 700, fontFamily: "DM Mono", color: col }}>
          {cgpa?.toFixed(2)}
        </span>
        <span style={{ fontSize: 10, color: "var(--text3)", letterSpacing: "0.05em" }}>/ 4.00</span>
      </div>
    </div>
  );
}

// ─── Typing Indicator ───────────────────────────────────────
function TypingDots() {
  return (
    <div style={{ display: "flex", gap: 5, padding: "10px 0", alignItems: "center" }}>
      {[0, 150, 300].map(delay => (
        <div key={delay} style={{
          width: 7, height: 7, borderRadius: "50%",
          background: "var(--accent)",
          animation: `typingDot 1.2s ${delay}ms ease infinite`
        }} />
      ))}
    </div>
  );
}

// ─── Chat Message ───────────────────────────────────────────
function ChatMessage({ msg }) {
  const isUser = msg.role === "user";
  const badge  = msg.intent ? intentBadge[msg.intent] : null;
  const BadgeIcon = badge?.icon;

  return (
    <div className="fade-up" style={{
      display: "flex", gap: 12,
      flexDirection: isUser ? "row-reverse" : "row",
      alignItems: "flex-start", marginBottom: 20
    }}>
      {/* Avatar */}
      <div style={{
        width: 34, height: 34, borderRadius: 10, flexShrink: 0,
        display: "flex", alignItems: "center", justifyContent: "center",
        background: isUser
          ? "linear-gradient(135deg, var(--accent), var(--accent2))"
          : "var(--surface2)",
        border: isUser ? "none" : "1px solid var(--border2)"
      }}>
        {isUser
          ? <User size={16} color="#fff" />
          : <Bot size={16} color="var(--accent)" />
        }
      </div>

      {/* Bubble */}
      <div style={{ maxWidth: "72%", minWidth: 60 }}>
        {badge && (
          <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 6 }}>
            <span className="chip" style={{
              background: `${badge.color}18`, color: badge.color,
              border: `1px solid ${badge.color}30`
            }}>
              <BadgeIcon size={10} />
              {badge.label}
            </span>
            {msg.metadata?.sql_generated && (
              <span className="chip" style={{ background: "#0f172a", color: "var(--text3)", fontFamily: "DM Mono" }}>
                SQL
              </span>
            )}
            {msg.metadata?.chunks_retrieved > 0 && (
              <span className="chip" style={{ background: "#0f172a", color: "var(--text3)", fontFamily: "DM Mono" }}>
                {msg.metadata.chunks_retrieved} chunks
              </span>
            )}
          </div>
        )}

        <div style={{
          padding: "12px 16px",
          background: isUser ? "linear-gradient(135deg, #4f8ef7ee, #6366f1ee)" : "var(--surface)",
          border: isUser ? "none" : "1px solid var(--border)",
          borderRadius: isUser ? "16px 4px 16px 16px" : "4px 16px 16px 16px",
          color: isUser ? "#fff" : "var(--text)",
          fontSize: 14, lineHeight: 1.65,
          boxShadow: isUser ? "0 4px 20px rgba(79,142,247,0.2)" : "none",
          whiteSpace: "pre-wrap", wordBreak: "break-word"
        }}>
          {msg.content}
        </div>

        {msg.metadata?.sql_generated && (
          <details style={{ marginTop: 6 }}>
            <summary style={{
              fontSize: 11, color: "var(--text3)", cursor: "pointer",
              userSelect: "none", listStyle: "none", display: "inline-flex",
              alignItems: "center", gap: 4
            }}>
              <ChevronRight size={11} /> View generated SQL
            </summary>
            <pre style={{
              marginTop: 6, padding: "10px 14px",
              background: "#0a0f1a", border: "1px solid var(--border)",
              borderRadius: 8, fontSize: 12, fontFamily: "DM Mono",
              color: "#7dd3fc", overflowX: "auto", lineHeight: 1.5,
              whiteSpace: "pre-wrap"
            }}>
              {msg.metadata.sql_generated}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}

// ─── Suggested Questions ────────────────────────────────────
const SUGGESTIONS = [
  "What is my current CGPA?",
  "Show me my attendance for all courses",
  "What is the probation policy?",
  "Am I at risk of getting XF?",
  "What are the gold medal requirements?",
  "Show me my grades this semester",
  "Can I freeze my semester?",
  "What is the fee refund policy?",
];

// ─── Dashboard View ─────────────────────────────────────────
function DashboardView({ data }) {
  const { student, grades, attendance, avg_attendance, status_summary, semester_label } = data;
  const cgpa = student?.cgpa ?? 0;

  const gradeChartData = grades.map(g => ({
    name: g.course_id,
    gp: g.grade_points,
    total: g.total_marks,
  }));

  return (
    <div style={{ padding: "0 0 40px 0" }}>

      {/* Header */}
      <div className="fade-up" style={{
        marginBottom: 24,
        padding: "20px 24px",
        background: "linear-gradient(135deg, #111827 0%, #1a1f2e 100%)",
        borderRadius: 18,
        border: "1px solid var(--border)",
        display: "flex", alignItems: "center", gap: 20
      }}>
        <div style={{
          width: 56, height: 56, borderRadius: 16, flexShrink: 0,
          background: "linear-gradient(135deg, var(--accent), var(--accent2))",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 22, fontWeight: 700, color: "#fff"
        }}>
          {student?.name?.[0]}
        </div>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: "var(--text)", letterSpacing: "-0.01em" }}>
            {student?.name}
          </h2>
          <div style={{ display: "flex", gap: 10, marginTop: 5, flexWrap: "wrap" }}>
            <span className="chip" style={{ background: "#4f8ef720", color: "var(--accent)" }}>
              {student?.program}
            </span>
            <span className="chip" style={{ background: "var(--surface2)", color: "var(--text2)" }}>
              Semester {student?.semester}
            </span>
            <span className="chip" style={{ background: "var(--surface2)", color: "var(--text2)" }}>
              {semester_label}
            </span>
            {status_summary?.on_probation && (
              <span className="chip" style={{ background: "#ef444420", color: "var(--danger)" }}>
                <AlertTriangle size={10} /> On Probation
              </span>
            )}
          </div>
        </div>
        <CGPARadial cgpa={cgpa} />
      </div>

      {/* Stat Cards */}
      <div style={{ display: "flex", gap: 14, marginBottom: 20, flexWrap: "wrap" }}>
        <StatCard
          label="CGPA" value={cgpa.toFixed(2)} icon={TrendingUp}
          accent={gradeColor(cgpa)}
          sub={status_summary?.cgpa_status?.toUpperCase()}
          delay={0}
        />
        <StatCard
          label="Avg Attendance" value={`${avg_attendance}%`} icon={Calendar}
          accent={attColor(avg_attendance)}
          sub={`${data.total_courses} courses enrolled`}
          delay={60}
        />
        <StatCard
          label="XF Risk" value={status_summary?.xf_risk_count ?? 0} icon={AlertTriangle}
          accent={status_summary?.xf_risk_count > 0 ? "var(--danger)" : "var(--success)"}
          sub={status_summary?.xf_risk_count > 0 ? "Courses below 75%" : "All courses safe"}
          delay={120}
        />
        <StatCard
          label="Courses" value={data.total_courses} icon={BookOpen}
          accent="var(--accent3)"
          sub={`Enrolled · ${semester_label}`}
          delay={180}
        />
      </div>

      {/* Grades + Chart */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 14, marginBottom: 14 }}>
        <div className="card fade-up" style={{ animationDelay: "200ms" }}>
          <h3 style={{ fontSize: 13, fontWeight: 700, color: "var(--text)", marginBottom: 16,
            display: "flex", alignItems: "center", gap: 8 }}>
            <BarChart2 size={15} color="var(--accent)" /> Grade Breakdown
          </h3>
          <GradeTable grades={grades} />
        </div>

        <div className="card fade-up" style={{ animationDelay: "240ms" }}>
          <h3 style={{ fontSize: 13, fontWeight: 700, color: "var(--text)", marginBottom: 16,
            display: "flex", alignItems: "center", gap: 8 }}>
            <TrendingUp size={15} color="var(--accent2)" /> Grade Points
          </h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={gradeChartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <XAxis dataKey="name" tick={{ fill: "var(--text3)", fontSize: 11 }} />
              <YAxis domain={[0, 4]} tick={{ fill: "var(--text3)", fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: "var(--text2)" }}
                formatter={(v) => [v?.toFixed(2), "Grade Points"]}
              />
              <Bar dataKey="gp" radius={[5, 5, 0, 0]}>
                {gradeChartData.map((e, i) => (
                  <Cell key={i} fill={gradeColor(e.gp)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Attendance */}
      <div className="card fade-up" style={{ animationDelay: "280ms" }}>
        <h3 style={{ fontSize: 13, fontWeight: 700, color: "var(--text)", marginBottom: 18,
          display: "flex", alignItems: "center", gap: 8 }}>
          <Clock size={15} color="var(--warn)" /> Attendance by Course
          <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--text3)", fontWeight: 400 }}>
            Minimum required: 80%
          </span>
        </h3>
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: "0 32px"
        }}>
          {attendance.map((a, i) => <AttBar key={i} {...a} />)}
        </div>
      </div>
    </div>
  );
}

// ─── Chat View ──────────────────────────────────────────────
function ChatView({ studentId, studentName }) {
  const [messages, setMessages] = useState([{
    id: 0, role: "assistant",
    content: `Hello ${studentName?.split(" ")[0]}! 👋 I'm IM|Copilot, your AI academic assistant. I can answer questions about your grades, attendance, GPA, university policies, scholarships, and more. What would you like to know?`,
    intent: "greeting"
  }]);
  const [input, setInput]   = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const sendMessage = useCallback(async (text) => {
    const query = (text || input).trim();
    if (!query || loading) return;

    const userMsg = { id: Date.now(), role: "user", content: query };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, student_id: studentId }),
      });
      const data = await res.json();
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: "assistant",
        content: data.answer,
        intent: data.intent,
        metadata: data.metadata,
      }]);
    } catch (err) {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: "assistant",
        content: "⚠️ Connection error. Make sure the backend is running on http://localhost:8000",
        intent: null,
      }]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, studentId]);

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", padding: "24px 0 8px" }}>
        {messages.map(msg => <ChatMessage key={msg.id} msg={msg} />)}
        {loading && (
          <div className="fade-in" style={{ display: "flex", gap: 12, alignItems: "flex-start", marginBottom: 16 }}>
            <div style={{
              width: 34, height: 34, borderRadius: 10,
              background: "var(--surface2)", border: "1px solid var(--border2)",
              display: "flex", alignItems: "center", justifyContent: "center"
            }}>
              <Bot size={16} color="var(--accent)" />
            </div>
            <div className="card-sm" style={{ display: "inline-block" }}>
              <TypingDots />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions */}
      {messages.length <= 1 && (
        <div className="fade-up" style={{ paddingBottom: 14 }}>
          <p style={{ fontSize: 11, color: "var(--text3)", marginBottom: 8, letterSpacing: "0.06em", textTransform: "uppercase", fontWeight: 600 }}>
            Suggested Questions
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
            {SUGGESTIONS.map(s => (
              <button key={s} onClick={() => sendMessage(s)} style={{
                padding: "6px 12px", borderRadius: 20,
                background: "var(--surface2)", border: "1px solid var(--border2)",
                color: "var(--text2)", fontSize: 12, transition: "all 0.15s"
              }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--accent)"; e.currentTarget.style.color = "var(--accent)"; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border2)"; e.currentTarget.style.color = "var(--text2)"; }}
              >{s}</button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div style={{
        display: "flex", gap: 10, alignItems: "flex-end",
        paddingTop: 12, borderTop: "1px solid var(--border)"
      }}>
        <div style={{ flex: 1, position: "relative" }}>
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask about your GPA, attendance, policies…"
            rows={1}
            style={{
              width: "100%", padding: "12px 16px",
              background: "var(--surface2)", border: "1px solid var(--border2)",
              borderRadius: 12, color: "var(--text)", fontSize: 14,
              resize: "none", fontFamily: "DM Sans",
              outline: "none", lineHeight: 1.5,
              transition: "border-color 0.15s",
              maxHeight: 120, overflowY: "auto"
            }}
            onFocus={e => e.target.style.borderColor = "var(--accent)"}
            onBlur={e => e.target.style.borderColor = "var(--border2)"}
          />
        </div>
        <button
          className="btn-primary"
          onClick={() => sendMessage()}
          disabled={!input.trim() || loading}
          style={{ padding: "12px 16px", borderRadius: 12, flexShrink: 0 }}
        >
          {loading
            ? <Loader2 size={18} style={{ animation: "spin 1s linear infinite" }} />
            : <Send size={18} />
          }
        </button>
      </div>
    </div>
  );
}

// ─── Main App ───────────────────────────────────────────────
export default function App() {
  // user = { username, role, student_id } after login
  const [user,      setUser]      = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [activeTab, setActiveTab] = useState("dashboard");
  const [loadingDB, setLoadingDB] = useState(false);
  const [dbError,   setDbError]   = useState(null);

  // Fetch dashboard after login (students only)
  useEffect(() => {
    if (!user || user.role === "admin" || !user.student_id) return;
    setLoadingDB(true);
    setDbError(null);
    fetch(`${API_BASE}/dashboard/${user.student_id}`)
      .then(r => r.json())
      .then(d => { setDashboard(d); setLoadingDB(false); })
      .catch(e => { setDbError(e.message); setLoadingDB(false); });
  }, [user]);

  const handleLogout = () => {
    setUser(null);
    setDashboard(null);
    setActiveTab("dashboard");
  };

  // ── Not logged in ───────────────────────────────────────
  if (!user) return <><FontLoader /><LoginScreen onLogin={setUser} /></>;

  const student = dashboard?.student;
  const cgpa    = student?.cgpa ?? 0;
  const isAdmin = user.role === "admin";

  const tabs = [
    { id: "dashboard", label: "Dashboard", icon: BarChart2 },
    { id: "chat",      label: "AI Chat",   icon: Bot       },
  ];

  return (
    <>
      <FontLoader />
      <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>

        {/* Sidebar */}
        <aside style={{
          width: 220, flexShrink: 0,
          background: "var(--surface)", borderRight: "1px solid var(--border)",
          display: "flex", flexDirection: "column", padding: "20px 14px"
        }}>
          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "4px 8px", marginBottom: 28 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 9,
              background: "linear-gradient(135deg, var(--accent), var(--accent2))",
              display: "flex", alignItems: "center", justifyContent: "center"
            }}>
              <GraduationCap size={17} color="#fff" />
            </div>
            <span className="serif" style={{ fontSize: 17, fontWeight: 600, letterSpacing: "-0.01em" }}>
              IM<span style={{ color: "var(--accent)" }}>|</span>Copilot
            </span>
          </div>

          {/* User mini-profile */}
          <div style={{
            padding: "12px",
            borderRadius: 10,
            background: "var(--surface2)",
            border: "1px solid var(--border)",
            marginBottom: 20
          }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
                {isAdmin ? "Administrator" : (student?.name ?? user.username)}
              </div>
              <RoleBadge role={user.role} />
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {!isAdmin && student && (
                <span className="chip" style={{ background: "#4f8ef720", color: "var(--accent)", fontSize: 10 }}>
                  {student.program}
                </span>
              )}
              <span className="chip mono" style={{ background: "var(--border)", color: "var(--text3)", fontSize: 10 }}>
                {user.username}
              </span>
              {!isAdmin && (
                <span className="chip mono" style={{ background: "var(--border)", color: "var(--text2)", fontSize: 10 }}>
                  {cgpa.toFixed(2)}
                </span>
              )}
            </div>
          </div>

          {/* Nav */}
          <nav style={{ flex: 1 }}>
            {tabs.map(t => {
              const Icon   = t.icon;
              const active = activeTab === t.id;
              return (
                <button key={t.id} onClick={() => setActiveTab(t.id)} style={{
                  width: "100%", display: "flex", alignItems: "center", gap: 10,
                  padding: "9px 12px", borderRadius: 9, marginBottom: 4,
                  background: active ? "var(--accent)18" : "transparent",
                  color: active ? "var(--accent)" : "var(--text2)",
                  fontWeight: active ? 600 : 400, fontSize: 13,
                  transition: "all 0.15s",
                  borderLeft: active ? "2px solid var(--accent)" : "2px solid transparent"
                }}
                  onMouseEnter={e => { if (!active) e.currentTarget.style.background = "var(--surface2)"; }}
                  onMouseLeave={e => { if (!active) e.currentTarget.style.background = "transparent"; }}
                >
                  <Icon size={16} />
                  {t.label}
                </button>
              );
            })}
          </nav>

          {/* Footer */}
          <div style={{ borderTop: "1px solid var(--border)", paddingTop: 14 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 8px",
              borderRadius: 8, background: "#22c55e10", marginBottom: 8 }}>
              <div style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--success)" }} />
              <span style={{ fontSize: 11, color: "var(--success)" }}>API Connected</span>
            </div>
            <button onClick={handleLogout} style={{
              width: "100%", display: "flex", alignItems: "center", gap: 8,
              padding: "8px 12px", borderRadius: 9, color: "var(--text3)",
              fontSize: 13, background: "transparent", transition: "all 0.15s"
            }}
              onMouseEnter={e => { e.currentTarget.style.background = "var(--surface2)"; e.currentTarget.style.color = "var(--danger)"; }}
              onMouseLeave={e => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text3)"; }}
            >
              <LogOut size={15} /> Sign Out
            </button>
          </div>
        </aside>

        {/* Main content */}
        <main style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>

          {/* Topbar */}
          <header style={{
            height: 56, display: "flex", alignItems: "center",
            padding: "0 28px", borderBottom: "1px solid var(--border)",
            background: "var(--surface)", flexShrink: 0,
            gap: 16
          }}>
            <div style={{ flex: 1 }}>
              <h1 style={{ fontSize: 15, fontWeight: 700, color: "var(--text)" }}>
                {activeTab === "dashboard" ? "Academic Dashboard" : "AI Chat Assistant"}
              </h1>
              <p style={{ fontSize: 11, color: "var(--text3)" }}>
                {activeTab === "dashboard"
                  ? `${dashboard?.semester_label ?? "—"} · ${student?.program ?? (isAdmin ? "Admin View" : "")}`
                  : "Powered by Llama-3 + RAG · IMSciences Handbook"
                }
              </p>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              {dashboard?.status_summary?.xf_risk_count > 0 && (
                <div className="chip" style={{ background: "#ef444418", color: "var(--danger)", fontSize: 11 }}>
                  <AlertTriangle size={10} />
                  {dashboard.status_summary.xf_risk_count} XF Risk
                </div>
              )}
              {dashboard?.status_summary?.on_probation && (
                <div className="chip" style={{ background: "#f59e0b18", color: "var(--warn)", fontSize: 11 }}>
                  <AlertTriangle size={10} /> Probation
                </div>
              )}
              <div style={{ width: 1, height: 20, background: "var(--border)" }} />
              <RoleBadge role={user.role} />
              <span style={{ fontSize: 12, color: "var(--text3)", fontFamily: "DM Mono" }}>
                {user.username}
              </span>
            </div>
          </header>

          {/* Content area */}
          <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px" }}>
            {activeTab === "dashboard" && (
              isAdmin
                ? (
                  // Admin placeholder — extend later
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center",
                    height: "60vh", flexDirection: "column", gap: 14 }}>
                    <Shield size={40} color="var(--accent2)" />
                    <p style={{ color: "var(--text)", fontSize: 16, fontWeight: 600 }}>Admin Dashboard</p>
                    <p style={{ color: "var(--text2)", fontSize: 13 }}>
                      Student management features coming soon.
                    </p>
                  </div>
                )
                : loadingDB
                  ? <div style={{ display: "flex", alignItems: "center", justifyContent: "center",
                      height: "60vh", flexDirection: "column", gap: 14 }}>
                      <Loader2 size={28} color="var(--accent)" style={{ animation: "spin 1s linear infinite" }} />
                      <p style={{ color: "var(--text2)", fontSize: 13 }}>Loading your dashboard…</p>
                    </div>
                  : dbError
                    ? <div style={{ display: "flex", alignItems: "center", justifyContent: "center",
                        height: "60vh", flexDirection: "column", gap: 12 }}>
                        <AlertTriangle size={28} color="var(--danger)" />
                        <p style={{ color: "var(--text2)", fontSize: 13 }}>
                          Could not load dashboard. Is the backend running?
                        </p>
                        <code style={{ fontSize: 11, color: "var(--text3)", fontFamily: "DM Mono" }}>
                          {dbError}
                        </code>
                      </div>
                    : dashboard && <DashboardView data={dashboard} />
            )}
            {activeTab === "chat" && (
              <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
                <ChatView
                  studentId={user.student_id}
                  studentName={isAdmin ? "Admin" : (student?.name ?? user.username)}
                />
              </div>
            )}
          </div>
        </main>
      </div>
    </>
  );
}