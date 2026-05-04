import { useRef, useState } from "react";
import "./App.css";
import ReactMarkdown from "react-markdown";

const API_URL = "http://localhost:8000";

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);

  const [showSettings, setShowSettings] = useState(false);
  const [enableVoice, setEnableVoice] = useState(false);
  const [voiceMode, setVoiceMode] = useState("default");
  const [voiceFile, setVoiceFile] = useState(null);
  const [customVoiceId, setCustomVoiceId] = useState(null);
  const [isUploadingVoice, setIsUploadingVoice] = useState(false);

  const [enableVideo, setEnableVideo] = useState(false);
  const [avatarMode, setAvatarMode] = useState("default");
  const [avatarFile, setAvatarFile] = useState(null);

  const timerRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);

  async function uploadCustomVoice(file) {
    if (!file) return null;

    setIsUploadingVoice(true);

    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(`${API_URL}/upload-voice`, {
      method: "POST",
      body: formData,
    });

    setIsUploadingVoice(false);

    if (!response.ok) {
      console.error("Voice upload failed:", await response.text());
      return null;
    }

    const data = await response.json();

    if (!data.voice_id) {
      console.error("No voice_id returned:", data);
      return null;
    }

    setCustomVoiceId(data.voice_id);
    return data.voice_id;
  }

  async function generateTTSUrl(text) {
      if (!enableVoice) return null;

      const formData = new FormData();
      formData.append("text", text);

      let response;

      if (voiceMode === "default") {
        response = await fetch(`${API_URL}/speak-default`, {
          method: "POST",
          body: formData,
        });
      } else if (voiceMode === "custom") {
        let voiceId = customVoiceId;

        if (!voiceId) {
          if (!voiceFile) {
            console.error("No custom voice file selected");
            return null;
          }

          voiceId = await uploadCustomVoice(voiceFile);

          if (!voiceId) {
            console.error("Failed to upload custom voice");
            return null;
          }
        }

        formData.append("voice_id", voiceId);

        response = await fetch(`${API_URL}/speak-clone`, {
          method: "POST",
          body: formData,
        });
      } else {
        return null;
      }

      if (!response.ok) {
        console.error("TTS failed:", await response.text());
        return null;
      }

      const data = await response.json();

      if (!data.audio_url) {
        console.error("No audio_url in TTS response:", data);
        return null;
      }

      if (data.voice_id) {
        setCustomVoiceId(data.voice_id);
      }

      return data.audio_url;
    }

  async function addAssistantMessageWithVoice(reply) {
    const assistantMessageId = Date.now() + Math.random();

    setMessages((prev) => [
      ...prev,
      {
        id: assistantMessageId,
        role: "assistant",
        content: reply,
        audioUrl: null,
        isAudioLoading: enableVoice,
      },
    ]);

    setIsThinking(false);

    const audioUrl = await generateTTSUrl(reply);

    setMessages((prev) =>
      prev.map((message) =>
        message.id === assistantMessageId
          ? {
              ...message,
              audioUrl,
              isAudioLoading: false,
            }
          : message
      )
    );
  }

  async function sendText(text) {
    if (!text.trim()) return;

    setMessages((prev) => [
      ...prev,
      {
        id: Date.now() + Math.random(),
        role: "user",
        content: text,
      },
    ]);

    setInput("");
    setIsThinking(true);

    const response = await fetch(`${API_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message: text }),
    });

    const data = await response.json();

    await addAssistantMessageWithVoice(data.reply);
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

      const response = await fetch(`${API_URL}/voice`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + Math.random(),
          role: "user",
          content: data.transcript,
        },
      ]);

      setRecordingSeconds(0);

      await addAssistantMessageWithVoice(data.reply);

      stream.getTracks().forEach((track) => track.stop());
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

      <button
        className="settingsButton"
        onClick={() => setShowSettings(!showSettings)}
      >
        ⚙️ Settings
      </button>

      {showSettings && (
        <div className="settingsPanel">
          <h2>Settings</h2>

          <label className="checkboxRow">
            <input
              type="checkbox"
              checked={enableVoice}
              onChange={(e) => setEnableVoice(e.target.checked)}
            />
            Voice response
          </label>

          {enableVoice && (
            <div className="optionBlock">
              <div className="modeButtons">
                <button
                  type="button"
                  className={voiceMode === "default" ? "activeMode" : ""}
                  onClick={() => setVoiceMode("default")}
                >
                  Default voice
                </button>

                <button
                  type="button"
                  className={voiceMode === "custom" ? "activeMode" : ""}
                  onClick={() => setVoiceMode("custom")}
                >
                  Create new voice
                </button>
              </div>

              {voiceMode === "custom" && (
                <>
                  <input
                    type="file"
                    accept=".wav,.mp3,.m4a,.mp4,.mov,.webm,audio/*,video/*"
                    onChange={(e) => {
                      setVoiceFile(e.target.files[0]);
                      setCustomVoiceId(null);
                    }}
                  />

                  {isUploadingVoice && <p>Uploading custom voice...</p>}
                  {customVoiceId && <p>Custom voice is ready ✅</p>}
                </>
              )}
            </div>
          )}

          <label className="checkboxRow">
            <input
              type="checkbox"
              checked={enableVideo}
              onChange={(e) => setEnableVideo(e.target.checked)}
            />
            Create video
          </label>

          {enableVideo && (
            <div className="optionBlock">
              <div className="modeButtons">
                <button
                  type="button"
                  className={avatarMode === "default" ? "activeMode" : ""}
                  onClick={() => setAvatarMode("default")}
                >
                  Default avatar
                </button>

                <button
                  type="button"
                  className={avatarMode === "custom" ? "activeMode" : ""}
                  onClick={() => setAvatarMode("custom")}
                >
                  Create new avatar
                </button>
              </div>

              {avatarMode === "custom" && (
                <input
                  type="file"
                  accept="image/*,video/*"
                  onChange={(e) => setAvatarFile(e.target.files[0])}
                />
              )}
            </div>
          )}
        </div>
      )}

      <div className="chat">
        {messages.map((message, index) => (
          <div key={message.id ?? index} className={`msg ${message.role}`}>
            {message.role === "assistant" ? (
              <>
                <ReactMarkdown>{message.content}</ReactMarkdown>

                {message.isAudioLoading && (
                  <div className="audioLoading">Generating voice...</div>
                )}

                {message.audioUrl && (
                  <audio
                    className="audioPlayer"
                    src={message.audioUrl}
                    controls
                    autoPlay
                  />
                )}
              </>
            ) : (
              <div>{message.content}</div>
            )}
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
