"""Tests for realtime callbacks and the WebSocket protocol."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from sceneify import InputEvent, Scene
from sceneify.server import PROTOCOL_NAME, PROTOCOL_VERSION, create_app


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
