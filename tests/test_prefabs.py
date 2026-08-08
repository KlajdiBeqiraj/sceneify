"""Tests for reusable prefabs with overrides."""

from __future__ import annotations

from pathlib import Path

import pytest

from sceneify import Prefab, Scene, load_schema
from sceneify.commands import CommandStack
from sceneify.objects import Material, Physics


def _crate_prototype(scene: Scene) -> None:
    scene.create_primitive(
        "body",
        "box",
        position=(0, 0.5, 0),
        size=(1, 1, 1),
        material=Material(color="#c27a3a", roughness=0.8),
        physics=Physics(body="dynamic", collider="cuboid", mass=2.0),
        tags=["prop"],
    )
    scene.create_primitive(
        "lid",
        "box",
        parent_id="body",
        position=(0, 0.6, 0),
        size=(1.05, 0.1, 1.05),
        material=Material(color="#8b5a2b"),
        tags=["prop", "lid"],
    )


def test_define_instantiate_overrides_and_roundtrip(tmp_path: Path) -> None:
    scene = Scene("prefabs")
    _crate_prototype(scene)
    prefab = scene.define_prefab(
        "crate",
        from_node="body",
        label="Wooden crate",
        game_roles={"body": "pickup"},
    )
    assert prefab.root_id == "crate"
    assert prefab.label == "Wooden crate"
    assert "lid" in prefab.nodes()
    assert prefab.game_roles["crate"] == "pickup"

    root = scene.instantiate(
        "crate",
        id="crate_a",
        position=(2, 0, 1),
        rotation=(0, 45, 0),
        overrides={
            "material": {"color": "#ffaa00"},
            "physics": {"mass": 5.0},
            "tags": ["prop", "loot"],
            "meta": {"value": 3},
            "nodes": {"lid": {"material": {"color": "#111111"}, "visible": False}},
        },
    )
    assert root["id"] == "crate_a"
    assert root["position"] == [2.0, 0.0, 1.0]
    assert root["rotation"] == [0.0, 45.0, 0.0]
    assert root["material"]["color"] == "#ffaa00"
    assert root["material"]["roughness"] == 0.8
    assert root["physics"]["mass"] == 5.0
    assert root["physics"]["body"] == "dynamic"
    assert root["tags"] == ["prop", "loot"]
    assert root["meta"]["value"] == 3
    assert root["meta"]["prefab"] == "crate"
    assert root["meta"]["prefabRoot"] == "crate_a"

    lid = scene._primitives["crate_a_lid"]
    assert lid.material is not None
    assert lid.material.color == "#111111"
    assert lid.visible is False
    assert lid.parent_id == "crate_a"

    game = scene.to_dict()["game"]
    assert game is not None
    assert any(item["nodeId"] == "crate_a" for item in game["collectibles"])

    path = scene.save(tmp_path / "prefab_scene.json")
    loaded = Scene.load(path)
    assert loaded.list_prefabs() == ["crate"]
    assert loaded.get_prefab("crate").label == "Wooden crate"
    assert "crate_a" in loaded._primitives
    assert loaded._primitives["crate_a"].material is not None
    assert loaded._primitives["crate_a"].material.color == "#ffaa00"


def test_game_role_override_and_unknown_prefab() -> None:
    scene = Scene("roles")
    scene.create_primitive("hazard_box", "box", position=(0, 0.5, 0))
    scene.define_prefab("spike", from_node="hazard_box", game_roles={"hazard_box": "hazard"})
    scene.instantiate("spike", id="spike_1", overrides={"game_role": "checkpoint"})
    game = scene.to_dict()["game"]
    assert game is not None
    assert any(item["nodeId"] == "spike_1" for item in game["checkpoints"])
    assert not any(item["nodeId"] == "spike_1" for item in game["hazards"])

    with pytest.raises(KeyError, match="Unknown prefab"):
        scene.instantiate("missing")
    with pytest.raises(ValueError, match="already exists"):
        scene.define_prefab("spike", from_node="hazard_box")


def test_child_override_unknown_node_and_duplicate_instance_id() -> None:
    scene = Scene("errors")
    scene.create_primitive("body", "box")
    scene.define_prefab("crate", from_node="body")
    scene.instantiate("crate", id="crate_a")
    with pytest.raises(ValueError, match="already has a node"):
        scene.instantiate("crate", id="crate_a")
    with pytest.raises(KeyError, match="no node"):
        scene.instantiate(
            "crate",
            id="crate_b",
            overrides={"nodes": {"missing": {"visible": False}}},
        )


def test_prefab_schema_and_command_stack() -> None:
    schema = load_schema("scene")
    assert "prefab" in schema["$defs"]
    assert "prefabs" in schema["$defs"]["scene"]["properties"]

    scene = Scene("commands")
    scene.create_primitive("body", "box", position=(0, 0.5, 0))
    scene.create_primitive("lid", "box", parent_id="body", position=(0, 0.6, 0))
    stack = CommandStack(scene)
    stack.execute(
        {
            "action": "definePrefab",
            "id": "crate",
            "fromNode": "body",
            "label": "Crate",
            "gameRoles": {"body": "pickup"},
        }
    )
    ack = stack.execute(
        {
            "action": "instantiatePrefab",
            "prefabId": "crate",
            "id": "crate_cmd",
            "position": [3, 0, 0],
            "overrides": {"tags": ["from-command"]},
        }
    )
    assert ack["result"]["id"] == "crate_cmd"
    assert ack["result"]["tags"] == ["from-command"]
    assert "crate" in ack["scene"]["prefabs"][0]["id"]
    stack.undo()
    assert "crate_cmd" not in scene._graph_nodes()
    assert scene.list_prefabs() == ["crate"]
    stack.undo()
    assert scene.list_prefabs() == []


def test_prefab_from_dict_validation() -> None:
    with pytest.raises(ValueError, match="rootId"):
        Prefab.from_dict(
            {
                "id": "broken",
                "rootId": "missing",
                "meshes": [],
                "objects": [],
                "primitives": [],
                "gameRoles": {},
            }
        )
