"""Tests for agent-facing scene perception helpers."""

from __future__ import annotations

import json
import struct
from pathlib import Path

from sceneify.objects import Material, Physics
from sceneify.perception import (
    describe_scene,
    get_bounds,
    get_node,
    list_nodes,
    spatial_query,
    topdown_map,
)
from sceneify.scene import Scene


def _minimal_glb(tmp_path: Path) -> Path:
    """Write a tiny GLB whose JSON accessors advertise a 2x2x2 box."""
    gltf = {
        "asset": {"version": "2.0"},
        "accessors": [{"type": "VEC3", "min": [-1, -1, -1], "max": [1, 1, 1]}],
    }
    json_bytes = json.dumps(gltf).encode("utf-8")
    json_pad = (4 - (len(json_bytes) % 4)) % 4
    json_bytes += b" " * json_pad
    bin_chunk = b"\x00\x00\x00\x00"
    total = 12 + 8 + len(json_bytes) + 8 + len(bin_chunk)
    data = bytearray()
    data += struct.pack("<4sII", b"glTF", 2, total)
    data += struct.pack("<I4s", len(json_bytes), b"JSON")
    data += json_bytes
    data += struct.pack("<I4s", len(bin_chunk), b"BIN\x00")
    data += bin_chunk
    path = tmp_path / "box.glb"
    path.write_bytes(data)
    return path


def _sample_scene(tmp_path: Path | None = None) -> Scene:
    scene = Scene("perception-demo")
    scene.set_environment(bounds_min=(-10, 0, -10), bounds_max=(10, 8, 10), ground_y=0)
    scene.set_presentation(camera={"position": [8, 6, 10], "target": [0, 0, 0], "fov": 50})
    scene.create_primitive(
        "ground",
        "box",
        size=(20, 0.2, 20),
        position=(0, -0.1, 0),
        material=Material("#38533a"),
        physics=Physics(body="fixed", collider="cuboid"),
        tags=["ground"],
    )
    scene.add_object("house", label="House", position=(-4, 0, 2), tags=["house"])
    scene.create_primitive(
        "wall",
        "box",
        size=(2, 2, 0.2),
        position=(0, 1, 0),
        parent_id="house",
        tags=["wall"],
    )
    scene.create_primitive(
        "player",
        "capsule",
        position=(0, 1, 6),
        radius=0.3,
        height=0.8,
        tags=["player"],
    )
    scene.create_primitive(
        "exit",
        "box",
        size=(2, 2, 1),
        position=(0, 1, -8),
        tags=["goal"],
    )
    scene.add_annotation("poi", target_id="house", label="Door", offset=(0, 2, 0))
    if tmp_path is not None:
        glb = _minimal_glb(tmp_path)
        scene.add_mesh("crate", str(glb), position=(3, 0, 0), scale=(1, 1, 1), tags=["prop"])
    return scene


def test_world_transform_accumulates_parent_chain() -> None:
    scene = _sample_scene()
    local = scene._primitives["wall"]
    assert list(local.position) == [0.0, 1.0, 0.0]
    world = scene.world_transform("wall")
    assert world["position"] == [-4.0, 1.0, 2.0]
    assert world["rotation"] == [0.0, 0.0, 0.0]


def test_describe_scene_summary_lists_roots_and_tree() -> None:
    scene = _sample_scene()
    overview = describe_scene(scene, detail="summary")
    assert overview["name"] == "perception-demo"
    assert overview["counts"]["primitives"] >= 3
    assert overview["environment"]["boundsMin"] == [-10.0, 0.0, -10.0]
    assert "house" in overview["tree"]
    assert "  wall" in overview["tree"]
    root_ids = {node["id"] for node in overview["nodes"]}
    assert "house" in root_ids
    assert "wall" not in root_ids
    house = next(node for node in overview["nodes"] if node["id"] == "house")
    assert house["world"]["position"] == [-4.0, 0.0, 2.0]


def test_get_node_includes_world_pose_bounds_and_annotations() -> None:
    scene = _sample_scene()
    payload = get_node(scene, "wall")
    assert payload["world"]["position"] == [-4.0, 1.0, 2.0]
    assert payload["bounds"]["method"] == "primitive"
    assert payload["bounds"]["size"][1] == 2.0

    house = get_node(scene, "house")
    assert house["anchoredAnnotations"][0]["id"] == "poi"
    assert house["anchoredAnnotations"][0]["worldPosition"] == [-4.0, 2.0, 2.0]


def test_list_nodes_filters_and_paginates() -> None:
    scene = _sample_scene()
    page = list_nodes(scene, tag="player", limit=10)
    assert page["total"] == 1
    assert page["nodes"][0]["id"] == "player"
    page2 = list_nodes(scene, kind="primitive", page_offset=0, limit=2)
    assert page2["count"] == 2
    assert page2["hasMore"] is True


def test_spatial_query_nearest_relative_and_height() -> None:
    scene = _sample_scene()
    nearest = spatial_query(scene, mode="nearest", id="player", k=2)
    assert nearest["results"][0]["id"] in {"ground", "house", "exit", "wall"}
    relative = spatial_query(scene, mode="relative", from_id="player", to_id="exit")
    assert relative["bearing"] == "north"
    assert relative["distance"] > 10
    height = spatial_query(scene, mode="height_at", x=0, z=0)
    assert height["y"] == 0.0


def test_topdown_map_marks_player_and_goal() -> None:
    scene = _sample_scene()
    mapped = topdown_map(scene, cell_size=2.0, max_cells=20)
    assert "P" in mapped["ascii"]
    assert "X" in mapped["ascii"]
    assert mapped["axes"]["north"] == "-Z"
    assert any("player" in ids or "exit" in ids for ids in mapped["cells"].values())


def test_get_bounds_mesh_from_glb_accessors(tmp_path: Path) -> None:
    scene = _sample_scene(tmp_path)
    bounds = get_bounds(scene, "crate")
    assert bounds["method"] == "glb_accessors"
    assert bounds["size"] == [2.0, 2.0, 2.0]
    scene_aabb = get_bounds(scene)
    assert scene_aabb["scope"] == "scene"
    assert scene_aabb["size"][0] >= 20.0
