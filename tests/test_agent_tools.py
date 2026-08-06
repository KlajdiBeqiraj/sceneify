"""Tests for provider independent world actions."""

from __future__ import annotations

from pathlib import Path

import pytest

from sceneify import load_schema
from sceneify.agent_tools import WorldTools, tool_definition
from sceneify.catalog import Asset, AssetCatalog
from sceneify.scene import Scene


def test_world_tools_build_scene_from_catalog(tmp_path: Path) -> None:
    scene = Scene("agent-authored")
    catalog = AssetCatalog(
        assets=[
            Asset(id="arena", path="assets/arena.glb"),
            Asset(id="robot", path="assets/robot.glb", tags=["character"]),
        ]
    )
    tools = WorldTools(scene, catalog)

    tools.apply({"action": "set_world", "asset": "arena"})
    tools.apply(
        {
            "action": "add_asset",
            "asset": "robot",
            "id": "player",
            "position": [1, 0, 2],
        }
    )
    saved = tools.apply({"action": "save", "path": str(tmp_path / "world.sceneify.json")})

    assert scene.environment is not None
    assert scene.environment.world_mesh is not None
    assert scene.to_dict()["meshes"][0]["meta"]["catalog_asset"] == "robot"
    assert Path(saved["result"]["path"]).is_file()


def test_tool_definition_is_provider_neutral() -> None:
    descriptor = tool_definition()
    assert descriptor["name"] == "sceneify_apply"
    assert "inputSchema" in descriptor
    assert "provider" not in descriptor
    assert load_schema("scene")["properties"]["format"]["const"] == "sceneify-scene"


def test_world_tools_reject_unknown_action() -> None:
    tools = WorldTools(Scene(), AssetCatalog())
    with pytest.raises(ValueError, match="Unsupported world action"):
        tools.apply({"action": "invent_mesh"})
