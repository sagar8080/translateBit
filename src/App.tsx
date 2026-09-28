import React, { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  AudioLines,
  Check,
  ChevronRight,
  Headphones,
  Info,
  Languages,
  Link2,
  LogOut,
  MessageSquare,
  Pause,
  Radio,
  RefreshCw,
  ShieldCheck,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import {
  languageName,
  nextPlayback,
  terminal,
  type Credentials,
  type Language,
  type Sample,
} from "./types";
import { useSession } from "./useSession";
import MediaTest from "./MediaTest";

const storageKey = "translatebit.session.v1";
function restore(): Credentials | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(storageKey) || "null");
    const invited = new URLSearchParams(location.search).get("room");
    return value &&
      typeof value.token === "string" &&
      typeof value.participant_id === "string" &&
      ["en", "hi"].includes(value.language) &&
      (!invited || invited === value.code)
      ? value
      : null;
  } catch {
    return null;
  }
}

function Brand() {
  return (
    <a className="brand" href="/" aria-label="TranslateBit home">
      <span className="brand-icon">
        <AudioLines size={23} />
      </span>
      Translate<span>Bit</span>
      <small>LAB</small>
    </a>
  );
}

export default function App() {
  const [credentials, setCredentials] = useState<Credentials | null>(restore);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [loadError, setLoadError] = useState("");
  useEffect(() => {
    fetch("/api/samples")
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then(setSamples)
      .catch(() =>
        setLoadError(
          "The local service is unavailable. Start the API, then refresh this page.",
        ),
      );
  }, []);
  const enter = (value: Credentials) => {
    sessionStorage.setItem(storageKey, JSON.stringify(value));
    setCredentials(value);
  };
  const leave = () => {
    window.speechSynthesis?.cancel();
    sessionStorage.removeItem(storageKey);
    setCredentials(null);
    history.replaceState({}, "", "/");
  };
  return (
    <>
      <header>
        <Brand />
        <div className="header-meta">
          <span className="status-dot" /> DEVELOPMENT PREVIEW{" "}
          <span className="version">v0.3</span>
        </div>
      </header>
      {credentials ? (
        <Workspace
          key={credentials.participant_id}
          credentials={credentials}
          samples={samples}
          leave={leave}
        />
      ) : (
        <Lobby enter={enter} loadError={loadError} />
      )}
    </>
  );
}

function Lobby({
  enter,
  loadError,
}: {
  enter: (value: Credentials) => void;
  loadError: string;
}) {
  const invited = new URLSearchParams(location.search).get("room") || "";
  const invitedLanguage = new URLSearchParams(location.search).get("language");
  const [language, setLanguage] = useState<Language>(
    invitedLanguage === "hi" || invitedLanguage === "en"
      ? invitedLanguage
      : invited
        ? "en"
        : "hi",
  );
  const [joining, setJoining] = useState(Boolean(invited));
  const [code, setCode] = useState(invited);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await fetch(
        joining
          ? `/api/rooms/${encodeURIComponent(code.trim().toUpperCase())}/join`
          : "/api/rooms",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ language }),
        },
      );
      const data = await response.json();
      if (!response.ok)
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Please check your room code and language.",
        );
      enter(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not connect.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="lobby">
      <div className="intro">
        <div className="eyebrow">
          <span /> TWO LANGUAGES. ONE CONVERSATION.
        </div>
        <h1>
          A conversation,
          <br />
          <em>understood.</em>
        </h1>
        <p className="intro-copy">
          A small space to explore Hindi–English interpretation. Built around
          the words that matter, and the people saying them.
        </p>
        <div className="language-illustration">
          <div>
            <span className="script">नमस्ते</span>
            <small>HINDI</small>
          </div>
          <span className="bridge">
            <AudioLines size={36} />
            <i />
            <i />
          </span>
          <div>
            <span className="script">Hello</span>
            <small>ENGLISH</small>
          </div>
        </div>
        <div className="intro-features">
          <span>
            <Headphones size={17} /> Two participants
          </span>
          <span>
            <MessageSquare size={17} /> Shared captions
          </span>
          <span>
            <Activity size={17} /> Every turn visible
          </span>
        </div>
      </div>
      <section className="entry-card">
        <div className="card-top">
          <span className="section-label">YOUR CONVERSATION SPACE</span>
          <span className="tag">Local prototype</span>
        </div>
        <h2>Take a seat.</h2>
        <p>
          Create a room, invite someone, and try a conversation in two
          languages.
        </p>
        <form onSubmit={submit}>
          <div className="switcher">
            <button
              type="button"
              className={!joining ? "selected" : ""}
              onClick={() => setJoining(false)}
            >
              Create a room
            </button>
            <button
              type="button"
              className={joining ? "selected" : ""}
              onClick={() => setJoining(true)}
            >
              Join a room
            </button>
          </div>
          {joining && (
            <label className="field-label">
              Room code
              <input
                required
                value={code}
                maxLength={8}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                placeholder="8-character code"
                autoComplete="off"
              />
            </label>
          )}
          <label className="field-label">I speak</label>
          <div className="language-options">
            {(["hi", "en"] as Language[]).map((value) => (
              <button
                key={value}
                type="button"
                className={
                  language === value
                    ? "language-option active"
                    : "language-option"
                }
                onClick={() => setLanguage(value)}
              >
                <span className="language-symbol">
                  {value === "hi" ? "अ" : "A"}
                </span>
                <span>
                  <strong>{languageName(value)}</strong>
                  <small>{value === "hi" ? "हिन्दी" : "English"}</small>
                </span>
                {language === value && <Check size={17} />}
              </button>
            ))}
          </div>
          <button
            className="primary full"
            disabled={busy || Boolean(loadError)}
          >
            {busy
              ? "Connecting…"
              : joining
                ? "Join conversation"
                : "Create conversation"}
            <ArrowRight size={18} />
          </button>
          {(error || loadError) && (
            <p className="error" role="alert">
              {error || loadError}
            </p>
          )}
        </form>
        <div className="demo-note">
          <Info size={18} />
          <p>
            <strong>Local microphone interpretation is ready to try.</strong>{" "}
            Speech recognition and translation run on this machine. Playback
            uses an installed local voice. Sample buttons use prewritten
            translations. Experimental results: verify the captions.
          </p>
        </div>
      </section>
      <footer className="lobby-footer">
        <ShieldCheck size={15} /> Synthetic conversations only <span>·</span> No
        audio recording <span>·</span> Rooms expire after 2 hours
      </footer>
    </main>
  );
}

