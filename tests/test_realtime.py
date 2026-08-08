"""Tests for realtime callbacks and the WebSocket protocol."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from sceneify import InputEvent, Scene
from sceneify.server import PROTOCOL_NAME, PROTOCOL_VERSION, create_app


def test_transforms_delta_reports_only_dirty_poses() -> None:
    scene = Scene("delta")
    scene.create_primitive("a", "box", position=(0, 0, 0))
    scene.create_primitive("b", "box", position=(1, 0, 0))
    first, previous, full = scene.transforms_delta()
    assert full is True
    assert {row["id"] for row in first} == {"a", "b"}

    unchanged, previous, full = scene.transforms_delta(previous=previous)
    assert full is False
    assert unchanged == []

    scene.update_node("a", position=(0, 2, 0))
    changed, previous, full = scene.transforms_delta(previous=previous)
    assert full is False
    assert len(changed) == 1
    assert changed[0]["id"] == "a"
    assert changed[0]["position"] == [0.0, 2.0, 0.0]


def test_frame_broadcast_uses_delta_transforms() -> None:
    scene = Scene("frames")
    scene.create_primitive("mover", "box", position=(0, 0, 0))
    moved = {"count": 0}

    @scene.on_tick
    def tick(current: Scene, delta: float) -> None:
        moved["count"] += 1
        if moved["count"] == 1:
            return
        current.update_node("mover", position=(0, float(moved["count"]), 0))

    with (
        TestClient(create_app(scene, tick_rate=40.0)) as client,
        client.websocket_connect("/api/realtime") as socket,
    ):
        hello = socket.receive_json()
        assert "frameDelta" in hello["capabilities"]
        frames: list[dict] = []
        deadline = time.time() + 1.0
        while time.time() < deadline and len(frames) < 3:
            message = socket.receive_json()
            if message.get("type") == "frame":
                assert "scene" not in message
                assert "transforms" in message
                frames.append(message)
        assert frames
        assert frames[0]["full"] is True
        assert any(row["id"] == "mover" for row in frames[0]["transforms"])
        # Later frames that move the node are partial merges.
        partial = next((frame for frame in frames[1:] if frame.get("full") is False), None)
        if partial is not None:
            assert all(row["id"] == "mover" for row in partial["transforms"])


def test_callback_decorators_and_input_protocol() -> None:
    scene = Scene("callbacks")
    inputs: list[InputEvent] = []
    ticks: list[float] = []

    @scene.on_tick()
    def tick(current: Scene, delta: float) -> None:
        assert current is scene
        ticks.append(delta)

    @scene.on_input
    def receive_input(current: Scene, event: InputEvent) -> None:
        assert current is scene
        inputs.append(event)

    with (
        TestClient(create_app(scene, tick_rate=30.0)) as client,
        client.websocket_connect("/api/realtime") as socket,
    ):
        hello = socket.receive_json()
        assert hello["type"] == "hello"
        assert hello["protocol"] == PROTOCOL_NAME
        assert hello["version"] == PROTOCOL_VERSION
        socket.send_json({"type": "input", "action": "jump", "value": 2})
        socket.send_json({"type": "ping", "timestamp": 4.5})
        while True:
            message = socket.receive_json()
            if message["type"] == "ping":
                break
        assert message == {"type": "ping", "timestamp": 4.5, "reply": True}

    assert ticks
    assert len(inputs) == 1
    assert inputs[0].action == "jump"
    assert inputs[0].value == 2
    assert inputs[0].client_id


def test_tick_loop_is_shared_by_multiple_clients() -> None:
    scene = Scene("shared")
    tick_count = 0

    @scene.on_tick
    def tick(current: Scene, delta: float) -> None:
        nonlocal tick_count
        tick_count += 1

    with (
        TestClient(create_app(scene, tick_rate=20.0)) as client,
        client.websocket_connect("/api/realtime") as first,
        client.websocket_connect("/api/realtime") as second,
    ):
        assert first.receive_json()["type"] == "hello"
        assert second.receive_json()["type"] == "hello"
        time.sleep(0.16)

    assert 2 <= tick_count <= 8
