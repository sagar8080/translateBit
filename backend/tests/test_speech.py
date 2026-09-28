import asyncio

import av
import numpy as np
import pytest

from backend.translatebit.domain import Room
from backend.translatebit.local_speech import LocalEngine, PhraseBuffer, SpeechInput
from backend.translatebit.media import EchoTrack


def test_silence_never_creates_a_phrase():
    buffer = PhraseBuffer()
    for _ in range(1000):
        assert buffer.feed(np.zeros(320, dtype=np.float32)) is None
    assert not buffer.parts
    assert len(buffer.pre) <= 10


def test_phrase_commits_after_silence_and_is_bounded():
    buffer = PhraseBuffer()
    loud = np.full(320, .1, dtype=np.float32)
    for _ in range(25):
        assert buffer.feed(loud) is None
    for _ in range(39):
        assert buffer.feed(np.zeros(320, dtype=np.float32)) is None
    phrase = buffer.feed(np.zeros(320, dtype=np.float32))
    assert phrase is not None
    assert len(phrase) == 65 * 320
    assert not buffer.parts
    for _ in range(399):
        assert buffer.feed(loud) is None
    assert len(buffer.feed(loud)) == 128000


def test_short_noise_is_rejected():
    buffer = PhraseBuffer()
    buffer.feed(np.full(320, .5, dtype=np.float32))
    for _ in range(40):
        assert buffer.feed(np.zeros(320, dtype=np.float32)) is None


async def wait_for(predicate):
    async with asyncio.timeout(2):
        while not predicate():
            await asyncio.sleep(.001)


async def test_local_segments_use_real_results_and_ordered_playback():
    class Engine:
        async def process(self, audio, language):
            return {"source": "नमस्ते", "translation": "Hello", "asr_ms": 100, "translation_ms": 30}
    room = Room("test")
    source, listener = room.add_participant("hi"), room.add_participant("en")
    await room.connect(source)
    await room.connect(listener)
    try:
        segment = await room.submit_audio(source, np.zeros(16000), Engine())
        await wait_for(lambda: segment.status == "queued")
        assert segment.origin == "local"
        assert segment.source == "नमस्ते"
        assert segment.translation == "Hello"
        assert segment.asr_ms == 100
        await room.playback(listener, segment.id, "completed")
        assert segment.status == "completed"
    finally:
        await room.close()


async def test_stop_capture_rejects_late_recognition():
    release = asyncio.Event()
    class SlowEngine:
        async def process(self, audio, language):
            await release.wait()
            return {"source": "late", "translation": "late", "asr_ms": 1, "translation_ms": 1}
    room = Room("test")
    source, listener = room.add_participant("hi"), room.add_participant("en")
    await room.connect(source)
    await room.connect(listener)
    stream = SpeechInput(room, source, SlowEngine())
    try:
        await stream.submit(np.zeros(16000))
        await wait_for(lambda: room.segments[0].status == "recognizing")
        stream.close()
        release.set()
        await wait_for(lambda: room.tasks[source.id].done())
        assert room.segments[0].status == "cancelled"
        assert room.segments[0].translation == ""
    finally:
        await room.close()


def test_missing_models_do_not_trigger_download(tmp_path):
    assert not LocalEngine(tmp_path).available()


async def test_interpretation_consumes_input_but_returns_silence():
    class Source:
        stopped = False

        async def recv(self):
            frame = av.AudioFrame.from_ndarray(
                np.full((1, 960), 4000, dtype=np.int16), format="s16", layout="mono")
            frame.sample_rate = 48000
            frame.pts = 960
            return frame

        def stop(self):
            self.stopped = True

    class Sink:
        closed = False

        def feed(self, frame):
            self.samples = frame.to_ndarray().copy()

        def close(self):
            self.closed = True

    source, sink = Source(), Sink()
    track = EchoTrack(source, sink)
    output = await track.recv()
    assert np.all(sink.samples == 4000)
    assert not np.any(output.to_ndarray())
    assert output.pts == 960
    track.stop()
    assert source.stopped and sink.closed
