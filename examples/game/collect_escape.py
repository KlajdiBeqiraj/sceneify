"""Playable dungeon run: collect three relics, fight enemies, then reach the chest.

Run from the repository root:
  uv run python examples/game/collect_escape.py

Controls: WASD / arrows to move, Space to jump, J or left click to attack.
Use ``--edit`` to open the same world in the authoring editor.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sceneify import Game, Material, Physics, Scene

# KayKit Dungeon Remastered measured AABB sizes (meters at scale 1).
FLOOR_TILE = 4.0
# floor_tile_large top sits near y=0.05 at scale 1.
FLOOR_TOP = 0.05
BARREL = (1.8, 2.0, 1.8)
CHEST = (1.7, 1.21, 1.91)
# Rapier capsule: total height = 2 * halfHeight + 2 * radius
CAPSULE_HALF = 0.4
CAPSULE_RADIUS = 0.3

KAYKIT = "examples/assets/kaykit"


def _invisible(**meta: object) -> dict:
    return {"renderPrimitive": False, **meta}


def build_scene() -> Scene:
    scene = Scene("Collect and Escape", background="#120e18")
    scene.set_presentation(
        grid=False,
        helpers=False,
        shadows=True,
        exposure=1.15,
        environmentPreset="night",
        fog={"color": "#120e18", "near": 22, "far": 48},
        camera={"position": [0, 9, 16], "target": [0, 1, 2], "fov": 48},
        title="Collect & Escape",
        subtitle="A third-person browser game authored entirely from Python",
        ambientIntensity=0.35,
        keyLightIntensity=1.15,
    )

    # Floor tiles + matching physics slabs. Skip the pit cells so bodies can fall in.
    # Leave a center-right pit so the hazard reads as a shortcut, not a wall.
    hazard_tiles = {(0, 0), (1, 0)}
    for x_index in range(-2, 3):
        for z_index in range(-4, 4):
            if (x_index, z_index) in hazard_tiles:
                continue
            tile_x = x_index * FLOOR_TILE
            tile_z = z_index * FLOOR_TILE
            scene.create_primitive(
                f"ground_{x_index}_{z_index}",
                "box",
                size=(FLOOR_TILE, FLOOR_TOP, FLOOR_TILE),
                position=(tile_x, FLOOR_TOP / 2, tile_z),
                material=Material("#2b3344", roughness=1.0),
                physics=Physics(body="fixed", collider="cuboid"),
                tags=["ground"],
                **_invisible(),
            )
            scene.add_glb(
                f"floor_{x_index}_{z_index}",
                f"{KAYKIT}/floor_tile_large.glb",
                position=(tile_x, 0, tile_z),
                scale=(1, 1, 1),
                tags=["architecture", "ground"],
            )

    # Player capsule stands on FLOOR_TOP; visual feet share that contact plane.
    player_y = FLOOR_TOP + CAPSULE_HALF + CAPSULE_RADIUS
    knight_scale = 0.78
    scene.create_primitive(
        "player",
        "capsule",
        position=(0, player_y, 10),
        radius=CAPSULE_RADIUS,
        height=CAPSULE_HALF * 2,
        material=Material("#53b1fd"),
        physics=Physics(body="dynamic", collider="capsule", mass=1),
        tags=["player"],
        **_invisible(),
    )
    scene.add_glb(
        "player_visual",
        f"{KAYKIT}/knight.glb",
        parent_id="player",
        position=(0, -(CAPSULE_HALF + CAPSULE_RADIUS), 0),
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
                "attack": "1H_Melee_Attack_Chop",
            },
            "fadeSeconds": 0.12,
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
        scene.create_primitive(
            f"{node_id}_col",
            "box",
            position=(x, 1.2, -13.2),
            size=(1.1, 2.4, 1.1),
            material=Material("#667085"),
            physics=Physics(body="fixed", collider="cuboid"),
            tags=["obstacle", "collider"],
            **_invisible(),
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
    # Kill volume sits in the hole (no floor slab under these tiles).
    scene.create_primitive(
        "hazard",
        "box",
        position=(2.0, -0.6, 0.0),
        size=(7.6, 1.6, 3.8),
        material=Material("#3b1218"),
        physics=Physics(body="fixed", collider="cuboid", sensor=True),
        tags=["hazard"],
        **_invisible(),
    )
    scene.create_primitive(
        "hazard_pit_visual",
        "box",
        position=(2.0, -0.35, 0.0),
        size=(8.0, 0.08, 4.0),
        material=Material("#1a0c10", roughness=1.0),
        tags=["hazard", "decoration"],
        renderPrimitive=True,
    )
    # Thin rim markers so the hole edge reads without becoming a climbable ledge.
    for node_id, position, size in (
        ("pit_rim_n", (2.0, 0.04, -2.05), (8.0, 0.08, 0.2)),
        ("pit_rim_s", (2.0, 0.04, 2.05), (8.0, 0.08, 0.2)),
        ("pit_rim_w", (-1.85, 0.04, 0.0), (0.2, 0.08, 4.0)),
        ("pit_rim_e", (5.85, 0.04, 0.0), (0.2, 0.08, 4.0)),
    ):
        scene.create_primitive(
            node_id,
            "box",
            position=position,
            size=size,
            material=Material("#4a1d24", roughness=1.0),
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

    # Checkpoint: classic translucent pad (not a see-through pillar) + invisible sensor.
    scene.create_primitive(
        "checkpoint",
        "box",
        position=(0.0, 0.55, -4.0),
        size=(3.6, 1.4, 3.6),
        material=Material("#5eead4"),
        physics=Physics(body="fixed", collider="cuboid", sensor=True),
        tags=["checkpoint"],
        **_invisible(),
    )
    scene.create_primitive(
        "checkpoint_pad",
        "box",
        position=(0.0, 0.05, -4.0),
        size=(3.4, 0.1, 3.4),
        material=Material("#2dd4bf", roughness=0.25, opacity=0.45),
        tags=["checkpoint", "decoration"],
        renderPrimitive=True,
    )
    scene.create_primitive(
        "checkpoint_ring",
        "box",
        position=(0.0, 0.12, -4.0),
        size=(3.8, 0.04, 3.8),
        material=Material("#99f6e4", roughness=0.2, opacity=0.28),
        tags=["checkpoint", "decoration"],
        renderPrimitive=True,
    )
    for node_id, x in (("checkpoint_torch_l", -2.8), ("checkpoint_torch_r", 2.8)):
        scene.add_glb(
            node_id,
            f"{KAYKIT}/torch_lit.glb",
            position=(x, 1.35, -4.0),
            scale=(0.8, 0.8, 0.8),
            tags=["prop", "light"],
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
    scene.create_primitive(
        "goal_chest_col",
        "box",
        position=(0.0, 0.6, -15.2),
        size=(CHEST[0], CHEST[1], CHEST[2]),
        material=Material("#667085"),
        physics=Physics(body="fixed", collider="cuboid"),
        tags=["obstacle", "collider"],
        **_invisible(),
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
        attack=["KeyJ", "Mouse0"],
    )
    game.add_controller("player", move_speed=5.5, jump_speed=7.0)
    game.follow_camera("player", distance=9.5, height=4.8)
    for index in range(1, 4):
        game.add_collectible(f"coin_{index}")
    game.add_hazard("hazard")
    game.add_checkpoint("checkpoint")
    game.add_goal("goal", required_score=3)
    enemy_y = FLOOR_TOP + CAPSULE_HALF + CAPSULE_RADIUS
    game.set_enemies(
        spawn_points=[
            (-8.0, enemy_y, -8.0),
            (8.0, enemy_y, -8.0),
            (-8.0, enemy_y, 6.0),
            (8.0, enemy_y, 6.0),
            (0.0, enemy_y, -12.0),
        ],
        types=[
            {
                "kind": "knight",
                "source": f"{KAYKIT}/knight.glb",
                "max_alive": 2,
                "interval_seconds": 5.0,
                "speed": 2.9,
                "scale": 0.75,
                "health": 3,
                "contact_damage": 1,
                "animation": {
                    "idle": "Idle",
                    "run": "Running_A",
                    "hit": "Hit_A",
                    "death": "Death_A",
                },
            },
            {
                "kind": "mage",
                "source": f"{KAYKIT}/mage.glb",
                "max_alive": 2,
                "interval_seconds": 6.5,
                "speed": 2.3,
                "scale": 0.75,
                "health": 2,
                "contact_damage": 1,
                "animation": {
                    "idle": "Idle",
                    "run": "Running_A",
                    "hit": "Hit_A",
                    "death": "Death_A",
                },
            },
        ],
    )
    game.set_hud(
        title="Collect & Escape",
        description="Collect the three relics, avoid the pit, then reach the chest.",
        controls_hint="Move: WASD or arrows · Jump: Space · Attack: J or click",
        show_health=True,
    )
    game.set_timer(90)
    game.outcomes(
        win_message="You gathered the relics and escaped the dungeon.",
        lose_message="You fell in the pit or ran out of health. Fight smarter next time.",
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
    serve(project_root=Path(__file__).parents[2])
