import { useRef, useState } from "react";
import "./App.css";

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const timerRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);

  async function sendText(text) {
    if (!text.trim()) return;

    const userMessage = { role: "user", content: text };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsThinking(true);

    const response = await fetch("http://localhost:8000/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message: text }),
    });

    const data = await response.json();

    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: data.reply },
    ]);

    setIsThinking(false);
  }

  async function startRecording() {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        chunksRef.current.push(event.data);
      };

      mediaRecorder.onstop = async () => {
        clearInterval(timerRef.current);

        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        const formData = new FormData();
        formData.append("file", blob, "voice.webm");

        setIsThinking(true);

        const response = await fetch("http://localhost:8000/voice", {
          method: "POST",
          body: formData,
        });

        const data = await response.json();

        setMessages((prev) => [
          ...prev,
          { role: "user", content: data.transcript },
          { role: "assistant", content: data.reply },
        ]);

        setIsThinking(false);
        setRecordingSeconds(0);
      };

      mediaRecorder.start();
      setIsRecording(true);
      setRecordingSeconds(0);

      timerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
  }

  function stopRecording() {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
  }

  function handleSubmit(event) {
    event.preventDefault();
    sendText(input);
  }

  function formatTime(seconds) {
      const mins = Math.floor(seconds / 60);
      const secs = seconds % 60;

      return `${mins}:${secs.toString().padStart(2, "0")}`;
  }

  return (
    <div className="app">
      <h1>🤖 Jarvis</h1>

      <div className="chat">
        {messages.map((message, index) => (
          <div key={index} className={`msg ${message.role}`}>
            {message.content}
          </div>
        ))}

        {isThinking && <div className="msg assistant">Thinking...</div>}
      </div>

      <form className="input" onSubmit={handleSubmit}>
      {isRecording ? (
        <div className="recordingPreview">
          <span className="recordingDot"></span>
          <span>Recording</span>
          <span className="recordingTime">{formatTime(recordingSeconds)}</span>
        </div>
      ) : (
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask Jarvis..."
        />
      )}

      <div className="controls">
        <button
          className="mic"
          type="button"
          onClick={isRecording ? stopRecording : startRecording}
        >
          {isRecording ? "⏹" : "🎤"}
        </button>

        <button className="send" type="submit">
          ↑
        </button>
      </div>
      </form>
    </div>
  );
}