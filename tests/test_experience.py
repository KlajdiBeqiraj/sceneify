"""Experience manifest, board DSL, and character objectives."""

from __future__ import annotations

from sceneify import BoardPick, ExperienceManifest, Game, Scene
from sceneify.experience import character_payload
from sceneify.realtime import SemanticEvent


def test_game_sugar_wraps_character_experience() -> None:
    scene = Scene("ruins")
    scene.create_primitive("player", "capsule")
    game = Game()
    game.add_controller("player")
    game.add_collectible("player")
    scene.set_game(game)
    payload = scene.to_dict()
    assert "game" not in payload
    experience = payload["experience"]
    assert experience["family"] == "character"
    assert experience["runtimeSlot"] == "character_world"
    assert experience["interaction"]["primary"] == "overlap"
    assert character_payload(payload)["controllers"][0]["nodeId"] == "player"


def test_present_and_board_experiences() -> None:
    present = ExperienceManifest.present(title="Hall").to_dict()
    assert present["runtimeSlot"] == "present"
    assert present["hud"]["enabled"] is False
    board = ExperienceManifest.board(rows=3, cols=3, title="Tokens").to_dict()
    assert board["runtimeSlot"] == "tabletop"
    assert board["interaction"]["primary"] == "cell_pick"
    assert board["tabletop"]["rows"] == 3


def test_board_sandbox_pick_moves_piece() -> None:
    scene = Scene("table")
    board = scene.add_board(size=(3, 3), cell_size=1.0, title="Tokens")
    board.place("token", cell=(0, 0), owner="P1")
    assert board.piece_at((0, 0)) == "token"
    board._handle_event(scene, SemanticEvent(name="node_picked", node_id="token"))
    assert board.selected_id == "token"
    assert (2, 2) in board.highlights
    board._handle_event(scene, SemanticEvent(name="node_picked", node_id=board.cell_id((2, 2))))
    assert board.piece_at((2, 2)) == "token"
    assert board.piece_at((0, 0)) is None
    assert board.turn == 1
    pos = scene._primitives["token"].position
    expected = board.cell_position((2, 2), y=board.origin[1] + 0.28)
    assert abs(pos[0] - expected[0]) < 1e-6
    assert abs(pos[2] - expected[2]) < 1e-6


def test_board_end_and_custom_on_pick() -> None:
    scene = Scene("custom")
    board = scene.add_board(size=(2, 2), title="Short")
    board.place("a", cell=(0, 0))
    seen: list[BoardPick] = []

    @board.on_pick
    def handle(current, pick):
        seen.append(pick)
        current.end("win", "Done")

    board._handle_event(scene, SemanticEvent(name="node_picked", node_id="a"))
    assert seen[0].kind == "piece"
    assert scene.to_dict()["experience"]["match"]["phase"] == "won"
    assert scene.to_dict()["experience"]["hud"]["winMessage"] == "Done"


def test_character_objectives_collect_and_reach() -> None:
    scene = Scene("dungeon")
    scene.create_primitive("ground", "box", size=(8, 0.2, 8), tags=["ground"])
    scene.create_primitive("relic_1", "sphere", tags=["pickup"])
    scene.create_primitive("exit", "box", tags=["goal"])
    play = scene.character(preset="third_person")
    play.hud(title="Find the relic", hint="WASD")
    play.objective("collect", need=1)
    play.objective("reach", node_id="exit", need=1)
    payload = character_payload(scene.to_dict())
    assert payload["collectibles"][0]["nodeId"] == "relic_1"
    assert payload["goals"][0]["nodeId"] == "exit"
    assert payload["goals"][0]["requiredScore"] == 1
    assert scene.to_dict()["experience"]["family"] == "character"
    assert scene.to_dict()["experience"]["objectives"][-1]["kind"] == "reach"


def test_legacy_game_payload_wraps_on_load() -> None:
    scene = Scene.from_dict(
        {
            "name": "legacy",
            "background": "#000",
            "meshes": [],
            "objects": [],
            "primitives": [],
            "annotations": [],
            "trajectories": [],
            "game": {
                "controllers": [{"nodeId": "p", "moveSpeed": 5, "jumpSpeed": 7}],
                "cameras": [],
                "collectibles": [],
                "hazards": [],
                "checkpoints": [],
                "goals": [],
            },
        }
    )
    assert scene.to_dict()["experience"]["runtimeSlot"] == "character_world"
    assert character_payload(scene.to_dict())["controllers"][0]["nodeId"] == "p"


def test_board_place_source_spawns_mesh_piece(tmp_path) -> None:
    glb = tmp_path / "token.glb"
    glb.write_bytes(b"glTF" + b"\x00" * 8)
    scene = Scene("table")
    board = scene.add_board(size=(2, 2), title="Tokens")
    payload = board.place("hero", cell=(0, 0), owner="P1", source=glb, scale=(0.4, 0.4, 0.4))
    assert payload["id"] == "hero"
    mesh = next(item for item in scene.to_dict()["meshes"] if item["id"] == "hero")
    assert mesh["source"].endswith("token.glb")
    assert mesh["meta"]["boardRole"] == "piece"
    assert mesh["meta"]["cell"] == [0, 0]
    assert board.piece_at((0, 0)) == "hero"
    board.move("hero", (1, 1))
    assert board.piece_at((1, 1)) == "hero"
    assert abs(scene._meshes["hero"].position[1] - mesh["position"][1]) < 1e-6


def test_board_place_catalog_asset(tmp_path, monkeypatch) -> None:
    from sceneify.catalog import Asset, AssetCatalog

    monkeypatch.chdir(tmp_path)
    glb = tmp_path / "mage.glb"
    glb.write_bytes(b"glTF" + b"\x00" * 8)
    AssetCatalog(assets=[Asset(id="kaykit-mage", path=str(glb), format="glb")]).save(
        tmp_path / "assets.catalog.json"
    )
    scene = Scene("table")
    board = scene.add_board(size=(2, 2))
    board.place("mage", cell=(1, 0), asset="kaykit-mage")
    mesh = next(item for item in scene.to_dict()["meshes"] if item["id"] == "mage")
    assert mesh["meta"]["catalog_asset"] == "kaykit-mage"
    assert board.piece_at((1, 0)) == "mage"
