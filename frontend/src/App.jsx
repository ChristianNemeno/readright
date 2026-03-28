import { startTransition, useEffect, useRef, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];

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

function Stars({ count, total = 3 }) {
  return (
    <div className="stars-row">
      {Array.from({ length: total }, (_, i) => (
        <span key={i} className={`star ${i < count ? "star-filled" : "star-empty"}`}>★</span>
      ))}
    </div>
  );
}

function Soundwave({ stream, active }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!stream || !active) return;
    let animId;
    let audioCtx;
    try {
      audioCtx = new AudioContext();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 128;
      source.connect(analyser);
      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      const canvas = canvasRef.current;
      const ctx = canvas.getContext("2d");
      const BARS = 32;
      const supportsRoundRect = typeof ctx.roundRect === "function";

      function draw() {
        animId = requestAnimationFrame(draw);
        analyser.getByteFrequencyData(dataArray);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const barW = Math.floor(canvas.width / BARS) - 2;
        const cy = canvas.height / 2;
        for (let i = 0; i < BARS; i++) {
          const v = dataArray[Math.floor((i * bufferLength) / BARS)] / 255;
          const h = Math.max(4, v * canvas.height * 0.85);
          ctx.fillStyle = `rgba(56, 189, 248, ${0.35 + v * 0.65})`;
          const x = i * (barW + 2);
          if (supportsRoundRect) {
            ctx.beginPath();
            ctx.roundRect(x, cy - h / 2, barW, h, 2);
            ctx.fill();
          } else {
            ctx.fillRect(x, cy - h / 2, barW, h);
          }
        }
      }
      draw();
    } catch (_) {}

    return () => {
      cancelAnimationFrame(animId);
      audioCtx?.close();
    };
  }, [stream, active]);

  return (
    <div className="soundwave-wrap">
      <canvas
        ref={canvasRef}
        className={`soundwave-canvas ${active ? "soundwave-active" : ""}`}
        width={280}
        height={64}
      />
    </div>
  );
}

function SelectScreen({ passages, loading, onSelect }) {
  return (
    <div className="screen screen-select">
      <header className="app-header">
        <span className="app-logo">ReadRight</span>
        <p className="app-subtitle">Phil-IRI Reading Assessment</p>
      </header>

      {loading ? (
        <div className="loading-state">
          <div className="loading-ring" />
          <p>Loading passages...</p>
        </div>
      ) : (
        <div className="passage-grid">
          {passages.map((p) => (
            <button key={p.id} className="passage-card" onClick={() => onSelect(p)}>
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
  passage, recordingState, recordedBlob, selectedFile, liveStream,
  isSubmitting, errorMessage,
  onBack, onStartRecording, onStopRecording, onFileChange, onSubmit,
}) {
  const hasAudio = !!(selectedFile ?? recordedBlob);
  const fileInputRef = useRef(null);
  const isRecording = recordingState === "recording";

  const statusText = isRecording
    ? "Recording — tap to stop"
    : recordedBlob
      ? "Recording ready"
      : selectedFile
        ? selectedFile.name
        : "Tap the mic to start";

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
        <Soundwave stream={liveStream} active={isRecording} />

        <p className="record-hint">{statusText}</p>

        <button
          className={`mic-btn ${isRecording ? "mic-btn--recording" : ""}`}
          onClick={isRecording ? onStopRecording : onStartRecording}
          disabled={isSubmitting || typeof MediaRecorder === "undefined"}
          aria-label={isRecording ? "Stop recording" : "Start recording"}
        >
          🎤
        </button>

        <div className="or-divider"><span>or</span></div>

        <button className="upload-btn" onClick={() => fileInputRef.current?.click()} disabled={isSubmitting}>
          Upload File
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".mp4,.mov,.webm,.wav,.m4a,.mp3,.ogg,audio/*,video/*"
          onChange={onFileChange}
          style={{ display: "none" }}
        />

        <button className="submit-btn" onClick={onSubmit} disabled={isSubmitting || !hasAudio}>
          {isSubmitting ? "Analyzing..." : "Analyze Recording"}
        </button>
      </div>
    </div>
  );
}

function ResultScreen({ result, onTryAgain, onPickNew }) {
  const stars = getStars(result?.reading_level);

  const levelMessage = {
    3: "Independent level achieved",
    2: "Instructional level",
    1: "Frustration level",
    0: "Assessment complete",
  }[stars];

  const recognitionPct = result?.word_recognition_pct ?? 0;

  return (
    <div className="screen screen-result">
      <div className="result-hero">
        <Stars count={stars} />
        <p className="level-message">{levelMessage}</p>
        {result?.reading_level && (
          <span className="reading-level-badge">{result.reading_level}</span>
        )}
      </div>

      <div className="metrics-row">
        <div className="metric-bubble">
          <strong className="metric-value">{result?.wpm ?? "—"}</strong>
          <span className="metric-label">WPM</span>
        </div>
        <div className="metric-bubble">
          <strong className="metric-value">{formatTime(result?.reading_time_seconds)}</strong>
          <span className="metric-label">Time</span>
        </div>
        <div className="metric-bubble">
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
      </div>

      {result?.miscues?.length > 0 && (
        <div className="miscue-section">
          <h3 className="miscue-title">Miscue Analysis</h3>
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
        <button className="action-btn action-btn--secondary" onClick={onTryAgain}>Try Again</button>
        <button className="action-btn action-btn--primary" onClick={onPickNew}>New Passage</button>
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
  const [liveStream, setLiveStream] = useState(null);
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
      setLiveStream(stream);
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      recorder.onstop = () => {
        const outMime = recorder.mimeType || mimeType || "audio/webm";
        setRecordedBlob(new Blob(chunksRef.current, { type: outMime }));
        setRecordingState("stopped");
        setLiveStream(null);
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      };
      recorder.start();
      setRecordingState("recording");
    } catch (e) {
      setErrorMessage(e.message || "Microphone access failed.");
      setRecordingState("idle");
      setLiveStream(null);
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
    if (!uploadBlob) { setErrorMessage("Please record or upload audio first."); return; }
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
        liveStream={liveStream}
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
