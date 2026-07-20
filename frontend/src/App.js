import React, { useState, useRef, useEffect } from "react";
import axios from "axios";
import { FaPaperPlane, FaBars, FaTimes, FaCloudUploadAlt, FaMoon, FaSun, FaUserGraduate, FaCompass, FaBriefcase, FaUsers } from "react-icons/fa";
import ReactMarkdown from "react-markdown";
import "./App.css";

const API = process.env.REACT_APP_API_URL || (window.location.hostname === "localhost" ? "http://localhost:8000" : "https://rag-play-ground.onrender.com");

export default function App() {
  const [sessionId, setSessionId] = useState("");

  useEffect(() => {
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
  const [careerGoal, setCareerGoal] = useState("");
  const [targetCompany, setTargetCompany] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const chatEnd = useRef(null);
  const fileRef = useRef(null);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
  };

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const headers = { headers: { "X-Session-ID": sessionId } };

  const uploadResume = async () => {
    if (!file) return;
    setUploading(true);
    setUploadMsg("");
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await axios.post(`${API}/student/upload-resume`, fd, {
        headers: { ...headers.headers, "Content-Type": "multipart/form-data" },
        timeout: 120000,
      });
      setUploadMsg(r.data.message);
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || "Unknown error";
      setUploadMsg(`❌ Upload failed: ${detail}`);
    }
    setUploading(false);
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const q = input;
    setInput("");
    setLoading(true);
    setChat((p) => [...p, { user: q, bot: null }]);
    try {
      const fd = new FormData();
      fd.append("question", q);
      fd.append("mode", tab);
      if (careerGoal) fd.append("career_goal", careerGoal);
      if (targetCompany) fd.append("target_company", targetCompany);
      if (targetRole) fd.append("target_role", targetRole);
      const r = await axios.post(`${API}/student/chat`, fd, {
        headers: { ...headers.headers, "Content-Type": "multipart/form-data" },
        timeout: 120000,
      });
      setChat((p) => {
        const c = [...p];
        c[c.length - 1].bot = r.data.answer;
        return c;
      });
    } catch {
      setChat((p) => {
        const c = [...p];
        c[c.length - 1].bot = "⚠️ Error.";
        return c;
      });
    }
    setLoading(false);
    setTimeout(() => chatEnd.current?.scrollIntoView({ behavior: "smooth" }), 100);
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
    resume_match: [
      { icon: "⚖️", text: "Compare me with placed alumni" },
      { icon: "📈", text: "What's my skill gap vs successful candidates?" },
      { icon: "🎯", text: "Am I ready for placement season?" },
    ],
  };

  const tabLabels = {
    mentor: { icon: <FaCompass />, label: "Career Guidance" },
    interview_prep: { icon: <FaBriefcase />, label: "Interview Prep" },
    resume_match: { icon: <FaUsers />, label: "Interview Match" },
  };

  const curSuggestions = suggestions[tab] || suggestions.mentor;

  if (!sessionId) return null;

  return (
    <div className="app-container">
      <aside className={`sidebar ${sidebar ? "open" : ""}`}>
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <div className="sidebar-logo">🎓</div>
            <div className="sidebar-brand-text">
              <h2>PlaceAI</h2>
              <span>Student Portal</span>
            </div>
          </div>
        </div>
        <div className="sidebar-nav">
          {Object.entries(tabLabels).map(([k, v]) => (
            <button
              key={k}
              className={`sidebar-nav-btn ${tab === k ? "active" : ""}`}
              onClick={() => {
                setTab(k);
                setChat([]);
              }}
            >
              {v.icon}
              <span>{v.label}</span>
            </button>
          ))}
        </div>
        <div className="sidebar-upload" style={{ flex: 1, overflow: "auto", padding: "var(--space-4)" }}>
          <div className="sidebar-section-title">Upload Resume</div>
          <p className="upload-hint">Stored only for this session. Refresh the page to clear it.</p>
          <div className="upload-zone">
            <input type="file" accept=".pdf" ref={fileRef} onChange={(e) => setFile(e.target.files[0])} />
            <span className="upload-zone-icon"><FaCloudUploadAlt /></span>
            <div className="upload-zone-text">{file ? file.name : "Drop PDF here"}</div>
          </div>
          {file && (
            <button className="upload-btn" onClick={uploadResume} disabled={uploading}>
              {uploading ? "Uploading..." : "Upload Resume"}
            </button>
          )}
          {uploadMsg && <div className="upload-status">{uploadMsg}</div>}

          {tab === "interview_prep" && (
            <div className="sidebar-context-fields">
              <div className="sidebar-section-title" style={{ marginTop: 12 }}>Interview Context</div>
              <input placeholder="Target Company" value={targetCompany} onChange={(e) => setTargetCompany(e.target.value)} className="context-input" />
              <input placeholder="Target Role" value={targetRole} onChange={(e) => setTargetRole(e.target.value)} className="context-input" />
            </div>
          )}
          {tab === "mentor" && (
            <div className="sidebar-context-fields">
              <div className="sidebar-section-title" style={{ marginTop: 12 }}>Career Goal</div>
              <input placeholder="e.g. AI Engineer" value={careerGoal} onChange={(e) => setCareerGoal(e.target.value)} className="context-input" />
            </div>
          )}
        </div>
        <div className="sidebar-footer">
          <div className="sidebar-user">
            <FaUserGraduate />
            <span>Temporary Session</span>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <div className="top-bar">
          <div className="top-bar-left">
            <button className="sidebar-toggle" onClick={() => setSidebar(!sidebar)}>
              {sidebar ? <FaTimes /> : <FaBars />}
            </button>
            <span className="top-bar-title">
              {tabLabels[tab]?.icon} {tabLabels[tab]?.label}
            </span>
          </div>
          <div className="top-bar-right">
            <button className="theme-toggle" onClick={toggleTheme}>
              {theme === "dark" ? <FaSun /> : <FaMoon />}
            </button>
          </div>
        </div>

        {chat.length === 0 ? (
          <div className="welcome-container">
            <div className="welcome-icon">
              {tab === "mentor" ? "🧭" : tab === "interview_prep" ? "🎯" : "⚖️"}
            </div>
            <h2>{tabLabels[tab]?.label}</h2>
            <p>
              {tab === "mentor" && "Get personalized career guidance using alumni profiles, interview experiences, and your uploaded resume."}
              {tab === "interview_prep" && "Practice for company interviews with real alumni experiences and targeted prep questions."}
              {tab === "resume_match" && "Compare your resume against successfully placed alumni and find your skill gaps."}
            </p>
            <div className="welcome-features">
              {curSuggestions.map((s, i) => (
                <button key={i} className="feature-card" onClick={() => setInput(s.text)}>
                  <span className="feature-card-icon">{s.icon}</span>
                  <h4>{s.text}</h4>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="chat-window">
            {chat.map((m, i) => (
              <React.Fragment key={i}>
                <div className="chat-row user-row">
                  <div className="avatar user-avatar">U</div>
                  <div className="user-message">{m.user}</div>
                </div>
                {m.bot && (
                  <div className="chat-row bot-row">
                    <div className="avatar bot-avatar">AI</div>
                    <div className="bot-message">
                      <ReactMarkdown>{m.bot}</ReactMarkdown>
                    </div>
                  </div>
                )}
              </React.Fragment>
            ))}
            {loading && (
              <div className="typing-indicator">
                <div className="avatar bot-avatar">AI</div>
                <div className="typing-dots"><span /><span /><span /></div>
              </div>
            )}
            <div ref={chatEnd} />
          </div>
        )}

        <div className="input-section">
          <div className="input-wrapper">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder={
                tab === "interview_prep"
                  ? "Ask about interview preparation..."
                  : tab === "resume_match"
                    ? "Ask about interview matching..."
                    : "Ask your career question..."
              }
              disabled={loading}
            />
            <button className="send-btn" onClick={sendMessage} disabled={!input.trim() || loading}>
              <FaPaperPlane />
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
