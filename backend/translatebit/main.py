from __future__ import annotations

import asyncio
import os
import secrets
import time
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .domain import Room
from .samples import SAMPLES
from .media import MediaService, ice_servers
from .local_speech import LocalEngine, SpeechInput

engine = LocalEngine()

media = MediaService()

rooms: dict[str, Room] = {}
sockets: dict[str, dict[str, WebSocket]] = {}
broadcast_locks: dict[str, asyncio.Lock] = {}


async def broadcast(room: Room):
    async with broadcast_locks.setdefault(room.code, asyncio.Lock()):
        payload = {"type": "snapshot", "room": room.snapshot()}
        for socket in list(sockets.get(room.code, {}).values()):
            try:
                await asyncio.wait_for(socket.send_json(payload), timeout=2)
            except (RuntimeError, WebSocketDisconnect, OSError, TimeoutError):
                pass


async def cleanup():
    while True:
        await asyncio.sleep(60)
        for code, room in list(rooms.items()):
            if time.time() - room.created_at > 7200:
                await asyncio.gather(
                    *(socket.close(code=4004, reason="Demo room expired.")
                      for socket in list(sockets.get(code, {}).values())),
                    return_exceptions=True,
                )
                await media.close_room(code)
                await room.close()
                rooms.pop(code, None)
                sockets.pop(code, None)
                broadcast_locks.pop(code, None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(cleanup())
    yield
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await media.close_all()
    for room in rooms.values():
        await room.close()


app = FastAPI(title="TranslateBit", version="0.1.0", lifespan=lifespan)


class JoinRequest(BaseModel):
    language: Literal["hi", "en"]


def get_room(code: str) -> Room:
    room = rooms.get(code.upper())
    if room is None:
        raise HTTPException(404, "Room not found or expired. Create a new room.")
    return room


def credentials(room: Room, language: str):
    try:
        p = room.add_participant(language)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    return {"code": room.code, "participant_id": p.id, "token": p.token, "language": p.language}


@app.get("/api/health")
async def health():
    return {"status": "ok", "mode": "scripted_demo", "media_transport": "self_hosted_webrtc", "media_modes": ["loopback", "interpret"], "voice_worker_ready": engine.available()}


@app.get("/api/samples")
async def samples():
    return SAMPLES


@app.post("/api/rooms", status_code=201)
async def create(body: JoinRequest):
    if len(rooms) >= 100:
        raise HTTPException(503, "Demo room capacity reached. Try again later.")
    code = secrets.token_hex(4).upper()
    while code in rooms:
        code = secrets.token_hex(4).upper()
    room = Room(code)
    room.notify = lambda: broadcast(room)
    rooms[code] = room
    return credentials(room, body.language)


@app.post("/api/rooms/{code}/join")
async def join(code: str, body: JoinRequest):
    room = get_room(code)
    result = credentials(room, body.language)
    await broadcast(room)
    return result


class MediaOffer(BaseModel):
    mode: Literal["loopback", "interpret"] = "loopback"
    sdp: str = Field(min_length=1, max_length=65536)
    session_id: str = Field(pattern=r"^[a-zA-Z0-9-]{16,64}$")


def media_participant(code, authorization):
    room = get_room(code)
    participant = room.authenticate(authorization.removeprefix("Bearer "))
    if participant is None:
        raise HTTPException(401, "Invalid participant credential.")
    return room, participant


@app.get("/api/rooms/{code}/media-config")
async def media_config(code: str, authorization: str = Header(default="")):
    media_participant(code, authorization)
    return {"iceServers": ice_servers(), "modes": ["loopback", "interpret"], "max_seconds": 120, "local_models_available": engine.available()}


@app.post("/api/rooms/{code}/media-offer")
async def media_offer(code: str, body: MediaOffer, authorization: str = Header(default="")):
    room, participant = media_participant(code, authorization)
    if not participant.connected:
        raise HTTPException(409, "Connect to the room before starting audio.")
    if body.mode == "interpret" and not engine.available():
        raise HTTPException(503, "Local models are missing. Run scripts/setup_models.py.")
    if body.mode == "interpret" and (len(room.participants) != 2 or not all(p.connected for p in room.participants.values())):
        raise HTTPException(409, "Connect both participants before starting interpretation.")
    sink = SpeechInput(room, participant, engine) if body.mode == "interpret" else None
    try:
        result = await media.offer((room.code, participant.id), body.session_id, body.sdp, sink)
        # A control disconnect during negotiation must not leave microphone processing running.
        if not participant.connected:
            await media.close((room.code, participant.id), body.session_id)
            raise HTTPException(409, "Room connection ended during negotiation.")
        room.event("media_negotiated", participant_id=participant.id)
        await broadcast(room)
        return result
    except (ValueError, TimeoutError) as error:
        raise HTTPException(400, "Could not negotiate audio. Stop and try again.") from error


@app.delete("/api/rooms/{code}/media/{session_id}", status_code=204)
async def media_stop(code: str, session_id: str, authorization: str = Header(default="")):
    room, participant = media_participant(code, authorization)
    await media.close((room.code, participant.id), session_id)
    await broadcast(room)


@app.websocket("/api/rooms/{code}/events")
async def events(socket: WebSocket, code: str):
    # Credentials travel in the first frame, never in URLs or access logs.
    origin = socket.headers.get("origin")
    allowed = os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:4173").split(",")
    if origin and origin not in allowed:
        await socket.close(code=4003)
        return
    await socket.accept()
    room = rooms.get(code.upper())
    if room is None:
        await socket.close(code=4004)
        return
    try:
        hello = await asyncio.wait_for(socket.receive_json(), 5)
        token = hello.get("token") if isinstance(hello, dict) else None
        p = room.authenticate(token) if isinstance(token, str) else None
    except (TimeoutError, ValueError, WebSocketDisconnect):
        await socket.close(code=4001)
        return
    if p is None:
        await socket.close(code=4001)
        return
    connections = sockets.setdefault(room.code, {})
    if p.id in connections:
        await socket.close(code=4009, reason="This participant is already open in another tab.")
        return
    connections[p.id] = socket
    await room.connect(p)
    try:
        while True:
            message = await socket.receive_json()
            try:
                if not isinstance(message, dict):
                    raise ValueError("Expected a command object.")
                action = message.get("type")
                if not isinstance(action, str):
                    raise ValueError("Command type must be text.")
                if action == "playback" and not isinstance(message.get("action"), str):
                    raise ValueError("Playback action must be text.")
                if action == "submit":
                    await room.submit(p, message.get("sample_id", ""))
                elif action == "playback":
                    await room.playback(p, message.get("segment_id", ""), message.get("action", ""))
                elif action == "stop":
                    await room.stop(p)
                elif action == "ping":
                    await socket.send_json({"type": "pong"})
                else:
                    raise ValueError("Unknown command.")
            except ValueError as error:
                await socket.send_json({"type": "error", "message": str(error)})
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass
    finally:
        if connections.get(p.id) is socket:
            connections.pop(p.id, None)
            await media.close((room.code, p.id))
            await room.disconnect(p)


if static_dir := os.getenv("STATIC_DIR"):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
