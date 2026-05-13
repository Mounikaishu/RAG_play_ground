import React, { useState, useRef } from "react";
import axios from "axios";
import { FaPaperPlane, FaBars, FaTimes, FaCloudUploadAlt, FaSearch, FaSignOutAlt, FaMoon, FaSun, FaUserGraduate, FaChartBar, FaDatabase, FaCompass, FaBriefcase, FaFileAlt, FaUsers, FaTrash, FaChevronDown, FaChevronRight, FaCheckCircle, FaTimesCircle, FaSpinner, FaUserPlus } from "react-icons/fa";
import ReactMarkdown from "react-markdown";
import { AuthProvider, useAuth } from "./context/AuthContext";
import "./App.css";

/* ========== SCORE RING ========== */
function ScoreRing({ score, size = 64, strokeWidth = 5 }) {
  const r = (size - strokeWidth) / 2, circ = 2 * Math.PI * r;
  const color = score >= 80 ? "#22c55e" : score >= 50 ? "#f59e0b" : "#ef4444";
  return (
    <svg width={size} height={size}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--color-border)" strokeWidth={strokeWidth} />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={strokeWidth}
        strokeDasharray={circ} strokeDashoffset={circ - (score/100)*circ}
        strokeLinecap="round" transform={`rotate(-90 ${size/2} ${size/2})`}
        style={{ transition: "stroke-dashoffset 1s ease" }} />
      <text x="50%" y="50%" textAnchor="middle" dy="0.35em"
        fill="var(--color-text-primary)" fontSize={size*0.22} fontWeight="700">{score}</text>
    </svg>
  );
}

/* ========== LOGIN PAGE ========== */
function LoginPage() {
  const { login } = useAuth();
  const [form, setForm] = useState({ roll_no: "", password: "" });
  const [error, setError] = useState("");
  const [warningMsg, setWarningMsg] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault(); setError(""); setWarningMsg(""); setLoading(true);
    try {
      const res = await login(form.roll_no, form.password);
      if (res.warning) {
        setWarningMsg(res.warning);
      }
    } catch (err) {
      if (err.response) {
        const detail = err.response.data?.detail;
        // Handle Pydantic validation errors (array of objects)
        if (Array.isArray(detail)) {
          setError(detail.map(d => d.msg || JSON.stringify(d)).join(", "));
        } else if (typeof detail === "object" && detail !== null) {
          setError(detail.msg || JSON.stringify(detail));
        } else {
          setError(detail || `Server error: ${err.response.status}`);
        }
      } else if (err.request) {
        setError("Cannot reach backend. Is it running on https://rag-play-ground.onrender.com?");
      } else {
        setError(err.message || "Something went wrong.");
      }
    }
    setLoading(false);
  };

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  return (
    <div className="login-page">
      <div className="login-bg-orb login-orb-1" />
      <div className="login-bg-orb login-orb-2" />
      <div className="login-card">
        <div className="login-brand">
          <div className="login-logo">🎓</div>
          <h1>PlaceAI</h1>
          <p>AI-Powered Placement & Career Guidance</p>
        </div>
        <div className="login-tabs">
          <button className="active">Student Login</button>
        </div>
        <form onSubmit={handleSubmit} className="login-form">
          <input placeholder="Roll Number / Registration ID" value={form.roll_no} onChange={e => set("roll_no", e.target.value)} required />
          <input placeholder="Password" type="password" value={form.password} onChange={e => set("password", e.target.value)} required />
          <div className="login-info" style={{ fontSize: "0.82rem", color: "var(--color-text-secondary)", padding: "4px 0 8px", lineHeight: 1.4 }}>
            🔑 Your account is created by the exam cell. Use your registration number and the default password provided to you.
          </div>
          {error && <div className="login-error">{error}</div>}
          {warningMsg && <div className="login-success" style={{ color: "#f59e0b", fontSize: "0.85rem", padding: "8px 0" }}>{warningMsg}</div>}
          <button type="submit" className="login-submit" disabled={loading}>
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}

