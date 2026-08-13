"""Tests for the optional MCP adapter."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sceneify.agent_tools import WorldTools
from sceneify.catalog import AssetCatalog
from sceneify.scene import Scene
from sceneify.server import create_app


def test_build_mcp_server_imports_optional_adapter() -> None:
    pytest.importorskip("mcp")
    from sceneify.mcp_server import build_mcp_server

    tools = WorldTools(Scene("mcp"), AssetCatalog())
    assert build_mcp_server(tools) is not None


def test_http_perception_endpoints() -> None:
    scene = Scene("http-sense")
    scene.set_environment(bounds_min=(-4, 0, -4), bounds_max=(4, 4, 4))
    scene.create_primitive("player", "capsule", position=(0, 1, 2), tags=["player"])
    app = create_app(scene, realtime=False)
    with TestClient(app) as client:
        overview = client.get("/api/scene/overview")
        assert overview.status_code == 200
        assert overview.json()["name"] == "http-sense"
        topdown = client.get("/api/scene/topdown", params={"cellSize": 1})
        assert topdown.status_code == 200
        assert "P" in topdown.json()["ascii"]
        world = client.get("/api/nodes/player/world")
        assert world.status_code == 200
        assert world.json()["world"]["position"] == [0.0, 1.0, 2.0]
        capture = client.post("/api/scene/capture", json={"preset": "presentation"})
        assert capture.status_code == 503


def test_live_world_tools_perception_uses_local_scene(monkeypatch: pytest.MonkeyPatch) -> None:
    from sceneify.mcp_server import LiveWorldTools

    tools = LiveWorldTools("http://127.0.0.1:8765")

    def fake_request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        assert method == "GET"
        assert path == "/api/scene"
        return {
            "schemaVersion": 2,
            "name": "live",
            "background": "#000",
            "environment": {
                "bounds": {"min": [-5, 0, -5], "max": [5, 5, 5], "visible": True, "color": "#fff"},
                "ground": {"y": 0, "visible": True, "color": "#333"},
                "snapGrid": None,
                "worldMesh": None,
                "zones": [],
                "rules": [],
            },
            "meshes": [],
            "objects": [
                {
                    "kind": "object",
                    "id": "root",
                    "parentId": None,
                    "tags": [],
                    "position": [2, 0, 0],
                    "rotation": [0, 0, 0],
                    "scale": [1, 1, 1],
                    "visible": True,
                    "material": None,
                    "physics": None,
                    "meta": {},
                    "label": "Root",
                }
            ],
            "primitives": [],
            "annotations": [],
            "trajectories": [],
            "game": None,
            "presentation": {},
            "prefabs": [],
            "revision": 1,
        }

    monkeypatch.setattr(tools, "_request", fake_request)
    result = tools.apply({"action": "describe_scene", "detail": "summary"})
    assert result["result"]["name"] == "live"
    assert result["result"]["nodes"][0]["id"] == "root"
    assert result.get("sceneIncluded") is False


def test_live_world_tools_mutation_syncs_python(monkeypatch: pytest.MonkeyPatch) -> None:
    from sceneify.mcp_server import LiveWorldTools

    calls: list[tuple[str, str, dict[str, object]]] = []

    def fake_request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        calls.append((method, path, kwargs))
        if path == "/api/scene":
            return {"name": "live", "revision": 4}
        if path == "/api/commands":
            return {
                "revision": 5,
                "result": {"id": "crate"},
                "scene": {"name": "live", "revision": 5},
            }
        assert path == "/api/scene/save-python"
        return {"saved": "/project/world.py", "revision": 5, "sync": {"mode": "markers"}}

    tools = LiveWorldTools("http://127.0.0.1:8765", source_path="world.py")
    monkeypatch.setattr(tools, "_request", fake_request)

    result = tools.apply({"action": "add_primitive", "id": "crate", "primitive": "box"})

    assert result["result"] == {"id": "crate"}
    assert calls == [
        ("GET", "/api/scene", {}),
        (
            "POST",
            "/api/commands",
            {
                "json": {
                    "action": "create_primitive",
                    "id": "crate",
                    "primitive": "box",
                    "expectedRevision": 4,
                }
            },
        ),
        (
            "POST",
            "/api/scene/save-python",
            {
                "json": {
                    "path": "world.py",
                    "mode": "auto",
                    "expectedRevision": 5,
                }
            },
        ),
    ]
