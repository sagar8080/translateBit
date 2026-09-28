import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.translatebit.main import app, rooms, sockets, broadcast_locks


@pytest.fixture
def client():
    rooms.clear()
    sockets.clear()
    broadcast_locks.clear()
    with TestClient(app) as value:
        yield value


def create(client, language="hi"):
    result = client.post("/api/rooms", json={"language": language})
    assert result.status_code == 201
    return result.json()


def test_capacity_and_language_validation(client):
    host = create(client)
    path = f"/api/rooms/{host['code']}/join"
    assert client.post(path, json={"language": "hi"}).status_code == 409
    assert client.post(path, json={"language": "en"}).status_code == 200
    assert client.post(path, json={"language": "en"}).status_code == 409
    assert client.post("/api/rooms", json={"language": "fr"}).status_code == 422
    assert client.post("/api/rooms/MISSING/join", json={"language": "en"}).status_code == 404


def test_websocket_requires_participant_secret(client):
    host = create(client)
    with client.websocket_connect(f"/api/rooms/{host['code']}/events") as ws:
        ws.send_json({"token": "incorrect"})
        with pytest.raises(WebSocketDisconnect) as error:
            ws.receive_json()
        assert error.value.code == 4001


def test_room_credentials_do_not_cross_room_boundaries(client):
    a, b = create(client), create(client)
    with client.websocket_connect(f"/api/rooms/{b['code']}/events") as ws:
        ws.send_json({"token": a["token"]})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_duplicate_connection_is_rejected(client):
    host = create(client)
    path = f"/api/rooms/{host['code']}/events"
    with client.websocket_connect(path) as first:
        first.send_json({"token": host["token"]})
        assert first.receive_json()["type"] == "snapshot"
        with client.websocket_connect(path) as second:
            second.send_json({"token": host["token"]})
            with pytest.raises(WebSocketDisconnect) as error:
                second.receive_json()
            assert error.value.code == 4009


def test_origin_is_checked(client):
    host = create(client)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/rooms/{host['code']}/events", headers={"origin": "https://untrusted.example"}):
            pass


def test_media_config_requires_room_credential(client):
    host = create(client)
    path = f"/api/rooms/{host['code']}/media-config"
    assert client.get(path).status_code == 401
    response = client.get(path, headers={"authorization": f"Bearer {host['token']}"})
    assert response.json()["iceServers"] == []
    assert response.json()["modes"] == ["loopback", "interpret"]
    assert isinstance(response.json()["local_models_available"], bool)


def test_media_offer_requires_active_participant(client):
    host = create(client)
    response = client.post(f"/api/rooms/{host['code']}/media-offer",
        headers={"authorization": f"Bearer {host['token']}"},
        json={"sdp": "invalid", "session_id": "test-session-123456"})
    assert response.status_code == 409
    assert isinstance(client.get("/api/health").json()["voice_worker_ready"], bool)