function Workspace({
  credentials,
  samples,
  leave,
}: {
  credentials: Credentials;
  samples: Sample[];
  leave: () => void;
}) {
  const { room, connection, error, setError, send, reconnect } =
    useSession(credentials);
  const [tab, setTab] = useState<"conversation" | "events">("conversation");
  const [audioEnabled, setAudioEnabled] = useState(false);
  const [copied, setCopied] = useState(false);
  const [voiceNotice, setVoiceNotice] = useState("");
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const attempted = useRef(new Set<string>());
  const activePlayback = useRef<string | null>(null);
  const scroll = useRef<HTMLDivElement>(null);
  const ownLanguage = credentials.language;
  const otherLanguage: Language = ownLanguage === "hi" ? "en" : "hi";
  const other = room?.participants.find(
    (p) => p.id !== credentials.participant_id,
  );
  const ready = connection === "connected" && other?.connected;
  const segments = room?.segments || [];
  const completed = segments.filter((s) => s.status === "completed").length;
  const interrupted = segments.filter(
    (s) => s.status === "cancelled" || s.status === "interrupted",
  ).length;
  const failed = segments.filter((s) => s.status === "failed").length;
  const ownPending = segments.filter(
    (s) =>
      s.speaker_id === credentials.participant_id && !terminal.has(s.status),
  ).length;
  const incoming = segments.some(
    (s) =>
      s.speaker_id !== credentials.participant_id && !terminal.has(s.status),
  );
  const playing = segments.find(
    (s) =>
      s.speaker_id !== credentials.participant_id && s.status === "playing",
  );

  useEffect(() => {
    if (!window.speechSynthesis) return;
    const update = () => setVoices(window.speechSynthesis.getVoices());
    update();
    window.speechSynthesis.addEventListener("voiceschanged", update);
    return () => {
      window.speechSynthesis.removeEventListener("voiceschanged", update);
      window.speechSynthesis.cancel();
    };
  }, []);
  useEffect(() => {
    scroll.current?.scrollTo({
      top: scroll.current.scrollHeight,
      behavior: "smooth",
    });
  }, [segments.length, tab]);

  useEffect(() => {
    const current = segments.find((s) => s.id === activePlayback.current);
    if (current && terminal.has(current.status)) {
      activePlayback.current = null;
      window.speechSynthesis?.cancel();
    }
    if (connection !== "connected") {
      activePlayback.current = null;
      return;
    }
    if (!audioEnabled || activePlayback.current) return;
    const next = nextPlayback(
      room,
      credentials.participant_id,
      attempted.current,
    );
    if (!next) return;
    const voice = voices.find(
      (v) => v.localService && v.lang.toLowerCase().startsWith(ownLanguage),
    );
    attempted.current.add(next.id);
    if (!window.speechSynthesis || !voice) {
      setVoiceNotice(
        `No ${languageName(ownLanguage)} browser voice is installed. Read the translated captions; audio is marked unavailable.`,
      );
      send({ type: "playback", segment_id: next.id, action: "failed" });
      return;
    }
    const utterance = new SpeechSynthesisUtterance(next.translation);
    utterance.voice = voice;
    utterance.lang = voice.lang;
    utterance.rate = 0.93;
    activePlayback.current = next.id;
    utterance.onstart = () => {
      if (activePlayback.current === next.id)
        send({ type: "playback", segment_id: next.id, action: "started" });
    };
    utterance.onend = () => {
      if (activePlayback.current !== next.id) return;
      activePlayback.current = null;
      send({ type: "playback", segment_id: next.id, action: "completed" });
    };
    utterance.onerror = () => {
      if (activePlayback.current !== next.id) return;
      activePlayback.current = null;
      setVoiceNotice("Browser playback failed. Captions are still available.");
      send({ type: "playback", segment_id: next.id, action: "failed" });
    };
    window.speechSynthesis.speak(utterance);
  }, [
    room,
    segments,
    audioEnabled,
    connection,
    credentials.participant_id,
    ownLanguage,
    send,
    voices,
  ]);

  function stopPlayback() {
    activePlayback.current = null;
    window.speechSynthesis?.cancel();
    send({ type: "stop" });
  }
  async function copyInvite() {
    try {
      await navigator.clipboard.writeText(
        `${location.origin}/?room=${credentials.code}&language=${otherLanguage}`,
      );
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      setError(`Copy this room code to invite someone: ${credentials.code}`);
    }
  }
  return (
    <main className="workspace">
      <div className="workspace-heading">
        <div>
          <div className="breadcrumb">
            WORKSPACE <ChevronRight size={12} /> HINDI ↔ ENGLISH
          </div>
          <h1>
            Conversation room<span className="tag">Local prototype</span>
          </h1>
          <p>A shared space. A little less lost in translation.</p>
        </div>
        <button className="quiet" onClick={leave}>
          <LogOut size={16} /> Leave room
        </button>
      </div>
      <div className="notice-strip">
        <Info size={16} />
        <span>
          Microphone: local models · Sample buttons: prewritten translations
        </span>
        <span className="notice-end">
          Local speech recognition and translation available below
        </span>
      </div>
      <MediaTest
        credentials={credentials}
        connected={connection === "connected"}
        partnerConnected={Boolean(other?.connected)}
        notice={room?.notices?.[credentials.participant_id]}
      />
      <div className="workspace-grid">
        <aside className="left-column">
          <section className="panel room-panel">
            <div className="section-label">
              THE ROOM{" "}
              <span
                className={`connection-dot ${connection === "connected" ? "online" : ""}`}
              />
            </div>
            <div className="room-code">{credentials.code}</div>
            <button className="secondary full" onClick={copyInvite}>
              {copied ? <Check size={15} /> : <Link2 size={15} />}{" "}
              {copied ? "Invite copied" : "Copy invite link"}
            </button>
            <a
              className="text-link"
              target="_blank"
              rel="noopener noreferrer"
              href={`/?room=${credentials.code}&language=${otherLanguage}`}
            >
              Open second participant <ArrowRight size={13} />
            </a>
            <div className="divider" />
            <div className="section-label">
              PARTICIPANTS <span> {room?.participants.length || 1}/2</span>
            </div>
            <ParticipantCard
              language={ownLanguage}
              own
              connected={connection === "connected"}
            />
            <ParticipantCard
              language={otherLanguage}
              connected={Boolean(other?.connected)}
            />
          </section>
          <section className="panel listening-panel">
            <Headphones size={21} />
            <h3>Make room for listening.</h3>
            <p>
              Use two browser windows to try the flow. Wear headphones when
              testing on separate devices.
            </p>
            <div className="small-note">
              Your phrases stay in this session. Microphone capture runs only
              while the audio test is active.
            </div>
          </section>
        </aside>
        <section className="panel conversation-panel">
          <div className="conversation-tabs">
            <button
              className={tab === "conversation" ? "active" : ""}
              onClick={() => setTab("conversation")}
            >
              <MessageSquare size={16} /> Conversation
            </button>
            <button
              className={tab === "events" ? "active" : ""}
              onClick={() => setTab("events")}
            >
              <Activity size={16} /> Event log
            </button>
            <span className="connection-label">
              <span className={`connection-dot ${ready ? "online" : ""}`} />
              {connection !== "connected"
                ? connection
                : ready
                  ? "Both connected"
                  : "Waiting for partner"}
            </span>
          </div>
          <div className="conversation-feed" ref={scroll}>
            {tab === "events" ? (
              <div className="event-list">
                <div className="event-heading">
                  <span>SESSION EVENTS</span>
                  <span>LOCAL TIME</span>
                </div>
                {room?.events.map((event, i) => (
                  <div className="event-row" key={`${event.at}-${i}`}>
                    <span className="event-dot" />
                    <div>
                      <strong>{event.name.replaceAll("_", " ")}</strong>
                      {event.segment_id && <small>{event.segment_id}</small>}
                    </div>
                    <time>
                      {new Date(event.at * 1000).toLocaleTimeString()}
                    </time>
                  </div>
                ))}
              </div>
            ) : segments.length === 0 ? (
              <div className="empty-conversation">
                <div className="empty-art">
                  <span>अ</span>
                  <AudioLines size={32} />
                  <span>A</span>
                </div>
                <h2>
                  Every conversation
                  <br />
                  starts with a first word.
                </h2>
                <p>
                  {ready
                    ? "Start local interpretation above, or choose a sample phrase. Your partner will see its translation in their language."
                    : "Invite your partner, then choose a sample phrase to begin."}
                </p>
                <span className="empty-caption">
                  HINDI <span>↔</span> ENGLISH
                </span>
              </div>
            ) : (
              <div className="segments">
                <div className="session-date">TODAY · CONVERSATION</div>
                {segments.map((segment, i) => (
                  <article
                    className={`segment ${segment.speaker_id === credentials.participant_id ? "own" : ""}`}
                    key={segment.id}
                  >
                    <div className="segment-heading">
                      <span className={`mini-avatar ${segment.language}`}>
                        {segment.language === "hi" ? "अ" : "A"}
                      </span>
                      <strong>
                        {languageName(segment.language)} speaker
                        {segment.speaker_id === credentials.participant_id
                          ? " · You"
                          : ""}
                      </strong>
                      <time>
                        {new Date(segment.created_at * 1000).toLocaleTimeString(
                          [],
                          { hour: "2-digit", minute: "2-digit" },
                        )}
                      </time>
                      <span className="segment-number">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                    </div>
                    <div className="segment-body">
                      <p lang={segment.language}>
                        {segment.source || "Recognizing microphone speech…"}
                      </p>
                      {segment.translation && (
                        <div className="translation">
                          <span>
                            <Languages size={12} />{" "}
                            {segment.language === "hi" ? "ENGLISH" : "HINDI"}
                          </span>
                          <p lang={segment.language === "hi" ? "en" : "hi"}>
                            {segment.translation}
                          </p>
                        </div>
                      )}
                      <div className={`segment-status ${segment.status}`}>
                        <span className="tiny-dot" />
                        {segment.status === "queued"
                          ? "Waiting for listener playback"
                          : segment.status === "completed"
                            ? "Browser playback ended"
                            : segment.status === "recognizing"
                              ? "Recognizing and translating locally…"
                              : segment.status === "translating"
                                ? "Preparing sample translation…"
                                : segment.status}
                        {segment.processing_ms !== null && (
                          <span>
                            · {segment.processing_ms} ms{" "}
                            {segment.origin === "local"
                              ? "local processing"
                              : "simulated processing"}
                          </span>
                        )}
                      </div>
                      {segment.error && (
                        <p className="segment-error">{segment.error}</p>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>
          <div className="playback-bar">
            <div>
              <Volume2 size={16} />
              <span>
                {playing
                  ? "Playing translated speech"
                  : audioEnabled
                    ? "Browser audio enabled"
                    : "Enable audio to hear translations"}
              </span>
            </div>
            <button
              className={audioEnabled ? "audio-toggle enabled" : "audio-toggle"}
              onClick={() => {
                if (audioEnabled) stopPlayback();
                window.speechSynthesis?.resume();
                setAudioEnabled(!audioEnabled);
              }}
            >
              {audioEnabled ? <VolumeX size={14} /> : <Volume2 size={14} />}{" "}
              {audioEnabled ? "Disable audio" : "Enable audio"}
            </button>
          </div>
          {voiceNotice && <div className="voice-notice">{voiceNotice}</div>}
          <div className="composer">
            <div className="composer-heading">
              <span className="section-label">
                TRY A PHRASE IN {languageName(ownLanguage).toUpperCase()}
              </span>
              <span>Prewritten samples</span>
            </div>
            <div className="sample-buttons">
              {samples
                .filter((s) => s.language === ownLanguage)
                .map((sample, i) => (
                  <button
                    key={sample.id}
                    disabled={!ready || ownPending >= 4}
                    title={sample.source}
                    onClick={() => {
                      setError("");
                      send({ type: "submit", sample_id: sample.id });
                    }}
                  >
                    <span>{String(i + 1).padStart(2, "0")}</span>
                    {sample.label}
                    <ArrowRight size={14} />
                  </button>
                ))}
            </div>
            <div className="composer-bottom">
              <span>
                <Info size={12} />{" "}
                {ready
                  ? "New phrases preserve earlier turns."
                  : "Connect both participants to send a phrase."}
              </span>
              <button
                className="stop-button"
                disabled={!incoming || connection !== "connected"}
                onClick={stopPlayback}
              >
                <Pause size={13} /> Stop incoming playback
              </button>
            </div>
          </div>
        </section>
        <aside className="right-column">
          <section className="panel pulse-panel">
            <div className="section-label">
              <Activity size={15} /> SESSION PULSE{" "}
              <span className="tag tiny">DEMO</span>
            </div>
            <div className="pulse-count">
              {String(segments.length).padStart(2, "0")}
              <span>conversation segments</span>
            </div>
            <div className="metric-row">
              <span>Playback completed</span>
              <strong>{completed}</strong>
            </div>
            <div className="metric-row">
              <span>Stopped / interrupted</span>
              <strong>{interrupted}</strong>
            </div>
            <div className="metric-row">
              <span>Failed / unavailable</span>
              <strong>{failed}</strong>
            </div>
            <div className="metric-row">
              <span>Participant reconnects</span>
              <strong>
                {room?.participants.reduce((sum, p) => sum + p.reconnects, 0) ||
                  0}
              </strong>
            </div>
            <div className="divider" />
            <div className="unmeasured">
              <span>Speech-to-speech latency</span>
              <strong>Not measured</strong>
              <p>
                Each phrase shows local model processing time. End-to-end delay
                through listener playback has not yet been measured.
              </p>
            </div>
          </section>
          <section className="panel pipeline-panel">
            <div className="section-label">THIS BUILD</div>
            {[
              ["01", "Shared room", "Two participants, one session"],
              ["02", "Ordered phrases", "Independent language lanes"],
              ["03", "Playback controls", "Stop without stale replay"],
              ["04", "Visible events", "Every state change recorded"],
            ].map(([n, title, detail]) => (
              <div className="pipeline-step" key={n}>
                <span>{n}</span>
                <div>
                  <strong>{title}</strong>
                  <small>{detail}</small>
                </div>
                <Check size={13} />
              </div>
            ))}
            <div className="next-milestone">
              <Radio size={16} />
              <div>
                <strong>Local interpretation available</strong>
                <p>
                  Select live interpretation above. Model quality remains under
                  evaluation.
                </p>
              </div>
            </div>
          </section>
          <button
            className="reconnect-button"
            disabled={connection === "connecting"}
            onClick={() => {
              stopPlayback();
              reconnect();
            }}
          >
            <RefreshCw size={13} /> Reconnect this participant
          </button>
        </aside>
      </div>
      {error && (
        <div className="toast" role="alert">
          <Info size={18} />
          <span>{error}</span>
          <button aria-label="Dismiss error" onClick={() => setError("")}>
            <X size={16} />
          </button>
        </div>
      )}
      <footer className="workspace-footer">
        <span>
          <ShieldCheck size={13} /> Synthetic conversations · No audio saved
        </span>
        <span>TranslateBit / Development notebook 001</span>
      </footer>
    </main>
  );
}

function ParticipantCard({
  language,
  own,
  connected,
}: {
  language: Language;
  own?: boolean;
  connected: boolean;
}) {
  return (
    <div className="participant">
      <span className={`avatar ${language}`}>
        {language === "hi" ? "अ" : "A"}
      </span>
      <div>
        <strong>
          {languageName(language)} speaker {own && <small>You</small>}
        </strong>
        <span>
          <i className={`connection-dot ${connected ? "online" : ""}`} />
          {connected ? "Connected" : "Not connected"}
        </span>
      </div>
    </div>
  );
}
