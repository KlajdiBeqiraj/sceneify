"""Server start/stop smoke test."""

from __future__ import annotations

import time

import httpx

from sceneify.scene import Scene


def test_run_block_false_can_stop() -> None:
    scene = Scene("stop-test")
    scene.add_annotation("a", position=(0, 1, 0), label="n")
    handle = scene.run(block=False, open_browser=False, port=8766)
    try:
        deadline = time.time() + 3.0
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                response = httpx.get(f"{handle.url}api/health", timeout=0.5)
                if response.status_code == 200:
                    break
            except Exception as exc:
                last_error = exc
                time.sleep(0.1)
        else:
            raise AssertionError(f"Server did not become ready: {last_error}")
    finally:
        handle.stop()
        time.sleep(0.2)
        assert not handle.running
