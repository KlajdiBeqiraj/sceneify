"""Tests for the optional MCP adapter."""

from __future__ import annotations

import pytest

from sceneify.agent_tools import WorldTools
from sceneify.catalog import AssetCatalog
from sceneify.scene import Scene


def test_build_mcp_server_imports_optional_adapter() -> None:
    pytest.importorskip("mcp")
    from sceneify.mcp_server import build_mcp_server

    tools = WorldTools(Scene("mcp"), AssetCatalog())
    assert build_mcp_server(tools) is not None


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
