"""Build a self-contained collect-and-escape game scene."""

from __future__ import annotations

import argparse
from pathlib import Path

from sceneify import Game, Material, Physics, Scene

# KayKit Dungeon Remastered measured AABB sizes (meters at scale 1).
FLOOR_TILE = 4.0
BARREL = (1.8, 2.0, 1.8)
CHEST = (1.7, 1.21, 1.91)

KAYKIT = "examples/assets/kaykit"


def _invisible(**meta: object) -> dict:
    return {"renderPrimitive": False, **meta}


def build_scene() -> Scene:
    scene = Scene("Collect and Escape", background="#1c2438")
    scene.set_presentation(
        grid=False,
        helpers=False,
        shadows=True,
        exposure=1.28,
        environmentPreset="sunset",
        fog={"color": "#243044", "near": 32, "far": 64},
        camera={"position": [0, 10, 18], "target": [0, 1, 0], "fov": 46},
        title="Collect & Escape",
        subtitle="A third-person browser game authored entirely from Python",
    )

    # Invisible physics ground; visuals come from floor_tile_large GLBs.
    scene.create_primitive(
        "ground",
        "plane",
        size=(24, 0.2, 36),
        position=(0, 0, -2),
        material=Material("#3d4658", roughness=1.0),
        physics=Physics(body="fixed", collider="cuboid"),
        tags=["ground"],
        **_invisible(),
    )

    # Floor tiles form a readable dungeon corridor (4x4 KayKit tiles).
    # Leave a center-right pit so the hazard reads as a shortcut, not a wall.
    hazard_tiles = {(0, 0), (1, 0)}
    for x_index in range(-2, 3):
        for z_index in range(-4, 4):
            if (x_index, z_index) in hazard_tiles:
                continue
            scene.add_glb(
                f"floor_{x_index}_{z_index}",
                f"{KAYKIT}/floor_tile_large.glb",
                position=(x_index * FLOOR_TILE, 0, z_index * FLOOR_TILE),
                scale=(1, 1, 1),
                tags=["architecture", "ground"],
            )

    # Player: invisible capsule collider + skinned knight visual.
    # KayKit Adventure knight is ~2m at scale 1; 0.78 keeps props readable.
    player_y = 0.78
    knight_scale = 0.78
    scene.create_primitive(
        "player",
        "capsule",
        position=(0, player_y, 10),
        radius=0.38,
        height=0.9,
        material=Material("#53b1fd"),
        physics=Physics(body="dynamic", collider="capsule", mass=1),
        tags=["player"],
        **_invisible(),
    )
    scene.add_glb(
        "player_visual",
        f"{KAYKIT}/knight.glb",
        parent_id="player",
        position=(0, -player_y, 0),
        scale=(knight_scale, knight_scale, knight_scale),
        apply_environment=False,
        visualFor="player",
        animation={
            "autoplay": "Idle",
            "states": {
                "idle": "Idle",
                "move": "Walking_A",
                "run": "Running_A",
                "jump": "Jump_Full_Short",
            },
            "fadeSeconds": 0.16,
        },
    )

    # Perimeter colliders (invisible) sized to match wall visuals.
    for node_id, position, size in (
        ("wall_left", (-10.25, 2.0, -2.0), (1.0, 4.0, 32.0)),
        ("wall_right", (10.25, 2.0, -2.0), (1.0, 4.0, 32.0)),
        ("wall_south", (0.0, 2.0, 14.25), (20.0, 4.0, 1.0)),
        ("wall_north_left", (-6.0, 2.0, -14.25), (8.0, 4.0, 1.0)),
        ("wall_north_right", (6.0, 2.0, -14.25), (8.0, 4.0, 1.0)),
    ):
        scene.create_primitive(
            node_id,
            "box",
            position=position,
            size=size,
            material=Material("#475467"),
            physics=Physics(body="fixed", collider="cuboid"),
            tags=["obstacle", "collider"],
            **_invisible(),
        )

    # Side wall visuals: one 4-unit panel every tile along the corridor.
    for side, x, yaw in (("left", -10.0, 1.5708), ("right", 10.0, -1.5708)):
        for index, z in enumerate(range(-14, 14, 4)):
            scene.add_glb(
                f"{side}_wall_{index}",
                f"{KAYKIT}/wall_broken.glb",
                position=(x, 0, z),
                rotation=(0, yaw, 0),
                scale=(1, 1, 1),
                tags=["architecture"],
            )

    # North gate visuals with a clear center exit.
    scene.add_glb(
        "gate_arch_left",
        f"{KAYKIT}/wall_arched.glb",
        position=(-4.0, 0, -14.0),
        scale=(1, 1, 1),
        tags=["architecture"],
    )
    scene.add_glb(
        "gate_arch_right",
        f"{KAYKIT}/wall_broken.glb",
        position=(4.0, 0, -14.0),
        rotation=(0, 3.1416, 0),
        scale=(1, 1, 1),
        tags=["architecture"],
    )
    for node_id, x in (("pillar_gate_l", -2.2), ("pillar_gate_r", 2.2)):
        scene.add_glb(
            node_id,
            f"{KAYKIT}/pillar.glb",
            position=(x, 0, -13.2),
            scale=(0.85, 0.85, 0.85),
            tags=["architecture"],
        )

    # Path blockers: collider first, matching GLB visual second.
    blockers = (
        (
            "cover_barrel_a",
            (-5.2, 0.85, 4.5),
            (BARREL[0] * 0.65, BARREL[1] * 0.65, BARREL[2] * 0.65),
            "barrel_large.glb",
            (-5.2, 0.0, 4.5),
            (0.65, 0.65, 0.65),
            (0, 0.35, 0),
        ),
        (
            "cover_barrel_b",
            (5.5, 0.85, -5.5),
            (BARREL[0] * 0.65, BARREL[1] * 0.65, BARREL[2] * 0.65),
            "barrel_large.glb",
            (5.5, 0.0, -5.5),
            (0.65, 0.65, 0.65),
            (0, -0.5, 0),
        ),
        (
            "cover_chest",
            (-4.5, 0.55, -7.0),
            (CHEST[0] * 0.8, CHEST[1] * 0.8, CHEST[2] * 0.8),
            "chest_gold.glb",
            (-4.5, 0.0, -7.0),
            (0.8, 0.8, 0.8),
            (0, 0.4, 0),
        ),
    )
    for node_id, col_pos, col_size, asset, vis_pos, scale, rotation in blockers:
        scene.create_primitive(
            node_id,
            "box",
            position=col_pos,
            size=col_size,
            material=Material("#667085"),
            physics=Physics(body="fixed", collider="cuboid"),
            tags=["obstacle", "collider"],
            **_invisible(),
        )
        # Visual is a sibling of the invisible collider (not parented) so play-mode
        # MeshAssets can render it while the collider stays renderPrimitive=False.
        scene.add_glb(
            f"{node_id}_visual",
            f"{KAYKIT}/{asset}",
            position=vis_pos,
            rotation=rotation,
            scale=scale,
            tags=["prop"],
        )

    # Collectibles along a readable path: left lane, right reward near hazard, gate approach.
    # Left safe lane, right-edge temptation beside the pit, final approach to the gate.
    coin_spots = ((-5.0, 0.55, 7.0), (6.5, 0.55, 2.8), (0.0, 0.55, -9.5))
    coin_scale = 2.2  # 0.36 * 2.2 ≈ 0.8m readable pickup
    for index, position in enumerate(coin_spots, start=1):
        scene.create_primitive(
            f"coin_{index}",
            "sphere",
            position=position,
            radius=0.45,
            material=Material("#fdb022"),
            physics=Physics(body="fixed", collider="ball", sensor=True),
            tags=["collectible"],
            **_invisible(),
        )
        scene.add_glb(
            f"coin_{index}_visual",
            f"{KAYKIT}/coin.glb",
            parent_id=f"coin_{index}",
            position=(0, 0, 0),
            scale=(coin_scale, coin_scale, coin_scale),
            apply_environment=False,
            visualFor=f"coin_{index}",
        )

    # Hazard pit on the center/right shortcut; safe lane stays on the left (-X).
    scene.create_primitive(
        "hazard",
        "box",
        position=(2.0, 0.45, 0.0),
        size=(7.2, 1.0, 3.6),
        material=Material("#3b1218"),
        physics=Physics(body="fixed", collider="cuboid", sensor=True),
        tags=["hazard"],
        **_invisible(),
    )
    scene.create_primitive(
        "hazard_pit_visual",
        "box",
        position=(2.0, -0.18, 0.0),
        size=(8.0, 0.08, 4.0),
        material=Material("#1a0c10", roughness=1.0),
        tags=["hazard", "decoration"],
        renderPrimitive=True,
    )
    scene.add_glb(
        "hazard_torch_l",
        f"{KAYKIT}/torch_lit.glb",
        position=(-1.8, 1.35, 0.0),
        scale=(0.8, 0.8, 0.8),
        tags=["prop", "light"],
    )
    scene.add_glb(
        "hazard_torch_r",
        f"{KAYKIT}/torch_lit.glb",
        position=(5.8, 1.35, 0.0),
        rotation=(0, 3.1416, 0),
        scale=(0.8, 0.8, 0.8),
        tags=["prop", "light"],
    )

    # Checkpoint: torch gate + invisible sensor (no colored debug slab).
    scene.create_primitive(
        "checkpoint",
        "box",
        position=(0.0, 0.5, -4.0),
        size=(4.0, 1.6, 1.2),
        material=Material("#d6a65f"),
        physics=Physics(body="fixed", collider="cuboid", sensor=True),
        tags=["checkpoint"],
        **_invisible(),
    )
    for node_id, x in (("checkpoint_torch_l", -2.6), ("checkpoint_torch_r", 2.6)):
        scene.add_glb(
            node_id,
            f"{KAYKIT}/torch_lit.glb",
            position=(x, 1.35, -4.0),
            scale=(0.8, 0.8, 0.8),
            tags=["prop", "light"],
        )
    scene.add_glb(
        "checkpoint_pillar_l",
        f"{KAYKIT}/pillar.glb",
        position=(-2.6, 0.0, -4.0),
        scale=(0.55, 0.55, 0.55),
        tags=["architecture"],
    )
    scene.add_glb(
        "checkpoint_pillar_r",
        f"{KAYKIT}/pillar.glb",
        position=(2.6, 0.0, -4.0),
        scale=(0.55, 0.55, 0.55),
        tags=["architecture"],
    )

    # Goal sensor (invisible) + treasure chest visual beyond the gate.
    scene.create_primitive(
        "goal",
        "box",
        position=(0.0, 1.0, -15.0),
        size=(3.5, 2.2, 1.4),
        material=Material("#12b76a"),
        physics=Physics(body="fixed", collider="cuboid", sensor=True),
        tags=["goal"],
        **_invisible(),
    )
    scene.add_glb(
        "goal_chest",
        f"{KAYKIT}/chest_gold.glb",
        position=(0.0, 0.0, -15.2),
        rotation=(0, 3.1416, 0),
        scale=(1.0, 1.0, 1.0),
        tags=["prop", "goal"],
    )

    # Corridor lighting props.
    for index, (x, z, yaw) in enumerate(
        ((-9.2, 8.0, 0.0), (9.2, 8.0, 3.1416), (-9.2, -10.0, 0.0), (9.2, -10.0, 3.1416))
    ):
        scene.add_glb(
            f"torch_wall_{index}",
            f"{KAYKIT}/torch_lit.glb",
            position=(x, 1.55, z),
            rotation=(0, yaw, 0),
            scale=(0.8, 0.8, 0.8),
            tags=["prop", "light"],
        )

    # Spawn landmark barrels (no overlap with the player capsule).
    scene.add_glb(
        "spawn_barrel",
        f"{KAYKIT}/barrel_large.glb",
        position=(-5.5, 0.0, 11.5),
        rotation=(0, 0.6, 0),
        scale=(0.65, 0.65, 0.65),
        tags=["prop"],
    )
    scene.create_primitive(
        "spawn_barrel_col",
        "box",
        position=(-5.5, 0.85, 11.5),
        size=(BARREL[0] * 0.65, BARREL[1] * 0.65, BARREL[2] * 0.65),
        material=Material("#667085"),
        physics=Physics(body="fixed", collider="cuboid"),
        tags=["obstacle", "collider"],
        **_invisible(),
    )

    game = Game()
    game.action_map(
        moveForward=["KeyW", "ArrowUp"],
        moveBack=["KeyS", "ArrowDown"],
        moveLeft=["KeyA", "ArrowLeft"],
        moveRight=["KeyD", "ArrowRight"],
        jump=["Space"],
    )
    game.add_controller("player", move_speed=5.5, jump_speed=7.0)
    game.follow_camera("player", distance=9.5, height=4.8)
    for index in range(1, 4):
        game.add_collectible(f"coin_{index}")
    game.add_hazard("hazard")
    game.add_checkpoint("checkpoint")
    game.add_goal("goal", required_score=3)
    game.set_hud(title="Collect & Escape")
    game.set_timer(90)
    game.outcomes(
        win_message="You gathered the relics and escaped the dungeon.",
        lose_message="A hazard ended the run. Try a safer route.",
    )
    scene.set_game(game)
    return scene


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--edit",
        action="store_true",
        help="Open the world editor instead of starting the game runtime.",
    )
    args = parser.parse_args()

    output = Path(__file__).with_name("collect_escape.sceneify.json")
    build_scene().save(output)
    scene = Scene.load(output)
    serve = scene.run if args.edit else scene.play
    serve(project_root=Path(__file__).parents[1])
