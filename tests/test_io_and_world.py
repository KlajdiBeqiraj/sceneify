"""Tests for save/load and place_on_world."""

from __future__ import annotations

from pathlib import Path

from sceneify.scene import Scene


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    scene = Scene("roundtrip")
    env = scene.set_environment(bounds_min=(-2, 0, -2), bounds_max=(2, 2, 2), snap=None)
    env.set_world_glb("/tmp/fake-world.glb", position=(0, 0, 0))
    scene.add_annotation("a", position=(0.5, 0.2, 0.1), label="hi")
    path = tmp_path / "world.sceneify.json"
    scene.save(path)

    loaded = Scene.load(path)
    assert loaded.name == "roundtrip"
    assert loaded.environment is not None
    assert loaded.environment.world_mesh is not None
    assert loaded.environment.world_mesh.source.endswith("fake-world.glb")
    assert loaded.to_dict()["annotations"][0]["label"] == "hi"


def test_update_node_and_place_on_world() -> None:
    scene = Scene("place")
    scene.set_environment(bounds_min=(-5, 0, -5), bounds_max=(5, 5, 5), ground_y=1.5, snap=None)
    mesh = scene.place_on_world("m", "prop.glb", x=1.0, z=2.0, offset_y=0.25)
    assert mesh.position[0] == 1.0
    assert mesh.position[1] == 1.75
    assert mesh.position[2] == 2.0
    scene.update_node("m", position=(0.0, 1.5, 0.0))
    assert scene.to_dict()["meshes"][0]["position"] == [0.0, 1.5, 0.0]
