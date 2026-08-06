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
    assert scene["presentation"]["environmentPreset"] == "night"
    player_node = next(node for node in scene["primitives"] if node["id"] == "player")
    assert abs(player_node["position"][1] - 0.75) < 1e-6
    ground_slabs = [node for node in scene["primitives"] if node["id"].startswith("ground_")]
    assert len(ground_slabs) >= 20
    assert all(node["physics"]["collider"] == "cuboid" for node in ground_slabs)
    # Pit cells keep visuals missing and no physics slab under the kill volume.
    assert not any(node["id"] in {"ground_0_0", "ground_1_0"} for node in ground_slabs)
    assert not any(node["id"] in {"floor_0_0", "floor_1_0"} for node in scene["meshes"])
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
    pad = next(node for node in scene["primitives"] if node["id"] == "checkpoint_pad")
    assert pad["material"]["opacity"] < 1
    assert pad["meta"].get("renderPrimitive") is not False
    assert not any(node["id"].startswith("checkpoint_pillar") for node in scene["meshes"])
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
    enemy_kinds = {item["kind"] for item in scene["game"]["enemies"]["types"]}
    assert enemy_kinds == {"knight", "mage"}
    assert len(scene["game"]["enemies"]["spawnPoints"]) >= 4
    for enemy in scene["game"]["enemies"]["types"]:
        assert (ROOT / enemy["source"]).is_file()
        assert int(enemy.get("health", 0)) >= 1
    assert "attack" in next(
        node for node in scene["meshes"] if node["id"] == "player_visual"
    )["meta"]["animation"]["states"]


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
    tour = scene["presentation"]["cameraTour"]
    assert tour["autoplay"] is True
    assert tour["loop"] is True
    assert len(tour["stops"]) >= 6
    assert any(stop.get("annotationId") == "poi_fountain" for stop in tour["stops"])
    assert any(stop.get("spotlight") for stop in tour["stops"])
    assert any((stop.get("lightScale") or 1) < 0.5 for stop in tour["stops"])
    for mesh in scene["meshes"]:
        asset = ROOT / mesh["source"]
        assert asset.is_file()
        assert asset.stat().st_size < 10 * 1024 * 1024


def test_demo_asset_budget_stays_under_twenty_megabytes() -> None:
    total = sum(
        path.stat().st_size for path in (ROOT / "examples" / "assets").rglob("*") if path.is_file()
    )
    assert total < 20 * 1024 * 1024
