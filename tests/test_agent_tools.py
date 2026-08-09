"""Tests for provider independent world actions."""

from __future__ import annotations

from pathlib import Path

import pytest

from sceneify import load_schema
from sceneify.agent_tools import WorldTools, tool_definition, tool_definitions
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
    assert "fetch_remote" in descriptor["inputSchema"]["properties"]["action"]["enum"]
    assert "set_presentation" in descriptor["inputSchema"]["properties"]["action"]["enum"]
    assert load_schema("scene")["properties"]["format"]["const"] == "sceneify-scene"
    names = {item["name"] for item in tool_definitions()}
    assert "sceneify_search_remote" in names
    assert "sceneify_set_presentation" in names
    assert "sceneify_apply" in names


def test_world_tools_set_presentation_merges_hdri_asset(tmp_path: Path) -> None:
    hdr = tmp_path / "sky.hdr"
    hdr.write_bytes(b"hdr")
    scene = Scene("lit")
    scene.set_presentation(title="Before", shadows=False, ambientIntensity=0.2)
    catalog = AssetCatalog(
        assets=[
            Asset(id="sky", path=str(hdr), format="hdr", tags=["hdri"]),
            Asset(id="prop", path="assets/prop.glb"),
        ]
    )
    tools = WorldTools(scene, catalog)
    result = tools.apply(
        {
            "action": "set_presentation",
            "asset": "sky",
            "shadows": True,
            "fog": {"color": "#112233", "near": 10, "far": 40},
        }
    )["result"]
    assert result["title"] == "Before"
    assert result["shadows"] is True
    assert result["environmentMap"] == str(hdr)
    assert result["ambientIntensity"] == 0.2
    assert scene.to_dict()["presentation"]["fog"]["near"] == 10

    with pytest.raises(ValueError, match="not an HDRI"):
        tools.apply({"action": "set_presentation", "asset": "prop"})


def test_world_tools_reject_unknown_action() -> None:
    tools = WorldTools(Scene(), AssetCatalog())
    with pytest.raises(ValueError, match="Unsupported world action"):
        tools.apply({"action": "invent_mesh"})


def test_world_tools_primitives_patch_and_roles(tmp_path: Path) -> None:
    tools = WorldTools(Scene("level"), AssetCatalog())
    tools.apply(
        {
            "action": "add_primitive",
            "id": "ground",
            "primitive": "plane",
            "size": [12, 1, 12],
            "material": {"color": "#344054"},
            "physics": {"body": "fixed", "collider": "cuboid"},
        }
    )
    tools.apply(
        {
            "action": "add_primitive",
            "id": "coin",
            "primitive": "sphere",
            "position": [1, 1, 0],
            "physics": {"body": "kinematic", "collider": "ball", "sensor": True},
        }
    )
    tools.apply({"action": "set_gameplay_role", "id": "coin", "role": "pickup"})
    tools.apply(
        {
            "action": "patch_node",
            "id": "coin",
            "patch": {"visible": True, "tags": ["pickup"]},
        }
    )
    listed = tools.apply({"action": "list_assets"})
    assert listed["result"]["count"] == 0
    assert listed["result"]["total"] == 0
    validated = tools.apply({"action": "validate_scene"})
    assert validated["result"]["graph"] == "ok"
    saved = tools.apply({"action": "save", "path": str(tmp_path / "level.sceneify.json")})
    assert Path(saved["result"]["path"]).is_file()
    scene = tools.scene.to_dict()
    assert scene["primitives"][1]["tags"] == ["pickup"]
    assert scene["game"]["collectibles"][0]["nodeId"] == "coin"


def test_world_tools_local_catalog_pagination() -> None:
    catalog = AssetCatalog(
        assets=[
            Asset(id="barrel-a", path="assets/barrel_a.glb", tags=["prop"]),
            Asset(id="barrel-b", path="assets/barrel_b.glb", tags=["prop"]),
            Asset(id="statue", path="assets/statue.glb", tags=["art"]),
        ]
    )
    tools = WorldTools(Scene(), catalog)
    page = tools.apply({"action": "search_assets", "query": "barrel", "pageOffset": 0, "limit": 1})[
        "result"
    ]
    assert page["total"] == 2
    assert page["count"] == 1
    assert page["hasMore"] is True
    assert page["assets"][0]["id"].startswith("barrel")
    next_page = tools.apply(
        {"action": "search_assets", "query": "barrel", "pageOffset": 1, "limit": 1}
    )["result"]
    assert next_page["hasMore"] is False
    assert next_page["count"] == 1


def test_world_tools_apply_many_stops_on_error() -> None:
    tools = WorldTools(Scene(), AssetCatalog())
    results = tools.apply_many(
        [
            {
                "action": "add_primitive",
                "id": "box",
                "primitive": "box",
            },
            {"action": "delete_node", "id": "missing"},
            {"action": "add_primitive", "id": "after", "primitive": "box"},
        ]
    )
    assert results[0]["ok"] is True
    assert results[1]["ok"] is False
    assert len(results) == 2
