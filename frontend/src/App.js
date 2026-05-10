import React, { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { FaPaperPlane, FaPlus, FaBars, FaTimes, FaCommentDots, FaCloudUploadAlt, FaExchangeAlt, FaSearch, FaUserGraduate, FaTrashAlt } from "react-icons/fa";
import ReactMarkdown from "react-markdown";
import "./App.css";

// API Base URL — change this when switching between local dev and deployed backend
const API_BASE = process.env.REACT_APP_API_URL || "https://rag-play-ground.onrender.com";

// Shared axios config for multipart requests (handles Render free-tier cold-start delay)
const multipartConfig = {
  headers: { "Content-Type": "multipart/form-data" },
  timeout: 120000, // 2 minutes — Render free tier can take ~50s to wake up
};

// Score Ring Component
function ScoreRing({ score, size = 100, strokeWidth = 8 }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 80 ? "#22c55e" : score >= 60 ? "#f59e0b" : "#ef4444";

  return (
    <svg width={size} height={size} className="score-ring">
      <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke="rgba(148,163,184,0.12)" strokeWidth={strokeWidth} />
      <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke={color} strokeWidth={strokeWidth}
        strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
        transform={`rotate(-90 ${size/2} ${size/2})`} style={{ transition: "stroke-dashoffset 1s ease" }} />
      <text x="50%" y="50%" textAnchor="middle" dy=".35em" fill={color} fontSize={size * 0.28} fontWeight="700"
        fontFamily="Inter, sans-serif">{score}</text>
    </svg>
  );
}

// Score Card Component
function ScoreCard({ scoreData, onClose }) {
  if (!scoreData) return null;
  const cats = scoreData.categories || {};
  return (
    <div className="score-overlay" onClick={onClose}>
      <div className="score-card" onClick={e => e.stopPropagation()}>
        <button className="score-close" onClick={onClose}><FaTimes /></button>
        <h3>Resume Score</h3>
        <div className="score-ring-wrap"><ScoreRing score={scoreData.overall || 0} size={140} strokeWidth={10} /></div>
        <p className="score-summary">{scoreData.summary}</p>
        <div className="score-categories">
          {Object.entries(cats).map(([key, val]) => (
            <div key={key} className="score-cat-row">
              <div className="score-cat-info">
                <span className="score-cat-name">{key.charAt(0).toUpperCase() + key.slice(1)}</span>
                <span className="score-cat-comment">{val.comment}</span>
              </div>
              <div className="score-cat-bar-wrap">
                <div className="score-cat-bar" style={{ width: `${(val.score / 20) * 100}%` }}></div>
              </div>
              <span className="score-cat-val">{val.score}/20</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function App() {
  const [mode, setMode] = useState(null);
  const [appTab, setAppTab] = useState("coach");
  const [file, setFile] = useState(null);
  const [compareFiles, setCompareFiles] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [compareChat, setCompareChat] = useState([]);
  const [input, setInput] = useState("");
  const [uploadMessage, setUploadMessage] = useState("");
  const [compareUploadMessage, setCompareUploadMessage] = useState("");
  const [compareResumeNames, setCompareResumeNames] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [resumeReady, setResumeReady] = useState(false);
  const [compareReady, setCompareReady] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [scoreData, setScoreData] = useState(null);
  const [scoreLoading, setScoreLoading] = useState(false);
  const [showScore, setShowScore] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState("");

  // Recruit tab state
  const [repoFiles, setRepoFiles] = useState([]);
  const [repoStudents, setRepoStudents] = useState([]);
  const [repoUploading, setRepoUploading] = useState(false);
  const [repoUploadMsg, setRepoUploadMsg] = useState("");
  const [repoSearching, setRepoSearching] = useState(false);
  const [repoQuery, setRepoQuery] = useState("");
  const [repoAnswer, setRepoAnswer] = useState("");
  const [repoCandidates, setRepoCandidates] = useState([]);
  const [repoExpanded, setRepoExpanded] = useState(null);

  const chatEndRef = useRef(null);
  const compareChatEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const compareFileInputRef = useRef(null);
  const repoFileInputRef = useRef(null);

  const activeConversation = conversations.find(c => c.id === activeConversationId);
  const chat = activeConversation ? activeConversation.messages : [];

  useEffect(() => {
    if (appTab === "coach") chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    else compareChatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat, compareChat, appTab]);

  const startNewChat = useCallback(() => {
    const newConv = { id: Date.now(), title: "New Chat", messages: [],
      createdAt: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) };
    setConversations(prev => [newConv, ...prev]);
    setActiveConversationId(newConv.id);
    setSidebarOpen(false);
  }, []);

  // --- Recruit tab functions ---
  const uploadToRepository = async () => {
    if (repoFiles.length === 0) return;
    setRepoUploading(true); setRepoUploadMsg("");
    try {
      const fd = new FormData();
      for (const f of repoFiles) fd.append("files", f);
      const res = await axios.post(`${API_BASE}/repository/upload`, fd, { ...multipartConfig, timeout: 300000 });
      setRepoUploadMsg(res.data.message);
      setRepoStudents(prev => {
        const existing = prev.map(s => s.name);
        const newStudents = (res.data.students || []).filter(s => !s.error && !existing.includes(s.name));
        return [...prev, ...newStudents];
      });
      // Also refresh full list
      const listRes = await axios.get(`${API_BASE}/repository/students`, { timeout: 30000 });
      setRepoStudents(listRes.data.students || []);
      setRepoFiles([]);
      if (repoFileInputRef.current) repoFileInputRef.current.value = "";
    } catch { setRepoUploadMsg("❌ Upload failed."); }
    setRepoUploading(false);
  };

  const searchRepository = async () => {
    if (!repoQuery.trim() || repoSearching) return;
    setRepoSearching(true); setRepoAnswer(""); setRepoCandidates([]);
    try {
      const fd = new FormData(); fd.append("query", repoQuery);
      const res = await axios.post(`${API_BASE}/repository/search`, fd, multipartConfig);
      setRepoAnswer(res.data.answer || "");
      setRepoCandidates(res.data.candidates || []);
    } catch { setRepoAnswer("⚠️ Search failed. Please try again."); }
    setRepoSearching(false);
  };

  const removeStudent = async (name) => {
    try {
      await axios.delete(`${API_BASE}/repository/student/${encodeURIComponent(name)}`, { timeout: 30000 });
      setRepoStudents(prev => prev.filter(s => s.name !== name));
    } catch { /* ignore */ }
  };

  const fetchScore = async () => {
    setScoreLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/score`, null, { timeout: 120000 });
      if (!res.data.error) { setScoreData(res.data); setShowScore(true); }
    } catch (e) { /* ignore */ }
    setScoreLoading(false);
  };

  const uploadResume = async () => {
    if (!file) return;
    setUploading(true); setUploadMessage("");
    try {
      const fd = new FormData(); fd.append("file", file);
      const uploadingName = file.name;
      const res = await axios.post(`${API_BASE}/upload`, fd, multipartConfig);
      setUploadMessage(res.data.message); setResumeReady(true);
      setUploadedFileName(uploadingName);
      setFile(null); setScoreData(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch { setUploadMessage("❌ Upload failed."); }
    setUploading(false);
  };

  const uploadCompareResumes = async () => {
    if (compareFiles.length < 2) return;
    setUploading(true); setCompareUploadMessage("");
    try {
      const fd = new FormData();
      for (const f of compareFiles) fd.append("files", f);
      const res = await axios.post(`${API_BASE}/upload-compare`, fd, multipartConfig);
      setCompareUploadMessage(res.data.message);
      setCompareResumeNames(res.data.resumes || []);
      setCompareReady(true); setCompareFiles([]); setCompareChat([]);
      if (compareFileInputRef.current) compareFileInputRef.current.value = "";
    } catch { setCompareUploadMessage("❌ Upload failed."); }
    setUploading(false);
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    let currentId = activeConversationId;
    if (!currentId) {
      const newConv = { id: Date.now(), title: input.slice(0, 40), messages: [],
        createdAt: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) };
      setConversations(prev => [newConv, ...prev]);
      setActiveConversationId(newConv.id); currentId = newConv.id;
    }
    const userMsg = input; setInput(""); setLoading(true);
    setConversations(prev => prev.map(c => c.id === currentId
      ? { ...c, messages: [...c.messages, { user: userMsg, bot: null }], title: c.messages.length === 0 ? userMsg.slice(0, 40) : c.title }
      : c));
    try {
      const fd = new FormData(); fd.append("question", userMsg); fd.append("mode", mode);
      const res = await axios.post(`${API_BASE}/chat`, fd, multipartConfig);
      setConversations(prev => prev.map(c => {
        if (c.id !== currentId) return c;
        const msgs = [...c.messages]; msgs[msgs.length - 1] = { user: userMsg, bot: res.data.answer }; return { ...c, messages: msgs };
      }));
    } catch {
      setConversations(prev => prev.map(c => {
        if (c.id !== currentId) return c;
        const msgs = [...c.messages]; msgs[msgs.length - 1] = { user: userMsg, bot: "⚠️ Something went wrong." }; return { ...c, messages: msgs };
      }));
    }
    setLoading(false);
  };

  const sendCompareMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input; setInput(""); setLoading(true);
    setCompareChat(prev => [...prev, { user: userMsg, bot: null }]);
    try {
      const fd = new FormData(); fd.append("question", userMsg);
      const res = await axios.post(`${API_BASE}/compare`, fd, multipartConfig);
      setCompareChat(prev => { const m = [...prev]; m[m.length-1] = { user: userMsg, bot: res.data.answer }; return m; });
    } catch {
      setCompareChat(prev => { const m = [...prev]; m[m.length-1] = { user: userMsg, bot: "⚠️ Something went wrong." }; return m; });
    }
    setLoading(false);
  };

  const handleSend = () => { if (appTab === "coach") sendMessage(); else sendCompareMessage(); };
  const handleKeyDown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } };
  const handleDragOver = (e) => { e.preventDefault(); setDragOver(true); };
  const handleDragLeave = () => setDragOver(false);
  const handleDrop = (e) => {
    e.preventDefault(); setDragOver(false);
    const droppedFiles = Array.from(e.dataTransfer.files).filter(f => f.type === "application/pdf");
    if (droppedFiles.length === 0) return;
    if (appTab === "coach") { setFile(droppedFiles[0]); }
    else if (appTab === "compare") { setCompareFiles(prev => [...prev, ...droppedFiles]); }
    else if (appTab === "recruit") { setRepoFiles(prev => [...prev, ...droppedFiles]); }
  };

  const modeLabels = { mentor: "👩‍🏫 Mentor", recruiter: "🧑‍💼 Recruiter", interview: "🎯 Interview" };

  const suggestionsByMode = {
    mentor: [
      { icon: "💯", text: "Score my resume out of 100" },
      { icon: "💪", text: "What are my strengths?" },
      { icon: "📈", text: "Detect skill gaps for product companies" },
      { icon: "🏢", text: "How ready am I for a backend role?" },
      { icon: "✍️", text: "Improve my project descriptions" },
      { icon: "📋", text: "Analyze my projects section" },
    ],
    recruiter: [
      { icon: "💯", text: "Score my resume out of 100" },
      { icon: "🔍", text: "Detect skill gaps for top tech companies" },
      { icon: "🏢", text: "How good is my resume for product companies?" },
      { icon: "🎯", text: "Evaluate me for a full-stack developer role" },
      { icon: "✍️", text: "Rewrite my experience section" },
      { icon: "🚩", text: "What red flags do you see?" },
    ],
    interview: [
      { icon: "🎤", text: "Start my mock interview" },
      { icon: "💻", text: "Ask me technical questions" },
      { icon: "🧠", text: "Ask behavioral questions about my projects" },
      { icon: "🎯", text: "Quiz me on my skills" },
    ],
    compare: [
      { icon: "⚖️", text: "Compare both resumes side by side" },
      { icon: "🏆", text: "Which resume is stronger overall?" },
      { icon: "🔍", text: "What skills does each resume highlight?" },
      { icon: "📊", text: "Rate each resume out of 10" },
    ],
    recruit: [
      { icon: "💻", text: "Find students suitable for backend development internship" },
      { icon: "🤖", text: "Students with AI/ML project experience" },
      { icon: "⚛️", text: "React and frontend development experience" },
      { icon: "🏆", text: "Hackathon winners with strong Python skills" },
      { icon: "📊", text: "Data science and analytics experience" },
      { icon: "🌐", text: "Full-stack developers with API experience" },
    ],
  };

  const currentSuggestions = appTab === "compare" ? suggestionsByMode.compare : appTab === "recruit" ? suggestionsByMode.recruit : (suggestionsByMode[mode] || suggestionsByMode.mentor);
  const currentChat = appTab === "coach" ? chat : compareChat;
  const currentEndRef = appTab === "coach" ? chatEndRef : compareChatEndRef;

  // ---- LANDING ----
  if (!mode) {
    return (
      <div className="landing-container">
        <div className="landing-brand">
          <div className="landing-brand-icon">🤖</div>
          <h1>AI Resume Coach</h1>
        </div>
        <p className="landing-subtitle">Enterprise-grade AI-powered resume analysis</p>
        <div className="landing-modes">
          <div className="mode-card" onClick={() => setMode("mentor")} id="mode-mentor">
            <div className="mode-card-icon">👩‍🏫</div>
            <h3>Mentor Mode</h3>
            <p>Personalized guidance, scoring, skill gap detection, and actionable improvement tips.</p>
          </div>
          <div className="mode-card" onClick={() => setMode("recruiter")} id="mode-recruiter">
            <div className="mode-card-icon">🧑‍💼</div>
            <h3>Recruiter Mode</h3>
            <p>Hiring manager evaluation — screening criteria, red flags, role readiness analysis.</p>
          </div>
          <div className="mode-card" onClick={() => setMode("interview")} id="mode-interview">
            <div className="mode-card-icon">🎯</div>
            <h3>Interview Mode</h3>
            <p>Mock interview based on your resume — technical, behavioral, and project deep-dives.</p>
          </div>
        </div>
      </div>
    );
  }

  // ---- MAIN APP ----
  return (
    <div className="app-layout">
      {sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />}
      {showScore && <ScoreCard scoreData={scoreData} onClose={() => setShowScore(false)} />}

      {/* SIDEBAR */}
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <div className="sidebar-logo">🤖</div>
            <div className="sidebar-brand-text"><h2>Resume Coach</h2><span>Enterprise AI</span></div>
          </div>
        </div>

        <div className="sidebar-tab-section">
          <div className="sidebar-tab-group">
            <button className={`sidebar-tab-btn ${appTab === "coach" ? "active" : ""}`} onClick={() => setAppTab("coach")} id="tab-coach">💬 Coach</button>
            <button className={`sidebar-tab-btn ${appTab === "compare" ? "active" : ""}`} onClick={() => setAppTab("compare")} id="tab-compare"><FaExchangeAlt style={{ marginRight: 4 }} /> Compare</button>
            <button className={`sidebar-tab-btn ${appTab === "recruit" ? "active" : ""}`} onClick={() => setAppTab("recruit")} id="tab-recruit"><FaSearch style={{ marginRight: 4 }} /> Recruit</button>
          </div>
        </div>

        {appTab === "coach" && (
          <>
            <button className="new-chat-btn" onClick={startNewChat} id="btn-new-chat"><FaPlus /> New Conversation</button>

            <div className="sidebar-section-title">History</div>
            <div className="conversation-list">
              {conversations.length === 0 && <div style={{ padding: 12, color: "var(--color-text-tertiary)", fontSize: "var(--text-xs)" }}>No conversations yet</div>}
              {conversations.map(conv => (
                <div key={conv.id} className={`conversation-item ${conv.id === activeConversationId ? "active" : ""}`}
                  onClick={() => { setActiveConversationId(conv.id); setSidebarOpen(false); }}>
                  <span className="conversation-item-icon"><FaCommentDots /></span>
                  <span className="conversation-item-text">{conv.title}</span>
                </div>
              ))}
            </div>

            <div className="sidebar-mode-section">
              <div className="sidebar-section-title" style={{ padding: "0 0 8px 0" }}>Mode</div>
              <div className="mode-toggle-group">
                {["mentor", "recruiter", "interview"].map(m => (
                  <button key={m} className={`mode-toggle-btn ${mode === m ? "active" : ""}`} onClick={() => setMode(m)} id={`toggle-${m}`}>
                    {modeLabels[m]}
                  </button>
                ))}
              </div>
            </div>

            <div className="sidebar-upload">
              <div className="sidebar-section-title" style={{ padding: "0 0 8px 0" }}>Resume</div>
              <div className={`upload-zone ${dragOver ? "drag-over" : ""}`} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}>
                <input type="file" accept=".pdf" ref={fileInputRef} onChange={(e) => setFile(e.target.files[0])} id="file-upload" />
                <span className="upload-zone-icon"><FaCloudUploadAlt /></span>
                <div className="upload-zone-text">{file ? file.name : (uploadedFileName ? `📄 ${uploadedFileName} loaded ✅` : "Drop PDF here")}</div>
                <div className="upload-zone-hint">{uploadedFileName && !file ? "drop a new PDF to replace" : "or click to browse"}</div>
              </div>
              {file && (
                <div className="upload-actions">
                  <span className="selected-file">📄 {file.name}</span>
                  <button className="upload-btn" onClick={uploadResume} disabled={uploading} id="btn-upload">{uploading ? "Uploading…" : "Upload"}</button>
                </div>
              )}
              {uploadMessage && <div className="upload-status">{uploadMessage}</div>}
              {resumeReady && (
                <button className="score-btn" onClick={fetchScore} disabled={scoreLoading} id="btn-score">
                  {scoreLoading ? "Analyzing…" : "💯 Get Resume Score"}
                </button>
              )}
            </div>
          </>
        )}

        {appTab === "compare" && (
          <div className="sidebar-upload" style={{ flex: 1, overflow: "auto" }}>
            <div className="sidebar-section-title" style={{ padding: "0 0 8px 0" }}>Upload Resumes to Compare</div>
            <div className={`upload-zone ${dragOver ? "drag-over" : ""}`} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}>
              <input type="file" accept=".pdf" multiple ref={compareFileInputRef}
                onChange={(e) => { setCompareFiles(prev => [...prev, ...Array.from(e.target.files)]); }} id="compare-file-upload" />
              <span className="upload-zone-icon"><FaCloudUploadAlt /></span>
              <div className="upload-zone-text">Drop PDFs here</div>
              <div className="upload-zone-hint">Select 2 or more resumes</div>
            </div>
            {compareFiles.length > 0 && (
              <div className="compare-file-list">
                {compareFiles.map((f, i) => (
                  <div key={i} className="compare-file-item">
                    <span className="compare-file-name">📄 {f.name}</span>
                    <button className="compare-file-remove" onClick={() => setCompareFiles(prev => prev.filter((_,j) => j!==i))}><FaTimes /></button>
                  </div>
                ))}
              </div>
            )}
            {compareFiles.length >= 2 && (
              <button className="upload-btn compare-upload-btn" onClick={uploadCompareResumes} disabled={uploading} id="btn-compare-upload">
                {uploading ? "Processing…" : `Compare ${compareFiles.length} Resumes`}
              </button>
            )}
            {compareFiles.length === 1 && <div className="compare-hint">Add at least 1 more resume to compare</div>}
            {compareUploadMessage && <div className="upload-status">{compareUploadMessage}</div>}
            {compareReady && compareResumeNames.length > 0 && (
              <div className="compare-loaded-resumes">
                <div className="sidebar-section-title" style={{ padding: "12px 0 6px 0" }}>Loaded for Comparison</div>
                {compareResumeNames.map((name, i) => (
                  <div key={i} className="compare-resume-badge"><span className="compare-resume-dot"></span>{name}</div>
                ))}
              </div>
            )}
          </div>
        )}

        {appTab === "recruit" && (
          <div className="sidebar-upload" style={{ flex: 1, overflow: "auto" }}>
            <div className="sidebar-section-title" style={{ padding: "0 0 8px 0" }}>Upload Department Resumes</div>
            <div className={`upload-zone ${dragOver ? "drag-over" : ""}`} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}>
              <input type="file" accept=".pdf" multiple ref={repoFileInputRef}
                onChange={(e) => { setRepoFiles(prev => [...prev, ...Array.from(e.target.files)]); }} id="repo-file-upload" />
              <span className="upload-zone-icon"><FaCloudUploadAlt /></span>
              <div className="upload-zone-text">Drop student resumes here</div>
              <div className="upload-zone-hint">Upload multiple PDFs at once</div>
            </div>
            {repoFiles.length > 0 && (
              <div className="compare-file-list">
                {repoFiles.map((f, i) => (
                  <div key={i} className="compare-file-item">
                    <span className="compare-file-name">📄 {f.name}</span>
                    <button className="compare-file-remove" onClick={() => setRepoFiles(prev => prev.filter((_,j) => j!==i))}><FaTimes /></button>
                  </div>
                ))}
              </div>
            )}
            {repoFiles.length > 0 && (
              <button className="upload-btn compare-upload-btn" onClick={uploadToRepository} disabled={repoUploading} id="btn-repo-upload">
                {repoUploading ? "Processing…" : `Upload ${repoFiles.length} Resume(s)`}
              </button>
            )}
            {repoUploadMsg && <div className="upload-status">{repoUploadMsg}</div>}

            {repoStudents.length > 0 && (
              <div className="compare-loaded-resumes">
                <div className="sidebar-section-title" style={{ padding: "12px 0 6px 0" }}>
                  <FaUserGraduate style={{ marginRight: 6 }} /> Student Repository ({repoStudents.length})
                </div>
                {repoStudents.map((s, i) => (
                  <div key={i} className="repo-student-card">
                    <div className="repo-student-info">
                      <span className="compare-resume-dot"></span>
                      <span className="repo-student-name">{s.name}</span>
                    </div>
                    <div className="repo-student-skills">
                      {(s.skills || []).slice(0, 3).map((sk, j) => (
                        <span key={j} className="repo-skill-tag">{sk}</span>
                      ))}
                      {(s.skills || []).length > 3 && <span className="repo-skill-more">+{s.skills.length - 3}</span>}
                    </div>
                    <button className="repo-student-remove" onClick={() => removeStudent(s.name)} title="Remove"><FaTrashAlt /></button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </aside>

      {/* MAIN */}
      <main className="main-content">
        <div className="top-bar">
          <div className="top-bar-left">
            <button className="sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)} id="btn-sidebar-toggle">
              {sidebarOpen ? <FaTimes /> : <FaBars />}
            </button>
            <span className="top-bar-title">
              {appTab === "coach" ? (modeLabels[mode] + " Mode") : appTab === "compare" ? "⚖️ Resume Comparison" : "🎯 AI Recruitment Assistant"}
            </span>
          </div>
          <div className="top-bar-right">
            {scoreData && appTab === "coach" && (
              <button className="top-score-pill" onClick={() => setShowScore(true)}>
                💯 Score: {scoreData.overall}
              </button>
            )}
            <div className={`status-badge ${(appTab === "coach" ? resumeReady : appTab === "compare" ? compareReady : repoStudents.length > 0) ? "ready" : ""}`}>
              <span className="status-dot"></span>
              {appTab === "coach" ? (resumeReady ? "Resume Loaded" : "No Resume") : appTab === "compare" ? (compareReady ? `${compareResumeNames.length} Resumes` : "No Resumes") : (repoStudents.length > 0 ? `${repoStudents.length} Students` : "Empty Repository")}
            </div>
          </div>
        </div>

        {/* ---- RECRUIT TAB MAIN ---- */}
        {appTab === "recruit" ? (
          <>
            {!repoAnswer && repoCandidates.length === 0 && !repoSearching ? (
              <div className="welcome-container">
                <div className="welcome-icon">🎯</div>
                <h2>AI Recruitment Assistant</h2>
                <p>Upload department resumes, then search for the best matching candidates.</p>
                <div className="welcome-features">
                  <div className="feature-card"><span className="feature-card-icon">📑</span><h4>Resume Repository</h4><p>Store all department student resumes.</p></div>
                  <div className="feature-card"><span className="feature-card-icon">🔍</span><h4>Semantic Search</h4><p>Find candidates by skills, not keywords.</p></div>
                  <div className="feature-card"><span className="feature-card-icon">🏆</span><h4>AI Ranking</h4><p>Gemini ranks and justifies top matches.</p></div>
                </div>
              </div>
            ) : (
              <div className="chat-window" id="recruit-results">
                {repoSearching && (
                  <div className="typing-indicator">
                    <div className="avatar bot-avatar">AI</div>
                    <div className="typing-dots"><span></span><span></span><span></span></div>
                  </div>
                )}
                {repoCandidates.length > 0 && (
                  <div className="recruit-candidates">
                    <div className="recruit-candidates-header">Top Matching Candidates</div>
                    <div className="recruit-cards-grid">
                      {repoCandidates.map((c, i) => (
                        <div key={i} className={`recruit-card ${repoExpanded === i ? "expanded" : ""}`} onClick={() => setRepoExpanded(repoExpanded === i ? null : i)}>
                          <div className="recruit-card-top">
                            <div className="recruit-card-rank">#{i + 1}</div>
                            <div className="recruit-card-info">
                              <div className="recruit-card-name">{c.name}</div>
                              <div className="recruit-card-dept">{c.department} {c.cgpa !== "N/A" ? `• CGPA: ${c.cgpa}` : ""}</div>
                            </div>
                            <div className="recruit-card-score-wrap">
                              <ScoreRing score={c.relevance_score} size={56} strokeWidth={5} />
                            </div>
                          </div>
                          <div className="recruit-card-skills">
                            {(c.skills || []).slice(0, 6).map((sk, j) => (
                              <span key={j} className="recruit-skill-tag">{sk}</span>
                            ))}
                            {(c.skills || []).length > 6 && <span className="recruit-skill-more">+{c.skills.length - 6}</span>}
                          </div>
                          {(c.projects || []).length > 0 && (
                            <div className="recruit-card-projects">
                              {(c.projects || []).slice(0, 3).map((p, j) => (
                                <span key={j} className="recruit-project-tag">📁 {p}</span>
                              ))}
                            </div>
                          )}
                          {repoExpanded === i && c.excerpts && (
                            <div className="recruit-card-excerpts">
                              <div className="recruit-excerpt-title">Resume Excerpts</div>
                              {c.excerpts.map((ex, j) => (
                                <p key={j} className="recruit-excerpt-text">{ex.substring(0, 300)}…</p>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {repoAnswer && (
                  <div className="chat-row bot-row" style={{ maxWidth: "100%" }}>
                    <div className="avatar bot-avatar">AI</div>
                    <div className="bot-message" style={{ maxWidth: "100%" }}><ReactMarkdown>{repoAnswer}</ReactMarkdown></div>
                  </div>
                )}
              </div>
            )}

            <div className="suggestions-section">
              <div className="suggestions-label">Suggested Searches</div>
              <div className="suggestions-chips">
                {currentSuggestions.map((s, i) => (
                  <button key={i} className="suggestion-chip" onClick={() => setRepoQuery(s.text)} id={`recruit-suggestion-${i}`}>
                    <span className="suggestion-chip-icon">{s.icon}</span>{s.text}
                  </button>
                ))}
              </div>
            </div>

            <div className="input-section">
              <div className="input-wrapper">
                <input value={repoQuery} onChange={(e) => setRepoQuery(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); searchRepository(); } }}
                  placeholder="Describe your ideal candidate…"
                  disabled={repoSearching} id="recruit-input" />
                <button className="send-btn" onClick={searchRepository} disabled={!repoQuery.trim() || repoSearching} id="btn-recruit-search"><FaSearch /></button>
              </div>
              <div className="input-hint">Press <kbd>Enter</kbd> to search</div>
            </div>
          </>
        ) : (
          <>
            {currentChat.length === 0 ? (
              <div className="welcome-container">
                <div className="welcome-icon">{appTab === "coach" ? (mode === "interview" ? "🎯" : "✨") : "⚖️"}</div>
                <h2>{appTab === "coach" ? (mode === "interview" ? "Mock Interview" : "Welcome to Resume Coach") : "Resume Comparison"}</h2>
                <p>{appTab === "coach"
                  ? (mode === "interview" ? "Upload your resume, then start a mock interview session." : "Upload your resume and start a conversation to get AI-powered insights.")
                  : "Upload 2 or more resumes from the sidebar, then ask questions to compare them."}</p>
                <div className="welcome-features">
                  {appTab === "coach" ? (
                    mode === "interview" ? (
                      <>
                        <div className="feature-card"><span className="feature-card-icon">🎤</span><h4>Project Deep-Dives</h4><p>Explain your projects, challenges, and decisions.</p></div>
                        <div className="feature-card"><span className="feature-card-icon">💻</span><h4>Technical Questions</h4><p>Technology choices, architecture, and implementation.</p></div>
                        <div className="feature-card"><span className="feature-card-icon">🧠</span><h4>Behavioral</h4><p>Situational questions based on your experience.</p></div>
                      </>
                    ) : (
                      <>
                        <div className="feature-card"><span className="feature-card-icon">💯</span><h4>Resume Score</h4><p>Get a detailed score breakdown out of 100.</p></div>
                        <div className="feature-card"><span className="feature-card-icon">🔍</span><h4>Skill Gap Detection</h4><p>Find missing skills for your target role.</p></div>
                        <div className="feature-card"><span className="feature-card-icon">✍️</span><h4>Resume Rewriter</h4><p>Before/after improvements for every section.</p></div>
                      </>
                    )
                  ) : (
                    <>
                      <div className="feature-card"><span className="feature-card-icon">📑</span><h4>Multi-Resume</h4><p>Upload and analyze multiple resumes.</p></div>
                      <div className="feature-card"><span className="feature-card-icon">⚖️</span><h4>Side by Side</h4><p>Compare qualifications head-to-head.</p></div>
                      <div className="feature-card"><span className="feature-card-icon">🏆</span><h4>Best Match</h4><p>Find the best resume for a role.</p></div>
                    </>
                  )}
                </div>
              </div>
            ) : (
              <div className="chat-window" id="chat-window">
                {currentChat.map((msg, index) => (
                  <React.Fragment key={index}>
                    <div className="chat-row user-row">
                      <div className="avatar user-avatar">U</div>
                      <div className="user-message">{msg.user}</div>
                    </div>
                    {msg.bot && (
                      <div className="chat-row bot-row">
                        <div className="avatar bot-avatar">AI</div>
                        <div className="bot-message"><ReactMarkdown>{msg.bot}</ReactMarkdown></div>
                      </div>
                    )}
                  </React.Fragment>
                ))}
                {loading && (
                  <div className="typing-indicator">
                    <div className="avatar bot-avatar">AI</div>
                    <div className="typing-dots"><span></span><span></span><span></span></div>
                  </div>
                )}
                <div ref={currentEndRef} />
              </div>
            )}

            <div className="suggestions-section">
              <div className="suggestions-label">Suggested Questions</div>
              <div className="suggestions-chips">
                {currentSuggestions.map((s, i) => (
                  <button key={i} className="suggestion-chip" onClick={() => setInput(s.text)} id={`suggestion-${i}`}>
                    <span className="suggestion-chip-icon">{s.icon}</span>{s.text}
                  </button>
                ))}
              </div>
            </div>

            <div className="input-section">
              <div className="input-wrapper">
                <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown}
                  placeholder={mode === "interview" ? "Answer the interview question…" : (appTab === "coach" ? "Ask about your resume…" : "Ask a comparison question…")}
                  disabled={loading} id="chat-input" />
                <button className="send-btn" onClick={handleSend} disabled={!input.trim() || loading} id="btn-send"><FaPaperPlane /></button>
              </div>
              <div className="input-hint">Press <kbd>Enter</kbd> to send</div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

export default App;