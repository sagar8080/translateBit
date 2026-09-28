# Verification

Initial implementation: 2026-09-19.

This file records checks of the current milestone. Live speech/provider and clinical evidence must be tracked separately from scripted behavior.

## Passed

- 15 backend tests: queue ordering, preservation of prior turns, active provider cancellation, listener-specific stop/flush, backpressure, playback authorization, disconnect handling, provider failure isolation, playback timeout, secret exclusion, room admission, credential isolation, duplicate connections, origin restrictions, and signed LiveKit grants.
- 3 frontend tests: listener-only playback selection, exclusion of terminal/already-attempted segments, ordering, and stale snapshot rejection.
- TypeScript checking and Vite production build.
- Dependency audit: zero reported npm vulnerabilities, including development dependencies, at the time of this check.
- Frontend formatting check.
- Compiled frontend and its bundled asset served through the FastAPI static mount, alongside the health API.

## Real browser pass

Using Playwright CLI with a headed browser on macOS:

1. Created a Hindi room and used the invite link to join as English in a second tab.
2. Enabled browser audio in both tabs. Hindi → English and English → Hindi samples reached `completed` based on the browser speech callbacks; both views displayed the same source and translated captions.
3. Interrupted an incoming phrase after playback started; the segment remained `interrupted`.
4. Reconnected a participant; segment counts and terminal states were preserved without replaying completed segments.
5. Toggled browser offline mode for five seconds, then restored it; both participants returned/remained connected and terminal segments were unchanged. This is a browser control-path smoke, **not** a WebRTC network-loss test or a measured recovery-time result.
6. Checked the 390 px layout: document width was 390 px with no horizontal overflow. Desktop layouts were also visually inspected.

Local artifacts (ignored by Git): `output/playwright/lobby.png`, `output/playwright/workspace-verified.png`, and `output/playwright/mobile.png`.

## Not verified or not implemented

- LiveKit cloud connectivity, microphone capture, streaming ASR, actual model translation, provider TTS, VAD, or automatic interruption.
- Semantic fidelity: current phrases are authored fixtures and still need independent bilingual review.
- Audible intelligibility: browser callbacks were observed, but no independent listener assessment was performed.
- Speech-to-speech latency, packet loss, jitter, media recovery, load, or a 20-minute live call.
- Docker image execution: Docker is not installed in this environment. The equivalent compiled-frontend/static-serving path was checked locally.
- Remote CI execution: workflow is authored; local constituent checks passed.

The Python test runner emits two upstream deprecation warnings from Starlette's test-client/httpx compatibility and its AnyIO alias. They did not fail tests.

## Self-hosted media milestone — 2026-09-19

The earlier LiveKit token checks describe the previous milestone. That integration and its dependencies have now been removed.

- 18 backend tests and 3 frontend tests pass; TypeScript and production build pass.
- A real aiortc-to-aiortc test sends a generated tone through the service and verifies non-silent returned audio, frame reception, and peer closure. It uses no STUN/TURN server.
- Tests verify that stale stop requests cannot close a newer session, stopped attempts cannot be recreated by late offers, and malformed offers do not leak connections.
- In a headed browser, a synthetic Web Audio stream substituted for microphone capture traversed the browser → Python → browser WebRTC path. Received-packet counters increased. This verifies browser media transport, not physical microphone permission or human assessment of audio quality.
- The browser Stop control ended capture tracks and detached the returned stream. A simulated permission denial returned the interface to idle with an explicit error.
- The first browser attempt was interrupted by development hot reload during negotiation; a stable rerun connected successfully. Live development edits should not be made during manual audio assessment.
- UI fonts no longer call an external font service, and scripted TTS selects only browser voices flagged as local.

Physical microphone audio, other browsers, internet/NAT traversal, Docker UDP networking, and local model inference remain unverified. Reconnection of this audio test is explicit via Stop/Start; it does not yet provide automatic ICE restart. Local ASR, translation, and local neural TTS are the next milestone.

## Local interpretation milestone — 2026-09-19

- 25 backend tests, 3 frontend tests, and the production build pass. New coverage includes phrase endpointing and bounds, silence/noise rejection, local result routing, cancelled recognition, missing model detection, and silent return audio while retaining speech input.
- Pinned Whisper turbo and M2M100 models installed locally; four offline synthetic speech cases evaluated. Raw results are in `local-model-evaluation.json`.
- Headed Chromium, two participants: synthetic English and Hindi recordings injected into a continuous Web Audio microphone substitute **after WebRTC connected**. Both traversed the real media service and local models, displayed source/translated captions, and reached completed through the intended listener browser playback callbacks. Local processing was 8265 ms English-to-Hindi and 6963 ms Hindi-to-English. Stop returned capture to idle.
- The first harness attempt began its finite audio source before media negotiation and produced no phrase; the continuous-source, post-connection rerun passed. No application success is inferred from that failed attempt.
- Screenshot: `output/playwright/local-interpretation.png`. No physical microphone permission, independent listening assessment, or cross-network claim is made.
- **Quality gate remains open:** the Hindi headache phrase lost its specific symptom in translation. The 1.5-second target is not met; processing times exclude full listener latency. See `local-inference.md`.

This section supersedes earlier statements that local recognition and translation are unimplemented. Portable server-side neural TTS, automatic interruption, human-speaker validation, and deployment/network certification remain pending.
