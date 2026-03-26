import { startTransition, useEffect, useRef, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
const CARD_COLORS = [
  "#FFE082", "#B3E5FC", "#C8E6C9", "#F8BBD9",
  "#D1C4E9", "#FFCCBC", "#B2EBF2", "#DCEDC8",
];
const CONFETTI_COLORS = ["#FFE066", "#4FC3F7", "#81C784", "#FF8A65", "#F48FB1", "#CE93D8"];
const CONFETTI_PIECES = Array.from({ length: 25 }, (_, i) => ({
  id: i,
  left: (i * 17 + 5) % 100,
  color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
  delay: (i * 0.15) % 2,
  duration: 2.5 + (i % 5) * 0.4,
  size: 8 + (i % 4) * 3,
}));

function pickMimeType() {
  if (typeof MediaRecorder === "undefined") return "";
  return MIME_CANDIDATES.find((c) => MediaRecorder.isTypeSupported(c)) ?? "";
}

function getExt(mimeType) {
  return mimeType.includes("mp4") ? "m4a" : "webm";
}

function getStars(level) {
  if (level === "Independent") return 3;
  if (level === "Instructional") return 2;
  if (level === "Frustration") return 1;
  return 0;
}

function formatTime(s) {
  if (s == null) return "—";
  const t = Math.max(0, Math.round(s));
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
}

function Confetti() {
  return (
    <div className="confetti-wrap" aria-hidden="true">
      {CONFETTI_PIECES.map((p) => (
        <div
          key={p.id}
          className="confetti-piece"
          style={{
            left: `${p.left}%`,
            backgroundColor: p.color,
            animationDelay: `${p.delay}s`,
            animationDuration: `${p.duration}s`,
            width: `${p.size}px`,
            height: `${p.size}px`,
          }}
        />
      ))}
    </div>
  );
}

function Stars({ count, total = 3 }) {
  return (
    <div className="stars-row">
      {Array.from({ length: total }, (_, i) => (
        <span key={i} className={`star ${i < count ? "star-filled" : "star-empty"}`}>★</span>
      ))}
    </div>
  );
}

function SelectScreen({ passages, loading, onSelect }) {
  return (
    <div className="screen screen-select">
      <header className="app-header">
        <span className="owl-mascot">🦉</span>
        <h1 className="app-title">ReadRight</h1>
        <p className="app-subtitle">Pick a story to read!</p>
      </header>

      {loading ? (
        <div className="loading-state">
          <span className="loading-spinner">📚</span>
          <p>Loading stories...</p>
        </div>
      ) : (
        <div className="passage-grid">
          {passages.map((p, i) => (
            <button
              key={p.id}
              className="passage-card"
              style={{ backgroundColor: CARD_COLORS[i % CARD_COLORS.length] }}
              onClick={() => onSelect(p)}
            >
              <span className="passage-card-icon">📖</span>
              <h3 className="passage-card-title">{p.title}</h3>
              <div className="passage-card-meta">
                <span className="grade-badge">Grade {p.grade_level}</span>
                <span className="lang-badge">{p.language}</span>
              </div>
              <p className="passage-card-words">{p.word_count} words</p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ReadScreen({
  passage, recordingState, recordedBlob, selectedFile,
  isSubmitting, errorMessage,
  onBack, onStartRecording, onStopRecording, onFileChange, onSubmit,
}) {
  const hasAudio = !!(selectedFile ?? recordedBlob);
  const fileInputRef = useRef(null);

  const statusText = recordingState === "recording"
    ? "🔴 Recording... tap to stop"
    : recordedBlob
      ? "✅ Recording ready!"
      : selectedFile
        ? `✅ ${selectedFile.name}`
        : "Tap the mic to start!";

  return (
    <div className="screen screen-read">
      <div className="read-topbar">
        <button className="back-btn" onClick={onBack}>← Back</button>
        <span className="read-topbar-title">{passage?.title}</span>
        <span className="grade-badge">Grade {passage?.grade_level}</span>
      </div>

      <div className="passage-text-card">
        <p className="passage-text">{passage?.text ?? "Loading..."}</p>
      </div>

      {errorMessage && <div className="error-bubble">{errorMessage}</div>}

      <div className="record-area">
        <p className="record-hint">{statusText}</p>

        <button
          className={`mic-btn ${recordingState === "recording" ? "mic-btn--recording" : ""}`}
          onClick={recordingState === "recording" ? onStopRecording : onStartRecording}
          disabled={isSubmitting || typeof MediaRecorder === "undefined"}
          aria-label={recordingState === "recording" ? "Stop recording" : "Start recording"}
        >
          🎤
        </button>

        <div className="or-divider"><span>or</span></div>

        <button className="upload-btn" onClick={() => fileInputRef.current?.click()} disabled={isSubmitting}>
          📁 Upload Recording
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".mp4,.mov,.webm,.wav,.m4a,.mp3,.ogg,audio/*,video/*"
          onChange={onFileChange}
          style={{ display: "none" }}
        />

        <button
          className="submit-btn"
          onClick={onSubmit}
          disabled={isSubmitting || !hasAudio}
        >
          {isSubmitting ? "⏳ Checking..." : "✨ Check My Reading!"}
        </button>
      </div>
    </div>
  );
}

function ResultScreen({ result, onTryAgain, onPickNew }) {
  const stars = getStars(result?.reading_level);
  const showConfetti = stars === 3;

  const levelMessage = {
    3: "Amazing job! 🎉",
    2: "Good reading! Keep it up! 😊",
    1: "Keep practicing! You can do it! 💪",
    0: "Assessment complete!",
  }[stars];

  const recognitionPct = result?.word_recognition_pct ?? 0;
  const recognitionFace = recognitionPct >= 95 ? "😄" : recognitionPct >= 90 ? "🙂" : "😐";

  return (
    <div className="screen screen-result">
      {showConfetti && <Confetti />}

      <div className="result-hero">
        <span className="owl-mascot owl-big">🦉</span>
        <Stars count={stars} />
        <p className="level-message">{levelMessage}</p>
        {result?.reading_level && (
          <span className="reading-level-badge">{result.reading_level}</span>
        )}
      </div>

      <div className="metrics-row">
        <div className="metric-bubble metric-wpm">
          <span className="metric-icon">⚡</span>
          <strong className="metric-value">{result?.wpm ?? "—"}</strong>
          <span className="metric-label">Words/Min</span>
        </div>
        <div className="metric-bubble metric-time">
          <span className="metric-icon">⏱️</span>
          <strong className="metric-value">{formatTime(result?.reading_time_seconds)}</strong>
          <span className="metric-label">Time</span>
        </div>
        <div className="metric-bubble metric-words">
          <span className="metric-icon">📝</span>
          <strong className="metric-value">{result?.total_words ?? "—"}</strong>
          <span className="metric-label">Words</span>
        </div>
      </div>

      <div className="recognition-card">
        <div className="recognition-header">
          <span>Word Recognition</span>
          <strong>{result?.word_recognition_pct != null ? `${result.word_recognition_pct}%` : "—"}</strong>
        </div>
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${recognitionPct}%` }} />
        </div>
        <div className="progress-face">{recognitionFace}</div>
      </div>

      {result?.miscues?.length > 0 && (
        <div className="miscue-section">
          <h3 className="miscue-title">How I Read Each Word</h3>
          <div className="miscue-stream">
            {result.miscues.map((m, i) => (
              <span key={i} className={`word-chip word-chip--${m.type}`} title={m.type}>
                {m.target}
              </span>
            ))}
          </div>
          <div className="miscue-legend">
            <span className="legend-item"><span className="chip-dot chip-dot--correct" />Correct</span>
            <span className="legend-item"><span className="chip-dot chip-dot--mispronunciation" />Mispronounced</span>
            <span className="legend-item"><span className="chip-dot chip-dot--omission" />Missed</span>
            <span className="legend-item"><span className="chip-dot chip-dot--insertion" />Added</span>
          </div>
        </div>
      )}

      <div className="result-actions">
        <button className="action-btn action-btn--secondary" onClick={onTryAgain}>🔁 Try Again</button>
        <button className="action-btn action-btn--primary" onClick={onPickNew}>📚 New Story</button>
      </div>
    </div>
  );
}

export default function App() {
  const [screen, setScreen] = useState("select");
  const [passages, setPassages] = useState([]);
  const [loadingPassages, setLoadingPassages] = useState(true);
  const [selectedPassage, setSelectedPassage] = useState(null);
  const [recordingState, setRecordingState] = useState("idle");
  const [recordedBlob, setRecordedBlob] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);

  useEffect(() => {
    const ctrl = new AbortController();
    async function load() {
      try {
        setLoadingPassages(true);
        const res = await fetch(`${API_BASE}/passages`, { signal: ctrl.signal });
        if (!res.ok) throw new Error("Failed to load passages.");
        const data = await res.json();
        startTransition(() => setPassages(data));
      } catch (e) {
        if (e.name !== "AbortError") setErrorMessage(e.message);
      } finally {
        setLoadingPassages(false);
      }
    }
    load();
    return () => ctrl.abort();
  }, []);

  useEffect(() => {
    return () => {
      if (recorderRef.current?.state !== "inactive") recorderRef.current?.stop();
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  async function handleSelectPassage(passage) {
    try {
      const res = await fetch(`${API_BASE}/passages/${passage.id}`);
      setSelectedPassage(res.ok ? await res.json() : passage);
    } catch {
      setSelectedPassage(passage);
    }
    setRecordedBlob(null);
    setSelectedFile(null);
    setRecordingState("idle");
    setErrorMessage("");
    setResult(null);
    setScreen("read");
  }

  async function handleStartRecording() {
    try {
      setErrorMessage("");
      setSelectedFile(null);
      setRecordedBlob(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = pickMimeType();
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      chunksRef.current = [];
      recorderRef.current = recorder;
      streamRef.current = stream;
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      recorder.onstop = () => {
        const outMime = recorder.mimeType || mimeType || "audio/webm";
        setRecordedBlob(new Blob(chunksRef.current, { type: outMime }));
        setRecordingState("stopped");
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      };
      recorder.start();
      setRecordingState("recording");
    } catch (e) {
      setErrorMessage(e.message || "Microphone access failed.");
      setRecordingState("idle");
    }
  }

  function handleStopRecording() {
    if (recorderRef.current?.state !== "inactive") recorderRef.current.stop();
  }

  function handleFileChange(e) {
    const file = e.target.files?.[0] ?? null;
    setSelectedFile(file);
    if (file) setRecordedBlob(null);
  }

  async function handleSubmit() {
    const uploadBlob = selectedFile ?? recordedBlob;
    if (!uploadBlob) { setErrorMessage("Please record or upload audio first!"); return; }
    setErrorMessage("");
    const formData = new FormData();
    const fileName = selectedFile?.name ?? `recording.${getExt(recordedBlob?.type || "audio/webm")}`;
    formData.append("file", uploadBlob, fileName);
    formData.append("passage_id", selectedPassage.id);
    try {
      setIsSubmitting(true);
      const res = await fetch(`${API_BASE}/assess`, { method: "POST", body: formData });
      const payload = await res.json();
      if (!res.ok) throw new Error(payload.detail || "Assessment failed.");
      startTransition(() => { setResult(payload); setScreen("result"); });
    } catch (e) {
      setErrorMessage(e.message || "Assessment failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (screen === "select") {
    return <SelectScreen passages={passages} loading={loadingPassages} onSelect={handleSelectPassage} />;
  }
  if (screen === "read") {
    return (
      <ReadScreen
        passage={selectedPassage}
        recordingState={recordingState}
        recordedBlob={recordedBlob}
        selectedFile={selectedFile}
        isSubmitting={isSubmitting}
        errorMessage={errorMessage}
        onBack={() => setScreen("select")}
        onStartRecording={handleStartRecording}
        onStopRecording={handleStopRecording}
        onFileChange={handleFileChange}
        onSubmit={handleSubmit}
      />
    );
  }
  return (
    <ResultScreen
      result={result}
      onTryAgain={() => setScreen("read")}
      onPickNew={() => setScreen("select")}
    />
  );
}