/* ========== STUDENT DASHBOARD ========== */
function StudentDashboard() {
  const { user, logout, authHeaders, API } = useAuth();
  const [tab, setTab] = useState("mentor");
  const [chat, setChat] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sidebar, setSidebar] = useState(true);
  const [theme, setTheme] = useState("dark");
  const [file, setFile] = useState(null);
  const [uploadMsg, setUploadMsg] = useState("");
  const [uploading, setUploading] = useState(false);
  const [atsData, setAtsData] = useState(null);
  const [atsLoading, setAtsLoading] = useState(false);
  const [careerGoal, setCareerGoal] = useState("");
  const [targetCompany, setTargetCompany] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const chatEnd = useRef(null);
  const fileRef = useRef(null);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next); document.documentElement.setAttribute("data-theme", next);
  };

  const uploadResume = async () => {
    if (!file) return;
    setUploading(true); setUploadMsg("");
    const fd = new FormData(); fd.append("file", file);
    try {
      const r = await axios.post(`${API}/student/upload-resume`, fd, {
        headers: { ...authHeaders.headers, "Content-Type": "multipart/form-data" }, timeout: 120000,
      });
      setUploadMsg(r.data.message); setFile(null);
      if (fileRef.current) fileRef.current.value = "";
    } catch { setUploadMsg("❌ Upload failed."); }
    setUploading(false);
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const q = input; setInput(""); setLoading(true);
    setChat(p => [...p, { user: q, bot: null }]);
    try {
      const fd = new FormData();
      fd.append("question", q); fd.append("mode", tab);
      if (careerGoal) fd.append("career_goal", careerGoal);
      if (targetCompany) fd.append("target_company", targetCompany);
      if (targetRole) fd.append("target_role", targetRole);
      const r = await axios.post(`${API}/student/chat`, fd, {
        headers: { ...authHeaders.headers, "Content-Type": "multipart/form-data" }, timeout: 120000,
      });
      setChat(p => { const c = [...p]; c[c.length-1].bot = r.data.answer; return c; });
    } catch { setChat(p => { const c = [...p]; c[c.length-1].bot = "⚠️ Error."; return c; }); }
    setLoading(false);
    setTimeout(() => chatEnd.current?.scrollIntoView({ behavior: "smooth" }), 100);
  };

  const fetchATS = async () => {
    setAtsLoading(true);
    try {
      const r = await axios.post(`${API}/student/ats-score`, {}, authHeaders);
      setAtsData(r.data);
    } catch { setAtsData({ error: "Failed to fetch ATS score." }); }
    setAtsLoading(false);
  };

  const suggestions = {
    mentor: [
      { icon: "🚀", text: "I want to become an AI Engineer" },
      { icon: "💻", text: "Guide me for backend development career" },
      { icon: "📊", text: "What skills do I need for data science?" },
      { icon: "🗺️", text: "Create a 6-month placement preparation plan" },
    ],
    interview_prep: [
      { icon: "🏢", text: "Prepare me for Amazon SDE interview" },
      { icon: "💻", text: "Google technical round questions" },
      { icon: "🎯", text: "Common DSA questions for placements" },
      { icon: "🧠", text: "Behavioral interview preparation" },
    ],
    ats: [
      { icon: "💯", text: "Score my resume for ATS compatibility" },
      { icon: "🔍", text: "What keywords am I missing?" },
      { icon: "✍️", text: "How can I improve my resume?" },
    ],
    resume_match: [
      { icon: "⚖️", text: "Compare me with placed alumni" },
      { icon: "📈", text: "What's my skill gap vs successful candidates?" },
      { icon: "🎯", text: "Am I ready for placement season?" },
    ],
  };

  const tabLabels = {
    mentor: { icon: <FaCompass />, label: "Career Guidance" },
    interview_prep: { icon: <FaBriefcase />, label: "Interview Prep" },
    ats: { icon: <FaFileAlt />, label: "ATS Score" },
    resume_match: { icon: <FaUsers />, label: "Resume Match" },
  };

  const curSuggestions = suggestions[tab] || suggestions.mentor;

  return (
    <div className="app-container">
      <aside className={`sidebar ${sidebar ? "open" : ""}`}>
        <div className="sidebar-header">
          <div className="sidebar-brand"><div className="sidebar-logo">🎓</div><div className="sidebar-brand-text"><h2>PlaceAI</h2><span>Student Portal</span></div></div>
        </div>
        <div className="sidebar-nav">
          {Object.entries(tabLabels).map(([k, v]) => (
            <button key={k} className={`sidebar-nav-btn ${tab === k ? "active" : ""}`} onClick={() => { setTab(k); setChat([]); setAtsData(null); }}>
              {v.icon}<span>{v.label}</span>
            </button>
          ))}
        </div>
        <div className="sidebar-upload" style={{ flex: 1, overflow: "auto", padding: "var(--space-4)" }}>
          <div className="sidebar-section-title">Upload Resume</div>
          <div className="upload-zone">
            <input type="file" accept=".pdf" ref={fileRef} onChange={e => setFile(e.target.files[0])} />
            <span className="upload-zone-icon"><FaCloudUploadAlt /></span>
            <div className="upload-zone-text">{file ? file.name : "Drop PDF here"}</div>
          </div>
          {file && <button className="upload-btn" onClick={uploadResume} disabled={uploading}>{uploading ? "Uploading..." : "Upload Resume"}</button>}
          {uploadMsg && <div className="upload-status">{uploadMsg}</div>}

          {tab === "interview_prep" && (
            <div className="sidebar-context-fields">
              <div className="sidebar-section-title" style={{marginTop: 12}}>Interview Context</div>
              <input placeholder="Target Company" value={targetCompany} onChange={e => setTargetCompany(e.target.value)} className="context-input" />
              <input placeholder="Target Role" value={targetRole} onChange={e => setTargetRole(e.target.value)} className="context-input" />
            </div>
          )}
          {tab === "mentor" && (
            <div className="sidebar-context-fields">
              <div className="sidebar-section-title" style={{marginTop: 12}}>Career Goal</div>
              <input placeholder="e.g. AI Engineer" value={careerGoal} onChange={e => setCareerGoal(e.target.value)} className="context-input" />
            </div>
          )}
        </div>
        <div className="sidebar-footer">
          <div className="sidebar-user"><FaUserGraduate /><span>{user?.name}</span><span className="sidebar-dept">{user?.department}</span></div>
          <button className="sidebar-logout" onClick={logout}><FaSignOutAlt /> Logout</button>
        </div>
      </aside>

      <main className="main-content">
        <div className="top-bar">
          <div className="top-bar-left">
            <button className="sidebar-toggle" onClick={() => setSidebar(!sidebar)}>{sidebar ? <FaTimes /> : <FaBars />}</button>
            <span className="top-bar-title">{tabLabels[tab]?.icon} {tabLabels[tab]?.label}</span>
          </div>
          <div className="top-bar-right">
            <button className="theme-toggle" onClick={toggleTheme}>{theme === "dark" ? <FaSun /> : <FaMoon />}</button>
          </div>
        </div>

        {tab === "ats" && !atsData && chat.length === 0 ? (
          <div className="welcome-container">
            <div className="welcome-icon">📋</div>
            <h2>ATS Resume Analysis</h2>
            <p>Upload your resume and get a detailed ATS compatibility score.</p>
            <button className="ats-fetch-btn" onClick={fetchATS} disabled={atsLoading}>{atsLoading ? "Analyzing..." : "🔍 Analyze My Resume"}</button>
            <div className="welcome-features">
              {curSuggestions.map((s, i) => (
                <button key={i} className="feature-card" onClick={() => { setInput(s.text); setTab("ats"); }}>
                  <span className="feature-card-icon">{s.icon}</span><h4>{s.text}</h4>
                </button>
              ))}
            </div>
          </div>
        ) : tab === "ats" && atsData && !atsData.error ? (
          <div className="ats-results">
            <div className="ats-score-card">
              <ScoreRing score={atsData.overall} size={120} strokeWidth={8} />
              <h3>ATS Score: {atsData.overall}/100</h3>
              <p>{atsData.summary}</p>
            </div>
            <div className="ats-categories">
              {atsData.categories && Object.entries(atsData.categories).map(([k, v]) => (
                <div key={k} className="ats-cat-card">
                  <div className="ats-cat-header"><span className="ats-cat-name">{k}</span><span className="ats-cat-score">{v.score}/20</span></div>
                  <div className="ats-cat-bar"><div className="ats-cat-fill" style={{ width: `${(v.score/20)*100}%` }} /></div>
                  <p className="ats-cat-comment">{v.comment}</p>
                </div>
              ))}
            </div>
            {atsData.keywords_found?.length > 0 && (
              <div className="ats-keywords"><h4>✅ Keywords Found</h4><div className="ats-tags">{atsData.keywords_found.map((k,i) => <span key={i} className="ats-tag found">{k}</span>)}</div></div>
            )}
            {atsData.keywords_missing?.length > 0 && (
              <div className="ats-keywords"><h4>❌ Missing Keywords</h4><div className="ats-tags">{atsData.keywords_missing.map((k,i) => <span key={i} className="ats-tag missing">{k}</span>)}</div></div>
            )}
            <button className="ats-fetch-btn" onClick={() => setAtsData(null)} style={{marginTop: 16}}>← Back</button>
          </div>
        ) : chat.length === 0 ? (
          <div className="welcome-container">
            <div className="welcome-icon">{tab === "mentor" ? "🧭" : tab === "interview_prep" ? "🎯" : "⚖️"}</div>
            <h2>{tabLabels[tab]?.label}</h2>
            <p>Ask questions powered by our institutional knowledge base of alumni profiles, interview experiences, and career roadmaps.</p>
            <div className="welcome-features">
              {curSuggestions.map((s, i) => (
                <button key={i} className="feature-card" onClick={() => setInput(s.text)}>
                  <span className="feature-card-icon">{s.icon}</span><h4>{s.text}</h4>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="chat-window">
            {chat.map((m, i) => (
              <React.Fragment key={i}>
                <div className="chat-row user-row"><div className="avatar user-avatar">U</div><div className="user-message">{m.user}</div></div>
                {m.bot && <div className="chat-row bot-row"><div className="avatar bot-avatar">AI</div><div className="bot-message"><ReactMarkdown>{m.bot}</ReactMarkdown></div></div>}
              </React.Fragment>
            ))}
            {loading && <div className="typing-indicator"><div className="avatar bot-avatar">AI</div><div className="typing-dots"><span/><span/><span/></div></div>}
            <div ref={chatEnd} />
          </div>
        )}

        {(tab !== "ats" || chat.length > 0 || (atsData && atsData.error)) && (
          <div className="input-section">
            <div className="input-wrapper">
              <input value={input} onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); sendMessage(); } }}
                placeholder={tab === "interview_prep" ? "Ask about interview preparation..." : tab === "resume_match" ? "Ask about resume matching..." : "Ask your career question..."}
                disabled={loading} />
              <button className="send-btn" onClick={sendMessage} disabled={!input.trim() || loading}><FaPaperPlane /></button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

/* ========== PLACEMENT CELL DASHBOARD ========== */
function PlacementDashboard() {
  const { user, logout, authHeaders, API } = useAuth();
  const [tab, setTab] = useState("search");
  const [sidebar, setSidebar] = useState(true);
  const [theme, setTheme] = useState("dark");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [analytics, setAnalytics] = useState(null);
  const [kbTitle, setKbTitle] = useState("");
  const [kbContent, setKbContent] = useState("");
  const [kbCategory, setKbCategory] = useState("resource");
  const [kbCompany, setKbCompany] = useState("");
  const [kbMsg, setKbMsg] = useState("");
  // File upload state
  const [kbFiles, setKbFiles] = useState([]);
  const [kbFileCategory, setKbFileCategory] = useState("alumni_resumes");
  const [kbSelectedFiles, setKbSelectedFiles] = useState([]);
  const [kbUploading, setKbUploading] = useState(false);
  const [kbUploadResults, setKbUploadResults] = useState(null);
  const [kbFilesLoading, setKbFilesLoading] = useState(false);
  const [kbTextOpen, setKbTextOpen] = useState(false);
  const [kbDeleting, setKbDeleting] = useState(null);
  const kbFileRef = useRef(null);
  // Registration state
  const [regForm, setRegForm] = useState({ name: "", roll_no: "", department: "IT", college_email: "", passing_out_year: 2028, skills: "" });
  const [regLoading, setRegLoading] = useState(false);
  const [regResult, setRegResult] = useState(null);
  const [bulkJson, setBulkJson] = useState("");
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkResults, setBulkResults] = useState(null);
  const [regMode, setRegMode] = useState("single"); // "single" or "bulk"

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next); document.documentElement.setAttribute("data-theme", next);
  };

  const searchCandidates = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true); setSearchResults(null);
    try {
      const fd = new FormData(); fd.append("query", searchQuery);
      const r = await axios.post(`${API}/placement/search`, fd, {
        headers: { ...authHeaders.headers, "Content-Type": "multipart/form-data" }, timeout: 120000,
      });
      setSearchResults(r.data);
    } catch { setSearchResults({ answer: "⚠️ Search failed.", candidates: [] }); }
    setSearching(false);
  };

  const loadAnalytics = async () => {
    try {
      const r = await axios.get(`${API}/placement/analytics`, authHeaders);
      setAnalytics(r.data);
    } catch { setAnalytics({ error: true }); }
  };

  const uploadKB = async () => {
    if (!kbTitle || !kbContent) return;
    try {
      const fd = new FormData();
      fd.append("title", kbTitle); fd.append("content", kbContent);
      fd.append("category", kbCategory); fd.append("company", kbCompany);
      await axios.post(`${API}/placement/upload-kb`, fd, {
        headers: { ...authHeaders.headers, "Content-Type": "multipart/form-data" },
      });
      setKbMsg("✅ Added!"); setKbTitle(""); setKbContent(""); setKbCompany("");
    } catch { setKbMsg("❌ Failed."); }
  };

  const fetchKbFiles = async () => {
    setKbFilesLoading(true);
    try {
      const r = await axios.get(`${API}/placement/kb-files`, authHeaders);
      setKbFiles(r.data.files || []);
    } catch { setKbFiles([]); }
    setKbFilesLoading(false);
  };

  const uploadKbFiles = async () => {
    if (!kbSelectedFiles.length) return;
    setKbUploading(true); setKbUploadResults(null);
    const fd = new FormData();
    fd.append("category", kbFileCategory);
    for (const f of kbSelectedFiles) fd.append("files", f);
    try {
      const r = await axios.post(`${API}/placement/upload-kb-files`, fd, {
        headers: { ...authHeaders.headers, "Content-Type": "multipart/form-data" }, timeout: 180000,
      });
      setKbUploadResults(r.data);
      setKbSelectedFiles([]);
      if (kbFileRef.current) kbFileRef.current.value = "";
      fetchKbFiles();
    } catch (err) {
      setKbUploadResults({ message: "❌ Upload failed.", results: [] });
    }
    setKbUploading(false);
  };

  const deleteKbFile = async (fileHash, filename) => {
    if (!window.confirm(`Delete "${filename}" from the knowledge base?`)) return;
    setKbDeleting(fileHash);
    try {
      await axios.delete(`${API}/placement/delete-kb-file/${fileHash}`, authHeaders);
      setKbFiles(prev => prev.filter(f => f.file_hash !== fileHash));
    } catch { alert("Failed to delete file."); }
    setKbDeleting(null);
  };

  const registerStudent = async () => {
    setRegLoading(true); setRegResult(null);
    try {
      const payload = { ...regForm, skills: regForm.skills ? regForm.skills.split(",").map(s => s.trim()).filter(Boolean) : [] };
      const r = await axios.post(`${API}/auth/register`, payload, authHeaders);
      setRegResult({ success: true, message: r.data.message, default_password: r.data.default_password });
      setRegForm({ name: "", roll_no: "", department: "IT", college_email: "", passing_out_year: 2028, skills: "" });
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = Array.isArray(detail) ? detail.map(d => d.msg || JSON.stringify(d)).join(", ") : (typeof detail === "string" ? detail : JSON.stringify(detail));
      setRegResult({ success: false, message: msg || "Registration failed." });
    }
    setRegLoading(false);
  };

  const bulkRegister = async () => {
    setBulkLoading(true); setBulkResults(null);
    try {
      const parsed = JSON.parse(bulkJson);
      const payload = Array.isArray(parsed) ? { students: parsed } : parsed;
      const r = await axios.post(`${API}/auth/bulk-register`, payload, authHeaders);
      setBulkResults(r.data);
    } catch (err) {
      if (err instanceof SyntaxError) {
        setBulkResults({ message: "❌ Invalid JSON format. Please check your input." });
      } else {
        const detail = err.response?.data?.detail;
        const msg = typeof detail === "string" ? detail : JSON.stringify(detail);
        setBulkResults({ message: msg || "❌ Bulk registration failed." });
      }
    }
    setBulkLoading(false);
  };

  const tabLabels = {
    search: { icon: <FaSearch />, label: "Search Candidates" },
    register: { icon: <FaUserPlus />, label: "Register Students" },
    kb: { icon: <FaDatabase />, label: "Knowledge Base" },
    analytics: { icon: <FaChartBar />, label: "Analytics" },
  };

  return (
    <div className="app-container">
      <aside className={`sidebar ${sidebar ? "open" : ""}`}>
        <div className="sidebar-header">
          <div className="sidebar-brand"><div className="sidebar-logo">🏛️</div><div className="sidebar-brand-text"><h2>PlaceAI</h2><span>Placement Cell</span></div></div>
        </div>
        <div className="sidebar-nav">
          {Object.entries(tabLabels).map(([k, v]) => (
            <button key={k} className={`sidebar-nav-btn ${tab === k ? "active" : ""}`} onClick={() => { setTab(k); if (k === "analytics") loadAnalytics(); if (k === "kb") fetchKbFiles(); }}>
              {v.icon}<span>{v.label}</span>
            </button>
          ))}
        </div>
        <div style={{ flex: 1 }} />
        <div className="sidebar-footer">
          <div className="sidebar-user"><FaUserGraduate /><span>{user?.name}</span><span className="sidebar-dept">Admin</span></div>
          <button className="sidebar-logout" onClick={logout}><FaSignOutAlt /> Logout</button>
        </div>
      </aside>

      <main className="main-content">
        <div className="top-bar">
          <div className="top-bar-left">
            <button className="sidebar-toggle" onClick={() => setSidebar(!sidebar)}>{sidebar ? <FaTimes /> : <FaBars />}</button>
            <span className="top-bar-title">{tabLabels[tab]?.icon} {tabLabels[tab]?.label}</span>
          </div>
          <div className="top-bar-right"><button className="theme-toggle" onClick={toggleTheme}>{theme === "dark" ? <FaSun /> : <FaMoon />}</button></div>
        </div>

        {tab === "search" && (
          <>
            <div className="search-hero">
              <h2>🔍 Find the Best Candidates</h2>
              <p>Describe your requirements in natural language</p>
              <div className="search-bar">
                <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter") searchCandidates(); }}
                  placeholder='e.g. "Students with Python, AI projects, hackathon experience"' />
                <button onClick={searchCandidates} disabled={searching}>{searching ? "..." : <FaSearch />}</button>
              </div>
            </div>
            {searchResults && (
              <div className="search-results">
                {searchResults.candidates?.length > 0 && (
                  <div className="candidates-grid">
                    {searchResults.candidates.map((c, i) => (
                      <div key={i} className="candidate-card">
                        <div className="candidate-top">
                          <div className="candidate-rank">#{i+1}</div>
                          <div className="candidate-info">
                            <div className="candidate-name">{c.name}</div>
                            <div className="candidate-dept">{c.department}</div>
                          </div>
                          <ScoreRing score={c.relevance_score} size={52} strokeWidth={4} />
                        </div>
                        <div className="candidate-skills">
                          {(c.skills||[]).slice(0,5).map((s,j) => <span key={j} className="skill-tag">{s}</span>)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {searchResults.answer && (
                  <div className="search-ai-answer"><div className="avatar bot-avatar">AI</div><div className="bot-message"><ReactMarkdown>{searchResults.answer}</ReactMarkdown></div></div>
                )}
              </div>
            )}
          </>
        )}

        {tab === "kb" && (
          <div className="kb-panel">
            <h2>📚 Knowledge Base Management</h2>

            {/* ── File Upload Section ── */}
            <div className="kb-section">
              <h3 className="kb-section-title">📤 Upload Files</h3>
              <p className="kb-section-desc">Upload PDF or TXT files to be processed through the ingestion pipeline and stored in ChromaDB.</p>
              <div className="kb-upload-controls">
                <select value={kbFileCategory} onChange={e => setKbFileCategory(e.target.value)} className="kb-select">
                  <option value="alumni_resumes">Alumni Resumes</option>
                  <option value="interview_experiences">Interview Experiences</option>
                  <option value="placement_materials">Placement Materials</option>
                </select>
              </div>
              <div className="kb-drop-zone" onClick={() => kbFileRef.current?.click()}>
                <input type="file" accept=".pdf,.txt" multiple ref={kbFileRef} onChange={e => setKbSelectedFiles(Array.from(e.target.files))} style={{ display: "none" }} />
                <FaCloudUploadAlt className="kb-drop-icon" />
                {kbSelectedFiles.length > 0 ? (
                  <div className="kb-drop-text">
                    <strong>{kbSelectedFiles.length} file(s) selected</strong>
                    <span>{kbSelectedFiles.map(f => f.name).join(", ")}</span>
                  </div>
                ) : (
                  <div className="kb-drop-text">
                    <strong>Click to select files</strong>
                    <span>Supports .pdf and .txt files</span>
                  </div>
                )}
              </div>
              {kbSelectedFiles.length > 0 && (
                <button className="kb-upload-btn" onClick={uploadKbFiles} disabled={kbUploading}>
                  {kbUploading ? <><FaSpinner className="spin-icon" /> Processing...</> : `Upload ${kbSelectedFiles.length} File(s)`}
                </button>
              )}

              {/* Upload Results */}
              {kbUploadResults && (
                <div className="kb-results">
                  <div className="kb-results-summary">{kbUploadResults.message}</div>
                  {(kbUploadResults.results || []).map((r, i) => (
                    <div key={i} className={`kb-result-item ${r.status}`}>
                      <span className="kb-result-icon">{r.status === "success" ? <FaCheckCircle /> : r.status === "skipped" ? "⏩" : <FaTimesCircle />}</span>
                      <span className="kb-result-name">{r.filename}</span>
                      {r.chunks > 0 && <span className="kb-result-chunks">{r.chunks} chunks</span>}
                      {r.error && <span className="kb-result-error">{r.error}</span>}
                      {r.reason && <span className="kb-result-reason">{r.reason}</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* ── Ingested Documents Table ── */}
            <div className="kb-section">
              <div className="kb-section-header">
                <h3 className="kb-section-title">📋 Ingested Documents ({kbFiles.length})</h3>
                <button className="kb-refresh-btn" onClick={fetchKbFiles} disabled={kbFilesLoading}>
                  {kbFilesLoading ? "Loading..." : "Refresh"}
                </button>
              </div>
              {kbFiles.length > 0 ? (
                <div className="kb-files-table">
                  <div className="kb-files-header">
                    <span>Filename</span><span>Category</span><span>Chunks</span><span>Ingested</span><span></span>
                  </div>
                  {kbFiles.map((f, i) => (
                    <div key={i} className="kb-files-row">
                      <span className="kb-file-name" title={f.filename}>{f.filename}</span>
                      <span className="kb-file-cat">{(f.folder || "").replace(/_/g, " ")}</span>
                      <span className="kb-file-chunks">{f.chunk_count}</span>
                      <span className="kb-file-date">{f.ingested_at ? new Date(f.ingested_at).toLocaleDateString() : "—"}</span>
                      <button className="kb-file-del" onClick={() => deleteKbFile(f.file_hash, f.filename)} disabled={kbDeleting === f.file_hash} title="Delete">
                        {kbDeleting === f.file_hash ? <FaSpinner className="spin-icon" /> : <FaTrash />}
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="kb-empty">No files ingested yet. Upload files above to populate the knowledge base.</div>
              )}
            </div>

            {/* ── Quick Text Entry (Collapsed) ── */}
            <div className="kb-section">
              <button className="kb-text-toggle" onClick={() => setKbTextOpen(!kbTextOpen)}>
                {kbTextOpen ? <FaChevronDown /> : <FaChevronRight />}
                <span>📝 Quick Text Entry</span>
              </button>
              {kbTextOpen && (
                <div className="kb-form">
                  <select value={kbCategory} onChange={e => setKbCategory(e.target.value)} className="kb-select">
                    <option value="resource">Resource</option>
                    <option value="interview">Interview Experience</option>
                    <option value="alumni">Alumni Profile</option>
                    <option value="roadmap">Skill Roadmap</option>
                  </select>
                  <input placeholder="Title" value={kbTitle} onChange={e => setKbTitle(e.target.value)} className="context-input" />
                  {(kbCategory === "interview" || kbCategory === "alumni") && (
                    <input placeholder="Company" value={kbCompany} onChange={e => setKbCompany(e.target.value)} className="context-input" />
                  )}
                  <textarea placeholder="Content..." value={kbContent} onChange={e => setKbContent(e.target.value)} className="kb-textarea" rows={6} />
                  <button className="upload-btn" onClick={uploadKB}>Add to Knowledge Base</button>
                  {kbMsg && <div className="upload-status">{kbMsg}</div>}
                </div>
              )}
            </div>
          </div>
        )}

        {tab === "register" && (
          <div className="kb-panel">
            <h2>👨‍🎓 Register Students</h2>
            <div className="reg-mode-tabs">
              <button className={`reg-mode-btn ${regMode === "single" ? "active" : ""}`} onClick={() => setRegMode("single")}>Single Student</button>
              <button className={`reg-mode-btn ${regMode === "bulk" ? "active" : ""}`} onClick={() => setRegMode("bulk")}>Bulk Registration</button>
            </div>

            {regMode === "single" && (
              <div className="kb-section">
                <h3 className="kb-section-title">📝 Register Individual Student</h3>
                <p className="kb-section-desc">Student will receive the default password: <code>svecw@2026</code></p>
                <div className="reg-form">
                  <div className="reg-row">
                    <input placeholder="Full Name *" value={regForm.name} onChange={e => setRegForm(p => ({...p, name: e.target.value}))} className="context-input" />
                    <input placeholder="Roll Number *" value={regForm.roll_no} onChange={e => setRegForm(p => ({...p, roll_no: e.target.value}))} className="context-input" />
                  </div>
                  <div className="reg-row">
                    <select value={regForm.department} onChange={e => setRegForm(p => ({...p, department: e.target.value}))} className="kb-select">
                      <option value="IT">IT</option>
                      <option value="CSE">CSE</option>
                      <option value="ECE">ECE</option>
                      <option value="EEE">EEE</option>
                      <option value="MECH">MECH</option>
                      <option value="CIVIL">CIVIL</option>
                      <option value="AIDS">AIDS</option>
                      <option value="AIML">AIML</option>
                    </select>
                    <input type="number" placeholder="Passing Out Year" value={regForm.passing_out_year} onChange={e => setRegForm(p => ({...p, passing_out_year: parseInt(e.target.value) || 2028}))} className="context-input" />
                  </div>
                  <input placeholder="College Email (e.g. 24b01a1276@svecw.edu.in) *" value={regForm.college_email} onChange={e => setRegForm(p => ({...p, college_email: e.target.value}))} className="context-input" />
                  <input placeholder="Skills (comma-separated, e.g. Python, ML, DSA)" value={regForm.skills} onChange={e => setRegForm(p => ({...p, skills: e.target.value}))} className="context-input" />
                  <button className="kb-upload-btn" onClick={registerStudent} disabled={regLoading || !regForm.name || !regForm.roll_no || !regForm.college_email}>
                    {regLoading ? <><FaSpinner className="spin-icon" /> Registering...</> : "Register Student"}
                  </button>
                </div>
                {regResult && (
                  <div className={`kb-results ${regResult.success ? "" : "error"}`}>
                    <div className="kb-results-summary">{regResult.message}</div>
                    {regResult.default_password && <div className="reg-password-note">🔑 Default Password: <strong>{regResult.default_password}</strong></div>}
                  </div>
                )}
              </div>
            )}

            {regMode === "bulk" && (
              <div className="kb-section">
                <h3 className="kb-section-title">📋 Bulk Registration (JSON)</h3>
                <p className="kb-section-desc">Paste a JSON array of students. All will receive the default password.</p>
                <div className="bulk-example">
                  <button className="bulk-example-btn" onClick={() => setBulkJson(JSON.stringify([{name:"Student Name",roll_no:"24b01a1276",department:"IT",college_email:"24b01a1276@svecw.edu.in",passing_out_year:2028},{name:"Another Student",roll_no:"24b01a1278",department:"CSE",college_email:"24b01a1278@svecw.edu.in",passing_out_year:2028}], null, 2))}>
                    📄 Load Example
                  </button>
                </div>
                <textarea className="kb-textarea bulk-textarea" rows={12} placeholder='[\n  { "name": "...", "roll_no": "...", "department": "IT", "college_email": "...@svecw.edu.in", "passing_out_year": 2028 }\n]' value={bulkJson} onChange={e => setBulkJson(e.target.value)} />
                <button className="kb-upload-btn" onClick={bulkRegister} disabled={bulkLoading || !bulkJson.trim()}>
                  {bulkLoading ? <><FaSpinner className="spin-icon" /> Processing...</> : "Register All Students"}
                </button>
                {bulkResults && (
                  <div className="kb-results">
                    <div className="kb-results-summary">{bulkResults.message}</div>
                    {bulkResults.default_password && <div className="reg-password-note">🔑 Default Password: <strong>{bulkResults.default_password}</strong></div>}
                    {(bulkResults.results || []).map((r, i) => (
                      <div key={i} className={`kb-result-item ${r.status}`}>
                        <span className="kb-result-icon">{r.status === "success" ? <FaCheckCircle /> : <FaTimesCircle />}</span>
                        <span className="kb-result-name">{r.roll_no} — {r.name}</span>
                        {r.error && <span className="kb-result-error">{r.error}</span>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {tab === "analytics" && (
          <div className="analytics-panel">
            <h2>📊 Placement Analytics</h2>
            {analytics && !analytics.error ? (
              <div className="analytics-grid">
                <div className="analytics-card"><div className="analytics-number">{analytics.total_students}</div><div className="analytics-label">Total Students</div></div>
                <div className="analytics-card"><div className="analytics-number">{analytics.resumes_uploaded}</div><div className="analytics-label">Resumes Uploaded</div></div>
                <div className="analytics-card"><div className="analytics-number">{analytics.kb_stats?.institutional_kb || 0}</div><div className="analytics-label">KB Documents</div></div>
                <div className="analytics-card"><div className="analytics-number">{analytics.kb_stats?.interview_experiences || 0}</div><div className="analytics-label">Interview Experiences</div></div>
                {analytics.top_skills?.length > 0 && (
                  <div className="analytics-card wide">
                    <h4>Top Skills</h4>
                    <div className="analytics-skills">{analytics.top_skills.map((s,i) => (
                      <div key={i} className="analytics-skill-row">
                        <span>{s.skill}</span>
                        <div className="analytics-skill-bar"><div style={{ width: `${Math.min(100, (s.count / (analytics.top_skills[0]?.count || 1)) * 100)}%` }} /></div>
                        <span className="analytics-skill-count">{s.count}</span>
                      </div>
                    ))}</div>
                  </div>
                )}
                {analytics.departments && Object.keys(analytics.departments).length > 0 && (
                  <div className="analytics-card wide">
                    <h4>Department Distribution</h4>
                    <div className="analytics-skills">{Object.entries(analytics.departments).map(([d, c], i) => (
                      <div key={i} className="analytics-skill-row">
                        <span>{d}</span>
                        <div className="analytics-skill-bar"><div style={{ width: `${Math.min(100, (c / analytics.total_students) * 100)}%` }} /></div>
                        <span className="analytics-skill-count">{c}</span>
                      </div>
                    ))}</div>
                  </div>
                )}
              </div>
            ) : (
              <button className="ats-fetch-btn" onClick={loadAnalytics}>Load Analytics</button>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

/* ========== ROOT APP ========== */
function AppContent() {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading-screen"><div className="loading-spinner" /><p>Loading PlaceAI...</p></div>;
  if (!user) return <LoginPage />;
  if (user.role === "placement_cell") return <PlacementDashboard />;
  return <StudentDashboard />;
}

export default function App() {
  return <AuthProvider><AppContent /></AuthProvider>;
}