"""Tests for the optional MCP adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sceneify.agent_tools import WorldTools
from sceneify.catalog import AssetCatalog
from sceneify.scene import Scene
from sceneify.server import create_app


def _tool_payload(result: object) -> dict[str, object]:
    """Normalize FastMCP call_tool return shapes to a JSON object."""
    if isinstance(result, tuple):
        result = result[0]
    content = getattr(result, "content", result)
    if isinstance(content, list) and content:
        first = content[0]
        text = getattr(first, "text", None)
        if isinstance(text, str):
            return json.loads(text)
        if isinstance(first, dict) and isinstance(first.get("text"), str):
            return json.loads(first["text"])
    structured = getattr(result, "structuredContent", None) or getattr(result, "data", None)
    if isinstance(structured, dict):
        return structured
    if isinstance(result, dict):
        return result
    raise AssertionError(f"Unexpected MCP tool result: {result!r}")


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
            "experience": None,
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


def test_mcp_apply_schema_does_not_require_extra() -> None:
    pytest.importorskip("mcp")
    import asyncio

    from sceneify.mcp_server import build_mcp_server
    from sceneify.session_manager import SessionManager

    server = build_mcp_server(
        WorldTools(Scene("schema"), AssetCatalog()),
        session_manager=SessionManager("."),
    )
    tools = asyncio.run(server.list_tools())
    by_name = {tool.name: tool for tool in tools}
    apply_schema = getattr(by_name["sceneify_apply"], "inputSchema", None) or by_name[
        "sceneify_apply"
    ].input_schema
    session_schema = getattr(by_name["sceneify_apply_session"], "inputSchema", None) or by_name[
        "sceneify_apply_session"
    ].input_schema
    assert apply_schema.get("required") == ["action"]
    assert session_schema.get("required") == ["sessionId", "action"]
    assert "sceneify_scaffold" in by_name
    scaffold_schema = getattr(by_name["sceneify_scaffold"], "inputSchema", None) or by_name[
        "sceneify_scaffold"
    ].input_schema
    assert "family" in scaffold_schema.get("required", ["family"])
    assert "extra" not in apply_schema.get("required", [])
    assert "extra" not in session_schema.get("required", [])


def test_mcp_apply_accepts_flattened_fields_without_extra() -> None:
    pytest.importorskip("mcp")
    import asyncio

    from sceneify.mcp_server import build_mcp_server

    tools = WorldTools(Scene("flat"), AssetCatalog())
    server = build_mcp_server(tools)
    result = asyncio.run(
        server.call_tool(
            "sceneify_apply",
            {"action": "add_primitive", "id": "floor", "primitive": "box"},
        )
    )
    payload = _tool_payload(result)
    assert payload["ok"] is True
    assert any(node["id"] == "floor" for node in tools.scene.to_dict()["primitives"])


def test_shared_catalog_fetch_then_live_set_presentation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sceneify.catalog import Asset
    from sceneify.mcp_server import LiveWorldTools

    hdr = tmp_path / "sky.hdr"
    hdr.write_bytes(b"hdr")
    catalog_path = tmp_path / "assets.catalog.json"
    catalog = AssetCatalog(
        assets=[Asset(id="sky", path=str(hdr), format="hdr", tags=["hdri"])]
    ).bind_path(catalog_path)
    catalog.persist()

    stdio = WorldTools(Scene("stdio"), catalog)
    live_a = LiveWorldTools("http://127.0.0.1:8765", catalog=stdio.catalog)
    live_b = LiveWorldTools("http://127.0.0.1:8765", catalog=stdio.catalog)
    assert live_a.catalog is stdio.catalog
    assert live_b.catalog is stdio.catalog
    assert live_b.catalog.get("sky").id == "sky"

    posted: list[dict[str, object]] = []

    def fake_request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        if path == "/api/scene":
            return {"name": "live", "revision": 1, "presentation": {}}
        if path == "/api/commands":
            posted.append(kwargs["json"])  # type: ignore[index]
            return {
                "revision": 2,
                "result": {"environmentMap": str(hdr)},
                "scene": {"name": "live", "revision": 2},
            }
        raise AssertionError(path)

    monkeypatch.setattr(live_a, "_request", fake_request)
    result = live_a.apply({"action": "set_presentation", "asset": "sky", "shadows": True})
    assert result["result"]["environmentMap"] == str(hdr)
    assert posted[0]["environmentMap"] == str(hdr)
    assert "asset" not in posted[0]


def test_shared_catalog_fetch_then_live_add_asset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sceneify.catalog import Asset
    from sceneify.mcp_server import LiveWorldTools

    glb = tmp_path / "bust.glb"
    glb.write_bytes(b"glb")
    catalog = AssetCatalog(assets=[Asset(id="bust", path=str(glb), format="glb")])
    live = LiveWorldTools("http://127.0.0.1:8765", catalog=catalog)
    posted: list[dict[str, object]] = []

    def fake_request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        if path == "/api/scene":
            return {"name": "live", "revision": 3}
        if path == "/api/commands":
            posted.append(kwargs["json"])  # type: ignore[index]
            return {"revision": 4, "result": {"id": "bust_1"}, "scene": {"revision": 4}}
        raise AssertionError(path)

    monkeypatch.setattr(live, "_request", fake_request)
    result = live.apply({"action": "add_asset", "asset": "bust", "id": "bust_1"})
    assert result["ok"] is True if "ok" in result else result["result"]["id"] == "bust_1"
    assert posted[0]["assetId"] == "bust"
    assert posted[0]["source"] == str(glb)


def test_apply_session_reuses_process_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("mcp")
    import asyncio
    from types import SimpleNamespace

    from sceneify.catalog import Asset
    from sceneify.mcp_server import LiveWorldTools, build_mcp_server
    from sceneify.session_manager import SessionManager

    glb = tmp_path / "bust.glb"
    glb.write_bytes(b"glb")
    catalog = AssetCatalog(assets=[Asset(id="bust", path=str(glb), format="glb")])
    stdio = WorldTools(Scene("stdio"), catalog)
    manager = SessionManager(tmp_path)
    script = tmp_path / "examples" / "mcp" / "demo.py"
    script.parent.mkdir(parents=True)
    script.write_text("# sceneify:scene-begin\n# sceneify:scene-end\n", encoding="utf-8")
    fake_session = SimpleNamespace(url="http://127.0.0.1:8765", script=script)
    monkeypatch.setattr(manager, "get", lambda session_id: fake_session)

    posted: list[dict[str, object]] = []
    catalogs: list[object] = []

    def fake_request(
        self: LiveWorldTools, method: str, path: str, **kwargs: object
    ) -> dict[str, object]:
        del method
        catalogs.append(self.catalog)
        if path == "/api/scene":
            return {"name": "live", "revision": 1}
        if path == "/api/commands":
            posted.append(kwargs["json"])  # type: ignore[index]
            return {"revision": 2, "result": {"id": "bust_1"}, "scene": {"revision": 2}}
        if path == "/api/scene/save-python":
            return {"saved": str(script), "revision": 2, "sync": {"mode": "markers"}}
        raise AssertionError(path)

    monkeypatch.setattr(LiveWorldTools, "_request", fake_request)
    server = build_mcp_server(stdio, session_manager=manager)
    first = asyncio.run(
        server.call_tool(
            "sceneify_apply_session",
            {"sessionId": "demo", "action": "add_asset", "asset": "bust", "id": "bust_1"},
        )
    )
    second = asyncio.run(
        server.call_tool(
            "sceneify_apply_session",
            {"sessionId": "demo", "action": "add_asset", "asset": "bust", "id": "bust_2"},
        )
    )
    assert _tool_payload(first)["ok"] is True
    assert _tool_payload(second)["ok"] is True
    assert catalogs[0] is stdio.catalog
    assert catalogs[1] is stdio.catalog
    assert posted[0]["assetId"] == "bust"
    assert posted[1]["id"] == "bust_2"


def test_mcp_apply_accepts_nested_fields() -> None:
    pytest.importorskip("mcp")
    import asyncio

    from sceneify.mcp_server import build_mcp_server

    tools = WorldTools(Scene("nested"), AssetCatalog())
    server = build_mcp_server(tools)
    result = asyncio.run(
        server.call_tool(
            "sceneify_apply",
            {"action": "add_primitive", "fields": {"id": "wall", "primitive": "box"}},
        )
    )
    payload = _tool_payload(result)
    assert payload["ok"] is True
    assert any(node["id"] == "wall" for node in tools.scene.to_dict()["primitives"])


def test_live_add_asset_unknown_catalog_id_is_actionable() -> None:
    from sceneify.mcp_server import LiveWorldTools

    live = LiveWorldTools("http://127.0.0.1:8765", catalog=AssetCatalog())
    with pytest.raises(ValueError, match="Unknown catalog asset"):
        live._server_command({"action": "add_asset", "asset": "missing"})


def test_mcp_scaffold_board_writes_clickable_shell(tmp_path: Path) -> None:
    pytest.importorskip("mcp")
    import asyncio

    from sceneify.mcp_server import build_mcp_server
    from sceneify.session_manager import SessionManager

    manager = SessionManager(tmp_path)
    server = build_mcp_server(WorldTools(Scene("mcp"), AssetCatalog()), session_manager=manager)
    result = asyncio.run(
        server.call_tool("sceneify_scaffold", {"family": "board", "name": "tokens", "title": "Tokens"})
    )
    payload = _tool_payload(result)
    assert payload["path"] == "examples/mcp/tokens.py"
    assert payload["family"] == "board"
    text = (tmp_path / payload["path"]).read_text(encoding="utf-8")
    assert "add_board" in text
    assert "kaykit-knight" in text
    assert "asset=" in text
    present = asyncio.run(
        server.call_tool("sceneify_scaffold", {"family": "present", "name": "hall"})
    )
    embed = _tool_payload(present)["embed"]
    assert "<sceneify-viewer" in embed["webComponent"]
