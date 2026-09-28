# Local speech interpretation milestone

The live mode now runs browser microphone → our WebRTC service → phrase boundary detection → local Whisper recognition → local M2M100 translation → shared captions → the listener's installed local browser voice. Both Hindi-to-English and English-to-Hindi use the same pipeline.

## Run

Model weights are not included in Git. After installing project dependencies, download and prepare them in this checkout:

```sh
uv run --project backend python scripts/setup_models.py
npm start
```

The setup script downloads pinned model revisions once and converts M2M100 to int8 using an isolated conversion environment. It needs `uv`, internet access, and several GB of free disk space. Runtime inference uses local paths only; no paid service or account is required. Active model files occupy about 2 GB. Model identities and checksums are recorded in `models/manifest.json`; the current baseline is also in `docs/models.json`.

1. Create a fresh room and join its invite link in a second browser/window with the other language.
2. Enable audio in the receiving participant's view.
3. Select **Local Hindi–English interpretation** and click **Start local interpretation** in the speaking participant's view.
4. Use headphones. Speak a short phrase and pause for at least a second. Source captions, translated captions, and local processing time appear in the conversation.
5. The other participant can enable their own microphone to use the reverse direction. Both lanes remain ordered.
6. Stop ends capture and cancels unfinished recognition. Already committed translations remain eligible for playback. The separate **Stop incoming playback** control cancels incoming queued/playing work.

The microphone session remains limited to two minutes. Start again for a fresh session. Browser voices must be installed locally for the listener's language. This milestone reuses the OS/browser voice adapter; it does **not** implement a portable, server-side neural TTS model.

## Runtime behavior

- Capture is streamed over WebRTC; recognition operates on committed phrases, not incremental word hypotheses.
- Audio is resampled to 16 kHz mono. Initial endpointing uses energy, 200 ms pre-roll, at least 300 ms of speech, 800 ms of silence, and a maximum phrase length of eight seconds. Recognition additionally runs bundled Silero VAD.
- The 8-second cutoff is a memory/latency bound, not a guarantee of a linguistically complete sentence. Long sentences can be split awkwardly. Quiet speech/noisy environments need further tuning.
- One bounded native-inference worker protects the event loop. Four pending jobs are allowed globally; each speaker also has a four-segment bound. Overload is explicit, with a request to pause/repeat.
- Stop invalidates results. A native inference call already running finishes in the background; cancellation does not forcibly terminate native model code. Its eventual result cannot revive a cancelled segment.
- Raw microphone audio remains in memory and is not recorded. Source/translated text remains in the existing ephemeral room state until expiration or server restart.
- Output WebRTC frames in interpretation mode are silent so the speaker does not hear their microphone echoed. Translated audio is synthesized on the listener's device from the committed translation, not routed as a server TTS track.

## Evidence and limits

See `local-model-evaluation.json` for four synthetic-voice cases and measured recognition/translation times. The evaluation uses macOS Samantha and Lekha voices, not independent human speakers, and sets offline model loading. There is no independent bilingual review yet.

The selected CPU baseline took approximately 6–8 seconds for recognition plus 0.2–0.7 seconds for translation in that run. These are inference timings, not listener speech-to-speech latency. Cold model loading is included in the first engine call. The original median 1.5-second target is **not met**.

Known semantic failure: Hindi “मुझे तीन दिनों से सिरदर्द है” was recognized with an incorrect spelling of “headache”; the translation became “I have been sick for three days.” Negation was preserved, but the specific symptom was lost. The earlier small-Whisper/Argos trial was worse and was not selected. Do not treat this prototype as a reliable medical interpreter.

The implemented boundary is functional local speech-to-translated-speech plumbing. Remaining work: human-speaker evaluation, terminology fidelity, model acceleration, lower latency, better endpointing, automatic listener interruptions, and a portable local TTS engine.

Model references: [Whisper turbo conversion](https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo), [M2M100](https://huggingface.co/facebook/m2m100_418M), [CTranslate2 translation integration](https://opennmt.net/CTranslate2/guides/transformers.html#m2m-100).
