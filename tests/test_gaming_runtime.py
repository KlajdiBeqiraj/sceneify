"""Tests for scene schema v2, editing, security, game manifests, and protocol v2."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sceneify import Game, Material, Physics, Scene, SemanticEvent
from sceneify.commands import CommandStack, RevisionConflict
from sceneify.io import SCENE_FORMAT
from sceneify.server import PROTOCOL_VERSION, create_app


def _minimal_glb() -> bytes:
    return struct.pack("<4sII", b"glTF", 2, 12)


def test_v1_migration_translates_children_to_parent_id(tmp_path: Path) -> None:
    document = {
        "format": SCENE_FORMAT,
        "version": 1,
        "scene": {
            "name": "legacy",
            "objects": [{"id": "root", "children": ["mesh"]}],
            "meshes": [{"id": "mesh", "source": "assets/mesh.glb"}],
        },
    }
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    scene = Scene.load(path)
    payload = scene.to_dict()
    assert payload["schemaVersion"] == 2
    assert payload["meshes"][0]["parentId"] == "root"
    assert "children" not in payload["objects"][0]
    assert Scene.from_dict(payload).to_dict() == payload


def test_graph_operations_and_validation() -> None:
    scene = Scene()
    scene.add_object("root")
    scene.create_primitive("box", "box", parent_id="root", tags=["solid"])
    scene.create_primitive("ball", "sphere", parent_id="box")

    duplicate = scene.duplicate_subtree("box", new_id="box_copy")
    assert duplicate["parentId"] == "root"
    assert scene.descendants("box_copy") == ["box_copy_ball"]
    with pytest.raises(ValueError, match="cycle"):
        scene.reparent("root", "ball")
    assert scene.to_dict()["objects"][0]["parentId"] is None

    world_before = scene._world_transform("ball")
    scene.reparent("ball", "root")
    assert scene._world_transform("ball") == world_before
    deleted = scene.delete_recursive("box")
    assert [node["id"] for node in deleted] == ["box"]


def test_material_physics_and_patch_are_explicit() -> None:
    scene = Scene()
    node = scene.create_primitive(
        "player",
        "capsule",
        material=Material("#00ff00", 0.5, True),
        physics=Physics("dynamic", "capsule", False, 2.0),
    )
    assert node.to_dict()["physics"]["body"] == "dynamic"
    scene.patch_node(
        "player",
        {
            "tags": ["player"],
            "material": {"color": "#fff", "opacity": 1, "wireframe": False},
        },
    )
    assert scene.to_dict()["primitives"][0]["tags"] == ["player"]


def test_annotation_can_be_anchored_to_a_graph_node() -> None:
    scene = Scene()
    scene.create_primitive("statue", "box", position=(3, 1, -2))
    annotation = scene.add_annotation(
        "statue_info",
        target_id="statue",
        offset=(0, 2, 0),
        label="Statue",
    )
    assert annotation.position == (3.0, 3.0, -2.0)
    payload = scene.to_dict()
    assert payload["annotations"][0]["targetId"] == "statue"
    assert payload["annotations"][0]["offset"] == [0.0, 2.0, 0.0]
    loaded = Scene.from_dict(payload)
    assert loaded.to_dict() == payload
    assert [item["id"] for item in loaded.delete_recursive("statue")] == [
        "statue",
        "statue_info",
    ]
    with pytest.raises(KeyError, match="Unknown annotation target"):
        scene.add_annotation("missing_info", target_id="missing", offset=(0, 1, 0))


def test_command_stack_all_operations_and_restart_determinism() -> None:
    scene = Scene()
    stack = CommandStack(scene)
    stack.execute({"action": "create", "id": "root", "primitive": "box"})
    stack.execute(
        {"action": "create", "id": "child", "primitive": "sphere", "parentId": "root"},
        expected_revision=1,
    )
    stack.execute({"action": "patch", "id": "child", "patch": {"visible": False}})
    stack.execute({"action": "reparent", "id": "child", "parentId": None})
    stack.execute({"action": "duplicate", "id": "root", "newId": "root_copy"})
    stack.execute({"action": "delete", "id": "root_copy"})
    final = scene.to_dict()

    for _ in range(6):
        stack.undo()
    assert scene.to_dict()["primitives"] == []
    for _ in range(6):
        stack.redo()
    assert scene.to_dict() == final
    with pytest.raises(RevisionConflict):
        stack.execute({"action": "delete", "id": "root"}, expected_revision=0)

    first = create_app(Scene.from_dict(final), realtime=False)
    second = create_app(Scene.from_dict(final), realtime=False)
    assert first.state.commands.snapshot() == second.state.commands.snapshot()


def test_gameplay_role_is_undoable_and_redoable() -> None:
    scene = Scene()
    scene.create_primitive("spawn", "capsule")
    stack = CommandStack(scene)
    stack.execute({"action": "set_gameplay_role", "id": "spawn", "role": "player-spawn"})
    assert scene.to_dict()["game"]["controllers"][0]["nodeId"] == "spawn"
    stack.undo()
    assert scene.to_dict()["game"] is None
    stack.redo()
    assert scene.to_dict()["game"]["cameras"][0]["targetId"] == "spawn"


def test_project_root_save_asset_upload_and_catalog(tmp_path: Path) -> None:
    app = create_app(Scene(), realtime=False, project_root=tmp_path)
    with TestClient(app) as client:
        saved = client.post("/api/scene/save", json={"path": "scenes/world.json"})
        assert saved.status_code == 200
        assert (tmp_path / "scenes/world.json").is_file()
        assert client.post("/api/scene/save", json={"path": "../escape.json"}).status_code == 400

        uploaded = client.post(
            "/api/assets/upload",
            files={"file": ("../safe model.glb", b"glTF", "model/gltf-binary")},
        )
        assert uploaded.status_code == 200
        assert uploaded.json()["asset"]["path"] == "assets/safe_model.glb"
        assert (tmp_path / "assets/safe_model.glb").read_bytes() == b"glTF"
        assert client.get("/api/asset", params={"path": "../escape.json"}).status_code == 404
        assert client.get("/api/asset", params={"path": "assets/safe_model.glb"}).status_code == 200

        catalog = client.get("/api/assets/catalog").json()
        assert catalog["assets"][0]["id"] == "safe_model"
        invalid = client.post(
            "/api/assets/import-glb",
            files={"file": ("model.txt", b"bad", "text/plain")},
        )
        assert invalid.status_code == 400


def test_controller_preset_ecctrl_roundtrip() -> None:
    scene = Scene()
    scene.create_primitive("player", "capsule")
    game = Game()
    game.add_controller(
        "player",
        preset="ecctrl",
        move_speed=4.5,
        jump_speed=6.5,
        sprint_mult=1.8,
    )
    game.follow_camera("player", distance=7.0, height=2.5)
    scene.set_game(game)
    controller = scene.to_dict()["game"]["controllers"][0]
    assert controller == {
        "nodeId": "player",
        "moveSpeed": 4.5,
        "jumpSpeed": 6.5,
        "actionMap": "default",
        "preset": "ecctrl",
        "sprintMult": 1.8,
    }
    loaded = Game.from_dict(scene.to_dict()["game"])
    assert loaded.controllers[0].preset == "ecctrl"
    assert loaded.controllers[0].sprint_mult == 1.8
    with pytest.raises(ValueError, match="preset"):
        game.add_controller("other", preset="fly")


def test_game_manifest_and_protocol_v2_semantic_event() -> None:
    scene = Scene()
    scene.create_primitive("player", "capsule")
    game = Game()
    game.action_map(moveForward=["KeyW"])
    game.add_controller("player")
    game.follow_camera("player")
    game.add_collectible("player")
    game.add_hazard("player")
    game.add_checkpoint("player")
    game.add_goal("player")
    game.set_hud(
        title="Test",
        description="A short game explanation.",
        controls_hint="Move: W",
    )
    game.set_timer(10)
    scene.set_game(game)
    events: list[SemanticEvent] = []

    @scene.on_event
    def receive_event(current: Scene, event: SemanticEvent) -> None:
        assert current is scene
        events.append(event)

    manifest = scene.to_dict()["game"]
    assert manifest["actionMaps"]["default"]["moveForward"] == ["KeyW"]
    assert manifest["controllers"][0]["nodeId"] == "player"
    assert manifest["controllers"][0]["preset"] == "simple"
    assert manifest["hud"]["description"] == "A short game explanation."
    assert manifest["hud"]["controlsHint"] == "Move: W"
    assert Game.from_dict(manifest).hud is not None
    assert Game.from_dict(manifest).hud.controls_hint == "Move: W"

    with (
        TestClient(create_app(scene, realtime=False)) as client,
        client.websocket_connect("/api/realtime") as socket,
    ):
        hello = socket.receive_json()
        assert hello["version"] == PROTOCOL_VERSION == 2
        assert hello["revision"] == 0
        assert "semanticEvents" in hello["capabilities"]
        socket.send_json({"type": "semantic_event", "name": "collect", "nodeId": "player"})
        assert socket.receive_json() == {"type": "event_ack", "name": "collect"}
        socket.send_json(
            {
                "type": "command",
                "revision": 0,
                "command": {"action": "patch", "id": "player", "patch": {"visible": False}},
            }
        )
        ack = socket.receive_json()
        assert ack["type"] == "command_ack"
        assert ack["revision"] == 1
        socket.send_json({"type": "resync"})
        snapshot = socket.receive_json()
        assert snapshot["type"] == "snapshot"
        assert snapshot["revision"] == 1

    assert events[0].name == "collect"


def test_frontend_v2_payloads_and_revision_guards(tmp_path: Path) -> None:
    app = create_app(Scene(), realtime=False, project_root=tmp_path)
    with TestClient(app) as client:
        created = client.post(
            "/api/scene/commands",
            json={"command": "create_primitive", "revision": 0, "primitive": "box"},
        )
        assert created.status_code == 200
        assert created.json()["result"]["id"] == "box"
        assert created.json()["commandId"] == "command-1"
        assert created.json()["scene"]["revision"] == 1

        asset = client.post(
            "/api/scene/commands",
            json={
                "command": "create_asset",
                "revision": 1,
                "assetId": "tree",
                "source": "assets/tree.glb",
            },
        )
        assert asset.status_code == 200
        assert asset.json()["result"]["kind"] == "mesh"
        assert asset.json()["result"]["id"] == "tree"

        player = client.post(
            "/api/scene/commands",
            json={
                "command": "set_gameplay_role",
                "revision": 2,
                "id": "box",
                "role": "player-spawn",
            },
        )
        assert player.status_code == 200
        game = player.json()["scene"]["game"]
        assert game["controllers"][0]["nodeId"] == "box"
        assert game["cameras"][0]["targetId"] == "box"

        pickup = client.post(
            "/api/scene/commands",
            json={
                "command": "set_gameplay_role",
                "revision": 3,
                "id": "box",
                "role": "pickup",
            },
        )
        game = pickup.json()["scene"]["game"]
        assert game["controllers"] == []
        assert game["cameras"] == []
        assert game["collectibles"][0]["nodeId"] == "box"

        patched = client.patch(
            "/api/nodes/box",
            json={
                "revision": 4,
                "material": {
                    "color": "#abcdef",
                    "opacity": 0.8,
                    "wireframe": False,
                    "roughness": 0.25,
                    "metalness": 0.75,
                },
            },
        )
        assert patched.status_code == 200
        material = patched.json()["result"]["material"]
        assert material["roughness"] == 0.25
        assert material["metalness"] == 0.75
        assert (
            Scene.from_dict(patched.json()["scene"]).to_dict()["primitives"][0]["material"]
            == material
        )

        stale_import = client.post(
            "/api/assets/import",
            files={"file": ("crate.glb", _minimal_glb(), "model/gltf-binary")},
            data={"revision": "4"},
        )
        assert stale_import.status_code == 409
        assert not (tmp_path / "assets/crate.glb").exists()

        imported = client.post(
            "/api/assets/import",
            files={"file": ("crate.glb", _minimal_glb(), "model/gltf-binary")},
            data={"revision": "5"},
        )
        assert imported.status_code == 200
        assert imported.json()["revision"] == 6

        catalog = client.get("/api/assets").json()
        assert catalog[0]["name"] == "crate"
        assert catalog[0]["source"] == catalog[0]["path"]

        stale_save = client.post(
            "/api/scene/save",
            json={"path": "scene.json", "revision": 5},
        )
        assert stale_save.status_code == 409
        assert not (tmp_path / "scene.json").exists()
        saved = client.post(
            "/api/scene/save",
            json={"path": "scene.json", "revision": 6},
        )
        assert saved.status_code == 200
        assert saved.json()["revision"] == 6

        snapshot = client.get("/api/scene/snapshot").json()
        assert snapshot["scene"]["revision"] == snapshot["revision"] == 6


def test_typed_project_catalog_filters_paths_and_unique_glb_import(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "tree.glb").write_bytes(_minimal_glb())
    (tmp_path / "assets.catalog.json").write_text(
        json.dumps(
            {
                "format": "sceneify-asset-catalog",
                "version": 2,
                "assets": [
                    {
                        "id": "tree",
                        "path": "assets/tree.glb",
                        "format": "glb",
                        "license": "CC0",
                        "byteSize": 12,
                        "animations": ["sway"],
                        "tags": ["nature"],
                        "metadata": {"author": "Sceneify"},
                    },
                    {
                        "id": "robot",
                        "source": "https://example.com/robot.glb",
                        "format": "glb",
                        "tags": ["character"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with TestClient(create_app(Scene(), realtime=False, project_root=tmp_path)) as client:
        catalog = client.get("/api/assets/catalog", params={"tag": "nature"}).json()
        assert catalog["version"] == 2
        assert [asset["id"] for asset in catalog["assets"]] == ["tree"]
        assert catalog["assets"][0]["source"] == "assets/tree.glb"
        assert catalog["assets"][0]["license"] == "CC0"
        search_results = client.get("/api/assets", params={"q": "robot"}).json()
        assert [asset["id"] for asset in search_results] == ["robot"]

        invalid = client.post(
            "/api/assets/import-glb",
            files={"file": ("broken.glb", b"glTF", "model/gltf-binary")},
        )
        assert invalid.status_code == 400
        first = client.post(
            "/api/assets/import-glb",
            files={"file": ("tree.glb", _minimal_glb(), "model/gltf-binary")},
        )
        assert first.status_code == 200
        assert first.json()["asset"]["path"] == "assets/tree-1.glb"

        (tmp_path / "assets.catalog.json").write_text(
            json.dumps(
                {
                    "format": "sceneify-asset-catalog",
                    "version": 2,
                    "assets": [{"id": "escape", "path": "../outside.glb"}],
                }
            ),
            encoding="utf-8",
        )
        assert client.get("/api/assets").status_code == 400
