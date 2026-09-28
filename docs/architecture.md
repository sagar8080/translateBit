# Architecture and invariants

## Current milestone

Live path: browser microphone → self-hosted WebRTC → phrase detection → local Whisper → local M2M100 → per-speaker ordered playback → listener local browser voice → playback acknowledgements. Authored sample buttons retain the separate demo fixture path.

WebSocket carries **control events and captions**, not microphone audio. Self-hosted aiortc/WebRTC carries microphone audio separately from control events. The server owns segment state; the client reports browser speech lifecycle events. A browser `end` event is evidence of browser playback ending, not proof that a human heard it.

The backend issues full room snapshots with monotonic revisions. A reconnect receives current state instead of replaying past events. Participant credentials are excluded from snapshots. Two participants occupy fixed language slots for a room's lifetime; disconnecting does not free a slot and permit identity takeover.

## Segment lifecycle

`committed → recognizing (local) / translating (sample) → queued → playing → completed`

Terminal alternatives: `cancelled`, `interrupted`, `failed`.

- Each speaker has one serial lane. A new segment never supersedes an earlier one implicitly.
- Up to four nonterminal segments may exist per speaker. Reaching this bound rejects further input with a visible error.
- The next segment waits for listener completion, failure, stop, or a 45-second timeout.
- Stop affects incoming segments only: playing becomes interrupted; pending becomes cancelled.
- Stop sets cancellation events, cancels active provider tasks, and rejects late results.
- The listener alone can acknowledge its incoming speech. Late acknowledgements cannot revive terminal segments.
- If a listener disconnects during playback, that segment becomes interrupted and is never replayed automatically.
- A queued segment that has not begun may remain pending across reconnection until its timeout. Browser playback is opt-in each page load.
- Failed translation has no fabricated translation text. Failed audio keeps translated captions.

## State and limits

One process owns in-memory rooms, participant credentials, bounded event history, queues, and task cancellation. Maximum 100 rooms, 200 segments per room, 100 retained events per room, and two-hour room lifetime. Process restart requires a new room; the UI reports expiration/unavailability.

The demo provider intentionally waits approximately 650 ms. This is displayed as **simulated processing**. It is not ASR, translation-model, speech-synthesis, or speech-to-speech latency.

## Planned live architecture

Browser microphone → our WebRTC service → Python worker → VAD / streaming ASR → committed phrase → contextual translation → streaming TTS → destination-specific WebRTC output track → listener browser.

Keep the processing state machine provider-independent. Add segment revisions, media generations, output-buffer cancellation, and received-playback evidence when integrating the media path. Subscribe to identified microphone tracks only. Route translated tracks to their intended listener and exclude all synthesized tracks from recognition.

Before enabling automatic interruptions, test source continuation separately from listener interruption. Before reporting speech-to-speech latency, define timestamp domains and measure at the receiving browser, with documented clock alignment.

## Deliberate limits

Live microphone interpretation and loopback are implemented. Four synthetic model cases are recorded in local-model-evaluation.json. Human evaluation, server TTS audio routing, durable storage, automatic interruptions, and production access controls remain pending. WebSocket reconnects are not evidence of WebRTC recovery. Browser speech synthesis uses installed local voices; portable server-side neural TTS remains pending.

## Self-hosted media implementation

Each authenticated participant owns one aiortc peer connection. The browser sends a complete audio-only SDP offer via HTTP; our service returns an answer. No external signaling service or default ICE server is used. A per-participant lock serializes negotiation, attempt IDs scope teardown, and a bounded tombstone history rejects stopped attempts that arrive late. A stale stop cannot close a newer attempt.

In loopback mode the server returns the received audio frames with their timestamps. Interpretation mode feeds frames to local inference and returns silence, preventing microphone echo. Captions reach the intended listener through room snapshots and are spoken by their local voice. Neither mode writes microphone audio to disk or invokes a paid API. Capture stops on user request, page departure, control disconnect, failure, or the two-minute test deadline. Reconnection is explicit through a new test attempt. Network relay configuration accepts a self-hosted TURN server, but no relay deployment has been certified.

## Local inference

See [local inference](local-inference.md) for endpointing, model pins, bounded native execution, cancellation behavior, setup, and known quality/latency failures. A stopped native call may finish internally; its discarded result cannot revive a terminal segment.
