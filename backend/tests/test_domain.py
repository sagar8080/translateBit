import asyncio

import pytest

from backend.translatebit.domain import Room


class ImmediateProvider:
    async def translate(self, sample):
        return sample["translation"]


class GateProvider:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = False

    async def translate(self, sample):
        self.started.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return sample["translation"]


async def setup_room(provider=None, timeout=45):
    room = Room("TESTROOM", provider or ImmediateProvider(), timeout)
    hindi = room.add_participant("hi")
    english = room.add_participant("en")
    await room.connect(hindi)
    await room.connect(english)
    return room, hindi, english


async def until(predicate):
    async with asyncio.timeout(1):
        while not predicate():
            await asyncio.sleep(0.001)


async def test_new_segments_preserve_earlier_turns_and_order():
    room, hindi, english = await setup_room()
    try:
        first = await room.submit(hindi, "hi-headache")
        second = await room.submit(hindi, "hi-negation")
        await until(lambda: first.status == "queued")
        assert second.status == "committed"
        await room.playback(english, first.id, "started")
        await room.playback(english, first.id, "completed")
        await until(lambda: second.status == "queued")
        assert first.status == "completed"
    finally:
        await room.close()


async def test_stop_cancels_provider_and_discards_late_output():
    provider = GateProvider()
    room, hindi, english = await setup_room(provider)
    try:
        segment = await room.submit(hindi, "hi-headache")
        await provider.started.wait()
        await room.stop(english)
        await until(lambda: room.tasks[hindi.id].done())
        assert provider.cancelled
        provider.release.set()
        assert segment.status == "cancelled"
        assert segment.translation == ""
    finally:
        await room.close()


async def test_stop_interrupts_playing_and_flushes_queue_only_for_listener():
    room, hindi, english = await setup_room()
    try:
        first = await room.submit(hindi, "hi-headache")
        queued = await room.submit(hindi, "hi-negation")
        reverse = await room.submit(english, "en-medication")
        await until(lambda: first.status == reverse.status == "queued")
        await room.playback(english, first.id, "started")
        await room.stop(english)
        assert first.status == "interrupted"
        assert queued.status == "cancelled"
        assert reverse.status == "queued"
        await room.playback(english, first.id, "completed")
        assert first.status == "interrupted"
    finally:
        await room.close()


async def test_queue_backpressure_and_language_permissions():
    room, hindi, english = await setup_room()
    try:
        with pytest.raises(ValueError, match="own language"):
            await room.submit(hindi, "en-medication")
        for _ in range(4):
            await room.submit(hindi, "hi-headache")
        with pytest.raises(ValueError, match="Please pause"):
            await room.submit(hindi, "hi-headache")
        with pytest.raises(ValueError, match="intended listener"):
            await room.playback(hindi, room.segments[0].id, "completed")
    finally:
        await room.close()


async def test_disconnect_does_not_replay_partially_heard_audio():
    room, hindi, english = await setup_room()
    try:
        segment = await room.submit(hindi, "hi-headache")
        await until(lambda: segment.status == "queued")
        await room.playback(english, segment.id, "started")
        await room.disconnect(english)
        await room.connect(english)
        assert segment.status == "interrupted"
        assert english.reconnects == 1
        with pytest.raises(ValueError, match="Both participants"):
            await room.disconnect(english)
            await room.submit(hindi, "hi-negation")
    finally:
        await room.close()


async def test_playback_timeout_does_not_block_lane_forever():
    room, hindi, english = await setup_room(timeout=0.01)
    try:
        first = await room.submit(hindi, "hi-headache")
        second = await room.submit(hindi, "hi-negation")
        await until(lambda: first.status == "failed" and second.status in {"queued", "failed"})
        assert first.error
    finally:
        await room.close()


async def test_provider_failure_is_explicit_and_other_lane_survives():
    class SelectivelyBrokenProvider:
        async def translate(self, sample):
            if sample["language"] == "hi":
                raise RuntimeError("internal secret should not leak")
            return sample["translation"]

    room, hindi, english = await setup_room(SelectivelyBrokenProvider())
    try:
        first = await room.submit(hindi, "hi-headache")
        reverse = await room.submit(english, "en-medication")
        await until(lambda: first.status == "failed" and reverse.status == "queued")
        assert first.translation == ""
        assert "secret" not in first.error
    finally:
        await room.close()


async def test_room_snapshot_never_contains_credentials():
    room, hindi, english = await setup_room()
    assert hindi.token not in str(room.snapshot())
    assert english.token not in str(room.snapshot())
    assert room.authenticate(hindi.token) is hindi
    assert room.authenticate("wrong") is None
    with pytest.raises(ValueError, match="two participants"):
        room.add_participant("en")
    await room.close()
