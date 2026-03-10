import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { FaPaperPlane } from "react-icons/fa";
import ReactMarkdown from "react-markdown";
import "./App.css";

function App() {
  const [mode, setMode] = useState(null);
  const [file, setFile] = useState(null);
  const [chat, setChat] = useState([]);
  const [input, setInput] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat]);

  const uploadResume = async () => {
    if (!file) return alert("Select a file first");

    const formData = new FormData();
    formData.append("file", file);

    const response = await axios.post(
      "http://127.0.0.1:8000/upload",
      formData
    );

    setMessage(response.data.message);
  };

  const sendMessage = async () => {
    if (!input) return;

    const formData = new FormData();
    formData.append("question", input);
    formData.append("mode", mode);

    setLoading(true);

    const response = await axios.post(
      "http://127.0.0.1:8000/chat",
      formData
    );

    setChat([...chat, { user: input, bot: response.data.answer }]);
    setInput("");
    setLoading(false);
  };

  if (!mode) {
    return (
      <div className="mode-container">
        <h1>🤖 AI Resume Coach</h1>
        <h3>Select Mode</h3>

        <button onClick={() => setMode("mentor")}>
          👩‍🏫 Mentor Mode
        </button>

        <button onClick={() => setMode("recruiter")}>
          🧑‍💼 Recruiter Mode
        </button>
      </div>
    );
  }

  return (
    <div className="app-container">

      <div className="header">
        🤖 AI Resume Coach | Mode: {mode.toUpperCase()}
      </div>

      <div className="upload-section">
        <input
          type="file"
          onChange={(e) => setFile(e.target.files[0])}
        />

        <button onClick={uploadResume}>
          Upload
        </button>

        <p className="status">{message}</p>
      </div>

      <div className="chat-window">

        {chat.map((msg, index) => (
          <div key={index}>

            <div className="user-message">
              {msg.user}
            </div>

            <div className="bot-message">
              <ReactMarkdown>
                {msg.bot}
              </ReactMarkdown>
            </div>

          </div>
        ))}

        {loading && (
          <div className="bot-message">
            Typing...
          </div>
        )}

        <div ref={chatEndRef} />

      </div>

      <div className="input-section">

        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask something about your resume..."
        />

        <button onClick={sendMessage}>
          <FaPaperPlane />
        </button>

      </div>

      <img
        src="/bot.png"
        className="floating-bot"
        alt="bot"
      />

    </div>
  );
}

export default App;