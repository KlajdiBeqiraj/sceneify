"""Tests for episode recording, persistence, and replay protocol."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sceneify import Episode, Scene, load_schema
from sceneify.episode import EPISODE_FORMAT, EPISODE_VERSION
from sceneify.server import PROTOCOL_VERSION, create_app


def test_episode_roundtrip_and_schema(tmp_path: Path) -> None:
    episode = Episode(id="ep1", scene_name="arena", tick_rate=30.0)
    episode.add_input(0.0, "keydown", value="w", metadata={"code": "KeyW"})
    episode.add_semantic(0.5, "collect", node_id="coin_1", data={"score": 1})
    episode.add_input(0.8, "keyup", value="w", metadata={"code": "KeyW"})
    episode.add_marker(1.0, "end")
    path = episode.save(tmp_path / "run.json")
    loaded = Episode.load(path)
    assert loaded.id == "ep1"
    assert loaded.duration == 1.0
    assert [event.kind for event in loaded.events] == ["input", "semantic", "input", "marker"]
    assert loaded.inputs()[0].metadata["code"] == "KeyW"
    document = loaded.to_document()
    assert document["format"] == EPISODE_FORMAT
    assert document["version"] == EPISODE_VERSION

    schema = load_schema("episode")
    assert schema["properties"]["format"]["const"] == EPISODE_FORMAT
    assert schema["properties"]["version"]["const"] == EPISODE_VERSION


def test_record_via_websocket_and_rest(tmp_path: Path) -> None:
    scene = Scene("record-demo")
    app = create_app(scene, realtime=True, tick_rate=20.0, project_root=tmp_path)
    with TestClient(app) as client, client.websocket_connect("/api/realtime") as socket:
        hello = socket.receive_json()
        assert hello["version"] == PROTOCOL_VERSION
        assert "recording" in hello["capabilities"]
        assert "replay" in hello["capabilities"]
        assert hello["recording"] is False

        started = client.post("/api/episode/record/start", json={"episodeId": "manual"})
        assert started.status_code == 200
        assert started.json()["recording"] is True
        assert started.json()["episodeId"] == "manual"
        state = socket.receive_json()
        assert state["type"] == "record_state"
        assert state["recording"] is True

        socket.send_json(
            {
                "type": "input",
                "action": "keydown",
                "value": "w",
                "metadata": {"code": "KeyW"},
            }
        )
        socket.send_json(
            {"type": "semantic_event", "name": "collect", "nodeId": "coin", "data": {"score": 1}}
        )
        assert socket.receive_json()["type"] == "event_ack"
        time.sleep(0.05)

        stopped = client.post("/api/episode/record/stop")
        assert stopped.status_code == 200
        document = stopped.json()
        assert document["format"] == EPISODE_FORMAT
        kinds = [event["kind"] for event in document["episode"]["events"]]
        assert "input" in kinds
        assert "semantic" in kinds
        assert kinds[-1] == "marker"
        assert Episode.from_document(document).scene_name == "record-demo"
        final_state = socket.receive_json()
        assert final_state["type"] == "record_state"
        assert final_state["recording"] is False


def test_replay_streams_inputs_to_clients(tmp_path: Path) -> None:
    scene = Scene("replay-demo")
    episode = Episode(id="replay1", scene_name="replay-demo", tick_rate=60.0)
    episode.add_input(0.0, "keydown", value="d", metadata={"code": "KeyD"})
    episode.add_input(0.05, "keyup", value="d", metadata={"code": "KeyD"})
    episode.add_marker(0.08, "end")
    episode_path = episode.save(tmp_path / "episode.json")

    app = create_app(scene, realtime=True, tick_rate=30.0, project_root=tmp_path)
    with TestClient(app) as client, client.websocket_connect("/api/realtime") as socket:
        assert socket.receive_json()["type"] == "hello"
        response = client.post("/api/episode/replay", json={"path": "episode.json"})
        assert response.status_code == 200
        assert response.json()["replaying"] is True

        saw_start = False
        saw_input = False
        saw_complete = False
        deadline = time.time() + 2.0
        while time.time() < deadline and not saw_complete:
            message = socket.receive_json()
            if message.get("type") == "replay_control" and message.get("action") == "start":
                saw_start = True
            if message.get("type") == "replay_input" and message.get("action") == "keydown":
                saw_input = True
                assert message["metadata"]["replay"] is True
                assert message["metadata"]["code"] == "KeyD"
            if message.get("type") == "replay_control" and message.get("action") == "complete":
                saw_complete = True
        assert saw_start and saw_input and saw_complete
        assert episode_path.is_file()


def test_cannot_record_twice() -> None:
    scene = Scene("once")
    app = create_app(scene, realtime=True)
    with TestClient(app) as client:
        assert client.post("/api/episode/record/start").status_code == 200
        assert client.post("/api/episode/record/start").status_code == 400
        assert client.post("/api/episode/record/stop").status_code == 200
        with pytest.raises(ValueError, match="not active"):
            # Direct runtime guard after stop.
            app.state.realtime.stop_recording()
