"""Checks for the asset-backed public showcase scenes."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from examples.collect_escape import build_scene as build_game  # noqa: E402
from examples.roman_environment import build_scene as build_roman  # noqa: E402


def test_collect_escape_uses_animated_glb_visuals() -> None:
    scene = build_game().to_dict()
    player = next(node for node in scene["meshes"] if node["id"] == "player_visual")
    assert player["meta"]["visualFor"] == "player"
    assert player["meta"]["animation"]["states"]["run"] == "Running_A"
    assert (
        next(node for node in scene["primitives"] if node["id"] == "player")["meta"][
            "renderPrimitive"
        ]
        is False
    )
    assert (ROOT / player["source"]).read_bytes()[:4] == b"glTF"
    floors = [node for node in scene["meshes"] if node["id"].startswith("floor_")]
    assert len(floors) >= 20
    assert all(node["source"].endswith("floor_tile_large.glb") for node in floors)
    assert scene["presentation"]["environmentPreset"] == "sunset"
    colliders = [
        node
        for node in scene["primitives"]
        if "collider" in node.get("tags", []) or node["id"].startswith("wall_")
    ]
    assert all(node["meta"].get("renderPrimitive") is False for node in colliders)
    hazard = next(node for node in scene["primitives"] if node["id"] == "hazard")
    assert hazard["meta"].get("renderPrimitive") is False
    assert hazard["position"][0] > 0
    pit = next(node for node in scene["primitives"] if node["id"] == "hazard_pit_visual")
    assert pit["meta"].get("renderPrimitive") is not False
    checkpoint = next(node for node in scene["primitives"] if node["id"] == "checkpoint")
    assert checkpoint["meta"].get("renderPrimitive") is False
    goal = next(node for node in scene["primitives"] if node["id"] == "goal")
    assert goal["meta"].get("renderPrimitive") is False
    assert any(node["id"] == "goal_chest" for node in scene["meshes"])
    assert {item["nodeId"] for item in scene["game"]["collectibles"]} == {
        "coin_1",
        "coin_2",
        "coin_3",
    }
    assert next(node for node in scene["meshes"] if node["id"] == "player_visual")[
        "scale"
    ][1] == 0.78


def test_roman_showcase_has_local_presentation_and_interactive_pois() -> None:
    scene = build_roman().to_dict()
    assert scene["presentation"]["environmentMap"].endswith("colosseum_1k.hdr")
    assert scene["presentation"]["grid"] is False
    assert len(scene["annotations"]) == 4
    assert {annotation["targetId"] for annotation in scene["annotations"]} == {
        "broken_arch",
        "central_fountain",
        "marble_bust",
        "horse_statue",
    }
    bust_poi = next(item for item in scene["annotations"] if item["id"] == "poi_bust")
    assert bust_poi["offset"] == [0.0, 1.95, 0.0]
    assert all(
        annotation["meta"]["interaction"]["clickEvent"] == "poi_selected"
        for annotation in scene["annotations"]
    )
    for mesh in scene["meshes"]:
        asset = ROOT / mesh["source"]
        assert asset.is_file()
        assert asset.stat().st_size < 10 * 1024 * 1024


def test_demo_asset_budget_stays_under_twenty_megabytes() -> None:
    total = sum(
        path.stat().st_size for path in (ROOT / "examples" / "assets").rglob("*") if path.is_file()
    )
    assert total < 20 * 1024 * 1024
