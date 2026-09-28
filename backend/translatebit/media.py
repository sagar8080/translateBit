"""Owned WebRTC loopback transport. No hosted services or default STUN calls."""
import asyncio
import json
import os
from collections import deque
from dataclasses import dataclass

from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamTrack


def ice_servers():
    return json.loads(os.getenv("ICE_SERVERS_JSON", "[]"))


class EchoTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, source, sink=None):
        super().__init__()
        self.source = source
        self.sink = sink
        self.frames = 0

    async def recv(self):
        frame = await self.source.recv()
        self.frames += 1
        if self.sink:
            self.sink.feed(frame)
            for plane in frame.planes:
                plane.update(bytes(plane.buffer_size))
        return frame

    def stop(self):
        super().stop()
        self.source.stop()
        if self.sink:
            self.sink.close()


@dataclass
class MediaSession:
    id: str
    peer: RTCPeerConnection
    echo: EchoTrack | None = None
    timer: asyncio.Task | None = None


class MediaService:
    def __init__(self):
        self.sessions: dict[tuple[str, str], MediaSession] = {}
        self.locks: dict[tuple[str, str], asyncio.Lock] = {}
        self.cancelled = deque(maxlen=1024)

    async def close(self, key, session_id=None):
        if session_id is not None:
            self.cancelled.append((key, session_id))
        session = self.sessions.get(key)
        if session is None or (session_id is not None and session.id != session_id):
            return
        self.sessions.pop(key, None)
        if session.timer and session.timer is not asyncio.current_task():
            session.timer.cancel()
        if session.echo:
            session.echo.stop()
        await session.peer.close()

    async def close_room(self, room):
        await asyncio.gather(*(self.close(key) for key in list(self.sessions) if key[0] == room))
        for key in list(self.locks):
            if key[0] == room:
                self.locks.pop(key, None)

    async def close_all(self):
        await asyncio.gather(*(self.close(key) for key in list(self.sessions)))

    async def offer(self, key, session_id, sdp, sink=None):
        async with self.locks.setdefault(key, asyncio.Lock()):
            if (key, session_id) in self.cancelled:
                raise ValueError("This media attempt was stopped.")
            return await self._offer(key, session_id, sdp, sink)

    async def _offer(self, key, session_id, sdp, sink=None):
        # Publish ownership before awaiting negotiation: stale offers cannot replace newer ones.
        await self.close(key)
        if (key, session_id) in self.cancelled:
            raise ValueError("This media attempt was stopped.")
        peer = RTCPeerConnection(RTCConfiguration(iceServers=[RTCIceServer(**s) for s in ice_servers()]))
        session = MediaSession(session_id, peer)
        self.sessions[key] = session

        async def expire():
            await asyncio.sleep(120)
            await self.close(key, session_id)

        session.timer = asyncio.create_task(expire())

        @peer.on("track")
        def on_track(track):
            if track.kind != "audio" or session.echo is not None:
                return
            session.echo = EchoTrack(track, sink)
            peer.addTrack(session.echo)

        @peer.on("connectionstatechange")
        async def state_changed():
            if peer.connectionState in {"failed", "closed"}:
                await self.close(key, session_id)

        try:
            async with asyncio.timeout(15):
                await peer.setRemoteDescription(RTCSessionDescription(sdp=sdp, type="offer"))
                if session.echo is None or len(peer.getTransceivers()) != 1:
                    raise ValueError("Offer must contain exactly one audio track.")
                await peer.setLocalDescription(await peer.createAnswer())
            if self.sessions.get(key) is not session:
                raise ValueError("Media attempt was superseded. Try again.")
            return {"sdp": peer.localDescription.sdp, "type": "answer", "session_id": session_id}
        except BaseException:
            await self.close(key, session_id)
            # Superseded sessions still own their local peer object.
            await peer.close()
            raise
