"""Demo: reusable prefabs with per-instance overrides.

Defines a wooden crate prefab (root + lid), then spawns several instances with
different colors, tags, and nested material overrides.

Run from the repository root:
  uv run python examples/game/prefab_demo.py

Walk around and push the crates to see that each prefab instance has independent
physics while sharing the same template.
"""

from __future__ import annotations

from pathlib import Path

import sceneify as sf
from sceneify.objects import Material, Physics

ROOT = Path(__file__).resolve().parents[2]
KAYKIT = "examples/assets/kaykit"


def _ground(scene: sf.Scene) -> None:
    scene.create_primitive(
        "ground",
        "box",
        position=(0, -0.05, 0),
        size=(24, 0.1, 24),
        material=Material(color="#3d4450", roughness=1.0),
        physics=Physics(body="fixed", collider="cuboid"),
        tags=["ground"],
    )


def _define_crate_prefab(scene: sf.Scene) -> None:
    scene.create_primitive(
        "crate_proto",
        "box",
        position=(0, 0.5, 0),
        size=(1, 1, 1),
        material=Material(color="#c27a3a", roughness=0.75),
        physics=Physics(body="dynamic", collider="cuboid", mass=2.0),
        tags=["prop"],
    )
    scene.create_primitive(
        "crate_lid",
        "box",
        parent_id="crate_proto",
        position=(0, 0.6, 0),
        size=(1.05, 0.12, 1.05),
        material=Material(color="#8b5a2b", roughness=0.8),
    )
    scene.define_prefab(
        "crate",
        from_node="crate_proto",
        label="Wooden crate",
    )
    # Prototype stays in the scene as a reference at the origin.


def build_scene() -> sf.Scene:
    scene = sf.Scene("prefab-demo", background="#1a1f2a")
    scene.set_presentation(
        grid=True,
        helpers=False,
        shadows=True,
        title="Prefabs",
        subtitle="One definition → many instances with overrides",
        camera={"position": [8, 6, 10], "target": [0, 0.5, 0], "fov": 50},
    )
    _ground(scene)
    _define_crate_prefab(scene)

    scene.instantiate(
        "crate",
        id="crate_a",
        position=(3, 0, 0),
        overrides={
            "material": {"color": "#d08a4a"},
            "tags": ["prop", "loot"],
            "nodes": {"crate_lid": {"material": {"color": "#222222"}}},
        },
    )
    scene.instantiate(
        "crate",
        id="crate_b",
        position=(-3, 0, 1),
        overrides={"material": {"color": "#6b8f71"}},
    )
    scene.instantiate(
        "crate",
        id="crate_c",
        position=(0, 0, -3),
        overrides={
            "material": {"color": "#4a6fa5"},
            "nodes": {"crate_lid": {"material": {"color": "#e8c547"}}},
        },
    )

    scene.create_primitive(
        "player",
        "capsule",
        position=(0, 1.1, 5),
        radius=0.3,
        height=0.8,
        material=Material(color="#53b1fd"),
        physics=Physics(body="dynamic", collider="capsule", mass=1.0),
        tags=["player"],
        renderPrimitive=False,
    )
    scene.add_glb(
        "player_visual",
        f"{KAYKIT}/knight.glb",
        parent_id="player",
        position=(0, -0.7, 0),
        scale=(0.78, 0.78, 0.78),
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
            "fadeSeconds": 0.12,
        },
    )
    game = sf.Game()
    game.add_controller("player", preset="simple", move_speed=5.0)
    game.follow_camera("player", distance=7.0, height=3.5)
    game.set_hud(
        title="Prefab demo — push the crates",
        show_score=False,
        show_health=False,
        show_timer=False,
        description=(
            "The center crate is the template. The other three reuse it with different "
            "material overrides, then behave as independent physics objects."
        ),
        controls_hint="Move: WASD or arrows · Jump: Space · Push the crates to compare them",
    )
    scene.set_game(game)
    return scene


if __name__ == "__main__":
    scene = build_scene()
    print("Prefabs:", scene.list_prefabs())
    print("Instances: crate_a (loot/dark lid), crate_b (green), crate_c (blue/gold lid)")
    scene.play(project_root=ROOT)
