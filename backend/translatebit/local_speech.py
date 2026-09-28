"""Local phrase recognition and translation. Runtime never downloads models."""
import asyncio
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import time

import av
import numpy as np

MODEL_ROOT = Path(os.getenv("MODEL_DIR", Path(__file__).resolve().parents[2] / "models"))


class LocalEngine:
    def __init__(self, root=MODEL_ROOT):
        self.root = Path(root)
        self.whisper = None
        self.translator = None
        self.tokenizer = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="local-inference")
        self.pending = set()

    def available(self):
        return (self.root / "whisper-turbo/model.bin").exists() and (self.root / "m2m100/model.bin").exists()

    def process_sync(self, audio, language):
        from faster_whisper import WhisperModel
        import ctranslate2
        import sentencepiece

        if not self.available():
            raise RuntimeError("Local models are missing. Run the model setup script.")
        start = time.monotonic()
        if self.whisper is None:
            self.whisper = WhisperModel(str(self.root / "whisper-turbo"), device="cpu",
                                        compute_type="int8", cpu_threads=4, local_files_only=True)
        chunks, _ = self.whisper.transcribe(audio, language=language, beam_size=3,
            condition_on_previous_text=False, vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400})
        text = " ".join(s.text.strip() for s in chunks if s.no_speech_prob < 0.6 and s.avg_logprob > -1).strip()
        asr_ms = round((time.monotonic() - start) * 1000)
        if not text:
            raise ValueError("No clear speech was recognized. Please repeat the phrase.")
        start = time.monotonic()
        if self.translator is None:
            self.tokenizer = sentencepiece.SentencePieceProcessor(model_file=str(self.root / "m2m100/sentencepiece.bpe.model"))
            self.translator = ctranslate2.Translator(str(self.root / "m2m100"), device="cpu", compute_type="int8", inter_threads=1, intra_threads=4)
        target = "hi" if language == "en" else "en"
        tokens = [f"__{language}__", *self.tokenizer.encode(text, out_type=str), "</s>"]
        output = self.translator.translate_batch([tokens], target_prefix=[[f"__{target}__"]],
                    beam_size=4, max_decoding_length=256)[0]
        translated = self.tokenizer.decode(output.hypotheses[0][1:]).strip()
        if not translated:
            raise ValueError("Local translation was empty. Please repeat the phrase.")
        return {"source": text, "translation": translated, "asr_ms": asr_ms,
                "translation_ms": round((time.monotonic() - start) * 1000)}

    async def process(self, audio, language):
        if len(self.pending) >= 4:
            raise ValueError("Local inference is busy. Pause and repeat your phrase.")
        future = asyncio.get_running_loop().run_in_executor(self.executor, self.process_sync, audio, language)
        self.pending.add(future)
        def complete(done):
            self.pending.discard(done)
            if not done.cancelled():
                done.exception()  # Consume errors even when the caller has stopped.
        future.add_done_callback(complete)
        # Cancelling a UI turn must not pretend a native inference thread has stopped.
        return await asyncio.shield(future)


class PhraseBuffer:
    """Energy endpointing with pre-roll, minimum speech, and bounded phrases.

    Final recognition also runs Silero VAD. This is phrase streaming, not partial-token ASR.
    """
    def __init__(self):
        self.pre = deque(maxlen=10)
        self.parts = []
        self.samples = self.speech = self.silence = 0

    def feed(self, samples):
        loud = float(np.sqrt(np.mean(samples * samples))) >= 0.012
        if not self.parts:
            if not loud:
                self.pre.append(samples.copy())
                return None
            self.parts = list(self.pre)
            self.samples = sum(len(p) for p in self.parts)
            self.pre.clear()
        self.parts.append(samples.copy())
        self.samples += len(samples)
        self.speech += len(samples) if loud else 0
        self.silence = 0 if loud else self.silence + len(samples)
        if self.silence < 12800 and self.samples < 128000:
            return None
        result = np.concatenate(self.parts) if self.speech >= 4800 else None
        self.parts = []
        self.samples = self.speech = self.silence = 0
        return result


class SpeechInput:
    def __init__(self, room, participant, engine):
        self.room, self.participant, self.engine = room, participant, engine
        self.resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        self.buffer = PhraseBuffer()
        self.active = True
        self.segment_ids = set()
        self.tasks = set()

    def feed(self, frame):
        if not self.active:
            return
        for converted in self.resampler.resample(frame):
            samples = converted.to_ndarray().flatten().astype(np.float32) / 32768.0
            phrase = self.buffer.feed(samples)
            if phrase is not None:
                task = asyncio.create_task(self.submit(phrase))
                self.tasks.add(task)
                task.add_done_callback(self.tasks.discard)

    async def submit(self, phrase):
        if not self.active:
            return
        try:
            segment = await self.room.submit_audio(self.participant, phrase, self.engine)
            self.segment_ids.add(segment.id)
            if not self.active:
                self.cancel_uncommitted()
        except ValueError as error:
            self.room.notices[self.participant.id] = str(error)
            self.room.event("speech_rejected", participant_id=self.participant.id)
            await self.room.notify()

    def cancel_uncommitted(self):
        for segment in self.room.segments:
            if segment.id in self.segment_ids and segment.status in {"committed", "recognizing"}:
                segment.status = "cancelled"
                self.room.finished[segment.id].set()
                self.room.event("recognition_cancelled", segment_id=segment.id)

    def close(self):
        self.active = False
        self.buffer = PhraseBuffer()
        self.cancel_uncommitted()
