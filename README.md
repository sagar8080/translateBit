# TranslateBit

A two-person Hindi–English interpretation workbench. The app includes **local microphone interpretation**, a scripted conversation demo, and a self-hosted WebRTC microphone round-trip. No paid APIs or managed media services are used.

## Stack

React and TypeScript provide the interface; FastAPI and WebSockets manage rooms and captions; aiortc handles self-hosted WebRTC audio. Whisper Turbo recognizes speech, M2M100 translates it, and installed local browser voices provide playback. Application orchestration is ours; codecs, model runtimes, and pretrained models use open-source components.

## What works today

- Create a room and invite a second participant using the other language.
- Interpret actual microphone speech in either direction using local models.
- Separately exchange six authored sample phrases with clearly labeled prewritten translations.
- Hear translations using the listener's available browser speech voices.
- Stop incoming playback, flush pending work, and see cancelled/interrupted states.
- Reconnect with a room snapshot; completed speech is not replayed.
- Inspect session events, completed playback, failures, and reconnect counts.
- Send microphone audio through our Python WebRTC service and receive your own audio back.
- Inspect actual sent/received packet counts, packet loss, and receive jitter.
- Stop the microphone and close media resources explicitly, on room disconnection, or after two minutes.

**Live local interpretation is now implemented:** microphone audio is recognized with local Whisper and translated with local M2M100, then spoken using the listener's local browser voice. See [local inference setup and measured limitations](docs/local-inference.md). Model accuracy and latency remain experimental; one Hindi terminology failure is documented.

**Still pending:** portable server-side neural TTS, automatic speech interruption, human-speaker quality certification, true speech-to-speech latency measurement, and internet media recovery.

## Run locally

Requirements: Node.js 22+, Python 3.11+, and [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/sagar8080/translateBit.git
cd translateBit
npm ci
uv sync --project backend --locked
# Required for microphone interpretation; optional for scripted samples:
uv run --project backend python scripts/setup_models.py
npm start
```

Open http://127.0.0.1:5173. The API listens on port 8000. Both services bind to loopback. Keep this private development build local.

1. Create a room as the Hindi speaker.
2. Click **Open second participant**, then join as the English speaker. The new tab must have separate session storage; use the supplied link or a separate browser rather than duplicating a connected tab.
3. Enable audio in the receiving tab. In the speaking tab, select **Local Hindi–English interpretation**, click **Start local interpretation**, allow microphone access, and speak a short phrase followed by a pause. You can also use a prewritten sample button.
4. Switch directions. Hindi audio requires an installed Hindi browser voice.
5. Stop incoming playback and inspect the event log. Use **Reconnect this participant** to test session reconnection.

Audio availability depends on the browser and operating system. If a voice is missing or speech is blocked, the turn is marked failed and captions remain available. No replacement audio or fabricated success metric is supplied. Background tabs and operating-system speech behavior can affect playback; use two windows for manual audio checks.

Room credentials are kept in sessionStorage and sent in the first WebSocket frame. The invite code admits at most one participant per language. Treat invite links as private. Rooms expire after two hours, hold at most 200 segments, and disappear when the API restarts. There are no accounts, durable history, public-service rate limits, or multi-worker coordination. Run **one API worker**.

## Checks

```sh
npm test
npm run build
uv run --project backend pytest backend/tests -q
```

Tests cover ordering, cancellation during provider work, listener-specific queue flushing, backlog limits, reconnect behavior, provider/playback failure, credential isolation, duplicate connections, allowed origins, and real WebRTC audio return/teardown. CI runs frontend tests/build and backend tests.

## Self-hosted audio modes

For live interpretation, follow [these instructions](docs/local-inference.md). For a transport-only test, select **Microphone round-trip test**, use headphones, and click **Start microphone test**. Allow microphone access. Your voice travels to the Python service and comes back to your own browser, not your partner. The counters come from WebRTC statistics; they are not translation latency. Click **Stop** to release the microphone. The test ends automatically after two minutes; start again to reconnect.

WebRTC needs no configuration on localhost. Local interpretation requires the model setup script above. Model files are downloaded separately and are not included in this repository. Both browser and server use `iceServers: []`, so they make no default external STUN/TURN requests. For internet use, run your own TURN relay and configure `ICE_SERVERS_JSON` in `.env`, then restart. For example, use your own host in a JSON array containing `urls`, `username`, and `credential`. This is private-lab configuration; do not share long-lived TURN credentials with untrusted users. Remote microphone access requires HTTPS. A self-hosted TURN deployment and cross-network verification are still pending.

Both interpretation and the scripted demo permit only browser voices marked `localService`; remote browser voices are excluded. Web fonts have also been removed, so the UI does not fetch third-party fonts.

## Container

```sh
docker build -t translatebit .
docker run --rm -p 127.0.0.1:8000:8000 translatebit
```

Then open http://127.0.0.1:8000 for the scripted interface. The Docker recipe publishes HTTP only; WebRTC media needs reachable UDP candidates/relay configuration and is not yet validated in Docker. The API serves the compiled frontend in the container. Set `ALLOWED_ORIGINS` to the exact browser origin if you change the address. Docker validation status is recorded in `docs/verification.md`.

See [architecture](docs/architecture.md), [roadmap](docs/roadmap.md), and [verification](docs/verification.md). Use synthetic conversations only. This is not a clinically validated interpreter.
