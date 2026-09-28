# Build roadmap

## Milestone 1 — Room and deterministic state foundation

- [x] React/TypeScript conversation workspace.
- [x] Python room creation and two-language admission.
- [x] Credential-bound WebSocket snapshots and reconnect.
- [x] Scripted phrase provider with separate ordered speaker lanes.
- [x] Browser speech adapter, explicit failure, and manual interruption.
- [x] Queue limits, provider cancellation, late-result rejection.
- [x] Event log and correctly labeled demo counters.
- [x] Replaced hosted-media token integration with our authenticated WebRTC signaling.
- [x] Regression tests and CI definition.

## Milestone 2 — Self-hosted media and local model feasibility

- [ ] Expand authored fixtures to a versioned corpus of at least 100 utterances and multi-turn dialogues.
- [ ] Obtain independent bilingual review; current samples are unreviewed authored fixtures.
- [ ] Benchmark Hindi, English, and code-switched recognition, translation fidelity, TTS intelligibility, latency, and usage cost.
- [x] Pin a local recognition/translation baseline and record a small synthetic evaluation, including failures.
- [x] Connect browser microphone to Python and return audio through our aiortc service.
- [x] Local-only browser speech and no external font downloads.
- [ ] Deploy self-hosted TURN and verify across networks.
- [x] Connect phrase-based local recognition and translation to the shared playback queue in both directions.

## Milestone 3 — Bidirectional live interpretation

- [x] Deliver translations to the intended listener using local browser speech; microphone return is silent in interpretation mode.
- [ ] Replace browser speech with portable local neural TTS output tracks.
- [ ] Committed phrase boundaries and bounded context.
- [ ] Small glossary with negation/quantity/correction regression cases.
- [ ] Live FIFO playback with cancellation across provider and media buffers.
- [ ] Listener interruption detection; source continuation preserves queued content.

## Milestone 4 — Recovery and measured reliability

- [ ] Five-second media network loss and reconnect tests.
- [ ] Worker restart and local inference timeout failure states.
- [ ] OpenTelemetry traces and true listener playback measurements.
- [ ] Three-room isolation test and 20-minute live conversation smoke.
- [ ] Measured latency targets and bilingual evaluation report.

The original target of median ≤1.5 s and p95 ≤3 s from phrase end to first listener audio remains a hypothesis until the real media path is measured. A passing scripted demo does not establish provider quality or clinical suitability.
