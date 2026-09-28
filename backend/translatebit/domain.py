from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from .samples import SAMPLES

TERMINAL = {"completed", "cancelled", "interrupted", "failed"}


@dataclass
class Participant:
    id: str
    language: str
    token: str
    connected: bool = False
    reconnects: int = 0
    joined_once: bool = False


@dataclass
class Segment:
    id: str
    speaker_id: str
    language: str
    source: str
    translation: str = ""
    status: str = "committed"
    created_at: float = field(default_factory=time.time)
    processing_ms: int | None = None
    error: str | None = None
    origin: str = "scripted"
    asr_ms: int | None = None
    translation_ms: int | None = None

    def public(self):
        return vars(self).copy()


class DemoProvider:
    """Deterministic fixture provider. Delay is simulation, not model latency."""

    async def translate(self, sample: dict) -> str:
        await asyncio.sleep(0.65)
        return sample["translation"]


class Room:
    def __init__(self, code: str, provider=None, playback_timeout: float = 45):
        self.code = code
        self.provider = provider or DemoProvider()
        self.playback_timeout = playback_timeout
        self.created_at = time.time()
        self.participants: dict[str, Participant] = {}
        self.segments: list[Segment] = []
        self.events: list[dict] = []
        self.revision = 0
        self.notices = {}
        self.queues: dict[str, asyncio.Queue] = {}
        self.tasks: dict[str, asyncio.Task] = {}
        self.finished: dict[str, asyncio.Event] = {}
        self.notify: Callable[[], Awaitable[None]] = self._noop

    async def _noop(self):
        pass

    def add_participant(self, language: str) -> Participant:
        if language not in {"hi", "en"}:
            raise ValueError("Choose Hindi or English.")
        if len(self.participants) >= 2:
            raise ValueError("This room already has two participants.")
        if any(p.language == language for p in self.participants.values()):
            raise ValueError("That language is already taken. Join with the other language.")
        participant = Participant(secrets.token_urlsafe(9), language, secrets.token_urlsafe(32))
        self.participants[participant.id] = participant
        self.event("participant_joined", participant_id=participant.id)
        return participant

    def authenticate(self, token: str) -> Participant | None:
        return next((p for p in self.participants.values() if secrets.compare_digest(p.token, token)), None)

    def event(self, name: str, **data):
        self.revision += 1
        self.events.append({"name": name, "at": time.time(), **data})
        self.events = self.events[-100:]

    async def connect(self, participant: Participant):
        if participant.joined_once:
            participant.reconnects += 1
        participant.connected = True
        participant.joined_once = True
        self.event("participant_connected", participant_id=participant.id)
        await self.notify()

    async def disconnect(self, participant: Participant):
        participant.connected = False
        # Speech may already have reached the listener. Never replay it implicitly.
        for segment in self.segments:
            if segment.speaker_id != participant.id and segment.status == "playing":
                segment.status = "interrupted"
                self.finished[segment.id].set()
                self.event("playback_interrupted", segment_id=segment.id)
        self.event("participant_disconnected", participant_id=participant.id)
        await self.notify()

    async def submit(self, participant: Participant, sample_id: str) -> Segment:
        if len(self.participants) != 2 or not all(p.connected for p in self.participants.values()):
            raise ValueError("Both participants must be connected before sending a phrase.")
        sample = next((s for s in SAMPLES if s["id"] == sample_id and s["language"] == participant.language), None)
        if sample is None:
            raise ValueError("Choose a sample in your own language.")
        return await self._enqueue(participant, sample)

    async def submit_audio(self, participant, audio, engine):
        if len(self.participants) != 2 or not all(p.connected for p in self.participants.values()):
            raise ValueError("Both participants must be connected for live interpretation.")
        return await self._enqueue(participant, {"audio": audio, "engine": engine, "source": ""})

    async def _enqueue(self, participant, sample):
        if len(self.segments) >= 200:
            raise ValueError("This demo has reached 200 segments. Start a new room.")
        pending = [s for s in self.segments if s.speaker_id == participant.id and s.status not in TERMINAL]
        if len(pending) >= 4:
            raise ValueError("Please pause. Four phrases are already waiting for your listener.")
        segment = Segment(secrets.token_urlsafe(9), participant.id, participant.language, sample["source"])
        if "audio" in sample:
            segment.origin = "local"
        self.notices.pop(participant.id, None)
        self.segments.append(segment)
        self.finished[segment.id] = asyncio.Event()
        self.event("segment_committed", segment_id=segment.id)
        queue = self.queues.setdefault(participant.id, asyncio.Queue())
        queue.put_nowait((segment, sample))
        if participant.id not in self.tasks or self.tasks[participant.id].done():
            self.tasks[participant.id] = asyncio.create_task(self._run_lane(participant.id))
        await self.notify()
        return segment

    async def _run_lane(self, speaker_id: str):
        queue = self.queues[speaker_id]
        while not queue.empty():
            segment, sample = queue.get_nowait()
            try:
                if segment.status in TERMINAL:
                    continue
                live = "audio" in sample
                segment.status = "recognizing" if live else "translating"
                self.event("translation_started", segment_id=segment.id)
                await self.notify()
                start = time.monotonic()
                translation_task = asyncio.create_task(
                    sample["engine"].process(sample["audio"], segment.language) if live
                    else self.provider.translate(sample))
                cancelled = asyncio.create_task(self.finished[segment.id].wait())
                try:
                    done, _ = await asyncio.wait({translation_task, cancelled}, timeout=45 if live else 8, return_when=asyncio.FIRST_COMPLETED)
                    if segment.status in TERMINAL:
                        continue
                    if translation_task not in done:
                        raise TimeoutError("Translation timed out. Please repeat the phrase.")
                    result = translation_task.result()
                    if live:
                        segment.source = result["source"]
                        segment.translation = result["translation"]
                        segment.asr_ms = result["asr_ms"]
                        segment.translation_ms = result["translation_ms"]
                    else:
                        segment.translation = result
                finally:
                    for task in (translation_task, cancelled):
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(translation_task, cancelled, return_exceptions=True)
                segment.processing_ms = round((time.monotonic() - start) * 1000)
                segment.status = "queued"
                self.event("translation_ready", segment_id=segment.id)
                await self.notify()
                await asyncio.wait_for(self.finished[segment.id].wait(), self.playback_timeout)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                if segment.status not in TERMINAL:
                    segment.status = "failed"
                    segment.error = str(error) if isinstance(error, (TimeoutError, ValueError)) and str(error) else "Playback or provider failed. Please repeat the phrase."
                    self.event("segment_failed", segment_id=segment.id)
            finally:
                queue.task_done()
                await self.notify()

    async def playback(self, participant: Participant, segment_id: str, action: str):
        segment = next((s for s in self.segments if s.id == segment_id), None)
        if segment is None or segment.speaker_id == participant.id:
            raise ValueError("Only the intended listener can acknowledge playback.")
        if segment.status in TERMINAL:
            return
        if action == "started" and segment.status == "queued":
            segment.status = "playing"
        elif action in {"completed", "failed"} and segment.status in {"playing", "queued"}:
            segment.status = action
            if action == "failed":
                segment.error = "Browser speech playback was unavailable or failed. Captions are retained."
            self.finished[segment.id].set()
        else:
            raise ValueError("Invalid playback transition.")
        self.event("playback_" + action, segment_id=segment_id)
        await self.notify()

    async def stop(self, participant: Participant):
        for segment in self.segments:
            if segment.speaker_id != participant.id and segment.status not in TERMINAL:
                segment.status = "interrupted" if segment.status == "playing" else "cancelled"
                self.finished[segment.id].set()
                self.event("playback_" + segment.status, segment_id=segment.id)
        await self.notify()

    def snapshot(self):
        return {
            "code": self.code, "mode": "scripted_demo", "revision": self.revision,
            "participants": [{"id": p.id, "language": p.language, "connected": p.connected, "reconnects": p.reconnects} for p in self.participants.values()],
            "segments": [s.public() for s in self.segments], "events": self.events, "notices": self.notices,
        }

    async def close(self):
        for task in self.tasks.values():
            task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
