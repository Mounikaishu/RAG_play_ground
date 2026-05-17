import React, { useState, useRef, useEffect } from "react";
import axios from "axios";
import { FaPaperPlane, FaBars, FaTimes, FaCloudUploadAlt, FaMoon, FaSun, FaUserGraduate, FaCompass, FaBriefcase, FaFileAlt, FaUsers } from "react-icons/fa";
import ReactMarkdown from "react-markdown";
import "./App.css";

const API = process.env.REACT_APP_API_URL || (window.location.hostname === "localhost" ? "http://localhost:8000" : "https://rag-play-ground.onrender.com");

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

export default function App() {
  const [sessionId, setSessionId] = useState("");
  
  useEffect(() => {
    // Generate a fresh session ID when the app loads (refresh = new session)
    setSessionId(Math.random().toString(36).substring(2, 15));
  }, []);

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

  const headers = { headers: { "X-Session-ID": sessionId } };

  const uploadResume = async () => {
    if (!file) return;
    setUploading(true); setUploadMsg("");
    const fd = new FormData(); fd.append("file", file);
    try {
      const r = await axios.post(`${API}/student/upload-resume`, fd, {
        headers: { ...headers.headers, "Content-Type": "multipart/form-data" }, timeout: 120000,
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
        headers: { ...headers.headers, "Content-Type": "multipart/form-data" }, timeout: 120000,
      });
      setChat(p => { const c = [...p]; c[c.length-1].bot = r.data.answer; return c; });
    } catch { setChat(p => { const c = [...p]; c[c.length-1].bot = "⚠️ Error."; return c; }); }
    setLoading(false);
    setTimeout(() => chatEnd.current?.scrollIntoView({ behavior: "smooth" }), 100);
  };

  const fetchATS = async () => {
    setAtsLoading(true);
    try {
      const r = await axios.post(`${API}/student/ats-score`, {}, headers);
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

  if (!sessionId) return null; // wait for session ID

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
          <div className="sidebar-user"><FaUserGraduate /><span>Student Demo Session</span></div>
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