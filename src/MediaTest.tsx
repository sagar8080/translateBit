import { useCallback, useEffect, useRef, useState } from "react";
import { Mic, Square } from "lucide-react";
import type { Credentials } from "./types";

type Attempt = {
  id: string;
  peer: RTCPeerConnection | null;
  stream: MediaStream | null;
  abort: AbortController;
  timer?: ReturnType<typeof setInterval>;
  deadline?: ReturnType<typeof setTimeout>;
};

export default function MediaTest({
  credentials,
  connected,
  partnerConnected,
  notice,
}: {
  credentials: Credentials;
  connected: boolean;
  partnerConnected: boolean;
  notice?: string;
}) {
  const [state, setState] = useState("idle");
  const [mode, setMode] = useState<"loopback" | "interpret">("interpret");
  const [error, setError] = useState("");
  const [stats, setStats] = useState({
    sent: 0,
    received: 0,
    lost: 0,
    jitter: 0,
  });
  const current = useRef<Attempt | null>(null);
  const audio = useRef<HTMLAudioElement>(null);
  const base = `/api/rooms/${credentials.code}`;
  const headers = { Authorization: `Bearer ${credentials.token}` };

  const stop = useCallback(() => {
    const attempt = current.current;
    current.current = null;
    if (attempt) {
      attempt.abort.abort();
      clearInterval(attempt.timer);
      clearTimeout(attempt.deadline);
      attempt.stream?.getTracks().forEach((track) => track.stop());
      attempt.peer?.close();
      void fetch(`${base}/media/${attempt.id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${credentials.token}` },
        keepalive: true,
      }).catch(() => {});
    }
    if (audio.current) {
      audio.current.pause();
      audio.current.srcObject = null;
    }
    setState("idle");
  }, [base, credentials.token]);

  useEffect(() => {
    if (!connected) stop();
  }, [connected, stop]);
  useEffect(() => {
    const leave = () => stop();
    window.addEventListener("pagehide", leave);
    return () => {
      window.removeEventListener("pagehide", leave);
      stop();
    };
  }, [stop]);

  async function start() {
    stop();
    setError("");
    setStats({ sent: 0, received: 0, lost: 0, jitter: 0 });
    setState("requesting microphone");
    const attempt: Attempt = {
      id: crypto.randomUUID(),
      peer: null,
      stream: null,
      abort: new AbortController(),
    };
    current.current = attempt;
    attempt.deadline = setTimeout(() => {
      if (current.current === attempt) {
        stop();
        setError("Audio setup timed out. Start again when ready.");
      }
    }, 25000);
    const active = () => current.current === attempt;
    try {
      if (!navigator.mediaDevices?.getUserMedia)
        throw new Error(
          "Microphone access requires localhost or HTTPS and a supported browser.",
        );
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
        video: false,
      });
      if (!active()) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      attempt.stream = stream;
      stream.getTracks().forEach((track) =>
        track.addEventListener("ended", () => {
          if (active()) {
            stop();
            setError("Microphone disconnected. Reconnect it and start again.");
          }
        }),
      );
      const configResponse = await fetch(`${base}/media-config`, {
        headers,
        signal: attempt.abort.signal,
      });
      if (!configResponse.ok)
        throw new Error(
          "The media service is unavailable. Reconnect to the room.",
        );
      const config = await configResponse.json();
      if (!active()) return;
      const peer = new RTCPeerConnection({ iceServers: config.iceServers });
      attempt.peer = peer;
      clearTimeout(attempt.deadline);
      attempt.deadline = setTimeout(() => {
        if (active()) {
          stop();
          setError("The two-minute audio test has ended.");
        }
      }, 115000);
      peer.ontrack = (event) => {
        if (!active() || !audio.current) return;
        audio.current.srcObject = new MediaStream([event.track]);
        void audio.current.play().catch(() => {
          if (active())
            setError(
              "Use the audio player’s Play button to hear the return stream.",
            );
        });
      };
      peer.onconnectionstatechange = () => {
        if (!active()) return;
        setState(peer.connectionState);
        if (
          ["failed", "closed", "disconnected"].includes(peer.connectionState)
        ) {
          stop();
          setError(
            "Audio connection ended. Start the test again to reconnect.",
          );
        }
      };
      stream.getAudioTracks().forEach((track) => peer.addTrack(track, stream));
      setState("connecting");
      await peer.setLocalDescription(await peer.createOffer());
      // Complete ICE in the offer. No separate trickle-ICE service is needed for this milestone.
      await new Promise<void>((resolve, reject) => {
        if (peer.iceGatheringState === "complete") {
          resolve();
          return;
        }
        const cleanup = () => {
          clearTimeout(timeout);
          peer.removeEventListener("icegatheringstatechange", changed);
          attempt.abort.signal.removeEventListener("abort", aborted);
        };
        const changed = () => {
          if (peer.iceGatheringState === "complete") {
            cleanup();
            resolve();
          }
        };
        const aborted = () => {
          cleanup();
          reject(new Error("Stopped"));
        };
        const timeout = setTimeout(() => {
          cleanup();
          reject(new Error("Connection discovery timed out. Try again."));
        }, 10000);
        peer.addEventListener("icegatheringstatechange", changed);
        attempt.abort.signal.addEventListener("abort", aborted);
        if (attempt.abort.signal.aborted) aborted();
      });
      if (!active()) return;
      const response = await fetch(`${base}/media-offer`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        signal: attempt.abort.signal,
        body: JSON.stringify({
          sdp: peer.localDescription!.sdp,
          session_id: attempt.id,
          mode,
        }),
      });
      if (!response.ok) {
        const failure = await response.json();
        throw new Error(
          failure.detail || "Audio negotiation failed. Stop and try again.",
        );
      }
      const answer = await response.json();
      if (!active()) return;
      await peer.setRemoteDescription(answer);
      attempt.timer = setInterval(async () => {
        if (!active()) return;
        const report = await peer.getStats().catch(() => null);
        if (!report || !active()) return;
        const next = { sent: 0, received: 0, lost: 0, jitter: 0 };
        report.forEach((item) => {
          if (item.type === "outbound-rtp" && item.kind === "audio")
            next.sent += item.packetsSent || 0;
          if (item.type === "inbound-rtp" && item.kind === "audio") {
            next.received += item.packetsReceived || 0;
            next.lost += item.packetsLost || 0;
            next.jitter = (item.jitter || 0) * 1000;
          }
        });
        setStats(next);
      }, 1000);
    } catch (cause) {
      if (!active()) return;
      stop();
      setError(
        cause instanceof Error ? cause.message : "Could not start audio.",
      );
    }
  }

  return (
    <section className="panel media-test">
      <div className="section-label">
        SELF-HOSTED AUDIO LAB <span className="tag">Live WebRTC</span>
      </div>
      <h3>
        {mode === "interpret"
          ? "Speak. Pause. Hear each other."
          : "Hear your voice make the round trip."}
      </h3>
      <p>
        {mode === "interpret"
          ? "Speech is recognized and translated on this machine. Pause briefly between phrases. Your partner hears the translation using an installed local voice. Use headphones."
          : "Your microphone goes to our Python server and returns to you. This test does not translate or send audio to your partner. Use headphones."}
      </p>
      <label className="field-label">
        Audio mode{" "}
        <select
          aria-label="Audio mode"
          value={mode}
          disabled={state !== "idle"}
          onChange={(e) => setMode(e.target.value as "loopback" | "interpret")}
        >
          <option value="interpret">Local Hindi–English interpretation</option>
          <option value="loopback">Microphone round-trip test</option>
        </select>
      </label>
      <div className="media-actions">
        <button
          className="primary"
          disabled={
            !connected ||
            state !== "idle" ||
            (mode === "interpret" && !partnerConnected)
          }
          onClick={start}
        >
          <Mic size={15} />{" "}
          {mode === "interpret"
            ? "Start local interpretation"
            : "Start microphone test"}
        </button>
        <button
          className="secondary"
          disabled={state === "idle"}
          onClick={stop}
        >
          <Square size={13} /> Stop
        </button>
        <span role="status">{state}</span>
      </div>
      <audio
        ref={audio}
        controls={mode === "loopback"}
        aria-label="Returned microphone audio"
      />
      <div className="media-stats">
        <span>
          Packets sent <strong>{stats.sent}</strong>
        </span>
        <span>
          Packets returned <strong>{stats.received}</strong>
        </span>
        <span>
          Packets lost <strong>{stats.lost}</strong>
        </span>
        <span>
          Receive jitter <strong>{stats.jitter.toFixed(1)} ms</strong>
        </span>
      </div>
      <small>
        Phrase-based processing · No microphone audio saved · Automatically
        stops after two minutes
      </small>
      {mode === "interpret" && (
        <p>
          Experimental translations: verify the captions. Allow several seconds
          per phrase.
        </p>
      )}
      {mode === "interpret" && !partnerConnected && (
        <p>Connect your partner and enable their audio before starting.</p>
      )}
      {notice && (
        <p className="error" role="alert">
          {notice}
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
