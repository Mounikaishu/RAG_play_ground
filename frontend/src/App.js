import React, { useState } from "react";
import axios from "axios";

function App() {
  const [file, setFile] = useState(null);
  const [chat, setChat] = useState([]);
  const [input, setInput] = useState("");
  const [message, setMessage] = useState("");

  const uploadResume = async () => {
    if (!file) {
      alert("Please select a file first.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await axios.post(
        "http://127.0.0.1:8000/upload",
        formData
      );

      setMessage(response.data.message);
    } catch (error) {
      console.error(error);
      alert("Upload failed. Make sure backend is running.");
    }
  };

  const sendMessage = async () => {
    if (!input) return;

    const formData = new FormData();
    formData.append("question", input);

    try {
      const response = await axios.post(
        "http://127.0.0.1:8000/chat",
        formData
      );

      setChat([...chat, { user: input, bot: response.data.answer }]);
      setInput("");
    } catch (error) {
      console.error(error);
      alert("Chat failed. Check backend.");
    }
  };

  return (
    <div style={{ padding: "40px", fontFamily: "Arial" }}>
      <h1>AI Resume Coach</h1>

      <h3>Upload Resume</h3>
      <input type="file" onChange={(e) => setFile(e.target.files[0])} />
      <button onClick={uploadResume}>Upload</button>
      <p>{message}</p>

      <hr />

      <h3>Chat</h3>
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Ask about your resume..."
        style={{ width: "300px" }}
      />
      <button onClick={sendMessage}>Send</button>

      <div style={{ marginTop: "20px" }}>
        {chat.map((msg, index) => (
          <div key={index} style={{ marginBottom: "15px" }}>
            <b>You:</b> {msg.user}
            <br />
            <b>Coach:</b> {msg.bot}
            <hr />
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;