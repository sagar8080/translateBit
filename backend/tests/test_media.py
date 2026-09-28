import asyncio
import math
import struct

import pytest
from aiortc import AudioStreamTrack, RTCPeerConnection, RTCConfiguration, RTCSessionDescription

from backend.translatebit.media import MediaService


class Tone(AudioStreamTrack):
    async def recv(self):
        frame = await super().recv()
        frame.planes[0].update(struct.pack("<" + "h" * frame.samples, *[
            int(8000 * math.sin(2 * math.pi * 440 * (frame.pts + i) / frame.sample_rate))
            for i in range(frame.samples)
        ]))
        return frame


async def test_real_webrtc_returns_audio_and_closes_resources():
    service = MediaService()
    client = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    track_received = asyncio.get_running_loop().create_future()

    @client.on("track")
    def received(track):
        track_received.set_result(track)

    client.addTrack(Tone())
    try:
        await client.setLocalDescription(await client.createOffer())
        answer = await service.offer(("room", "speaker"), "attempt-one", client.localDescription.sdp)
        await client.setRemoteDescription(RTCSessionDescription(sdp=answer["sdp"], type=answer["type"]))
        async with asyncio.timeout(10):
            returned = await track_received
            frames = [await returned.recv() for _ in range(8)]
        assert any(any(bytes(frame.planes[0])) for frame in frames)
        assert service.sessions[("room", "speaker")].echo.frames >= 8
        peer = service.sessions[("room", "speaker")].peer
        await service.close(("room", "speaker"), "older-attempt")
        assert ("room", "speaker") in service.sessions
        await service.close(("room", "speaker"), "attempt-one")
        assert peer.connectionState == "closed"
        assert not service.sessions
    finally:
        await client.close()
        await service.close_all()


async def test_stopped_attempt_cannot_be_resurrected_by_late_offer():
    service = MediaService()
    await service.close(("room", "speaker"), "cancelled-attempt")
    with pytest.raises(ValueError, match="stopped"):
        await service.offer(("room", "speaker"), "cancelled-attempt", "invalid")
    assert not service.sessions


async def test_invalid_offer_does_not_leak_peer():
    service = MediaService()
    with pytest.raises(ValueError):
        await service.offer(("room", "speaker"), "invalid-attempt", "invalid")
    assert not service.sessions
