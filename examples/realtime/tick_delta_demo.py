"""Protocol demo: Python on_tick motion with dirty pose deltas over the wire.

A platform and a spinning marker move every tick. Quiet frames (no transform
changes) skip the network; dirty poses are sent as compact frame deltas.

Run from the repository root:
  uv run python examples/realtime/tick_delta_demo.py

This is not a character or board game. ``play()`` is required so ``on_tick``
runs; ``run()`` is editor-only and would leave the platform still.
"""

from __future__ import annotations

import math
from pathlib import Path

import sceneify as sf
from sceneify.objects import Material, Physics

ROOT = Path(__file__).resolve().parents[2]


def build_scene() -> sf.Scene:
    scene = sf.Scene("tick-delta-demo", background="#10141c")
    scene.set_presentation(
        grid=True,
        helpers=False,
        shadows=True,
        title="Tick + pose deltas",
        subtitle="Protocol demo — Python drives transforms; only dirty poses leave the wire",
        camera={"position": [8, 6, 10], "target": [0, 1, 0], "fov": 50},
    )

    scene.create_primitive(
        "ground",
        "box",
        position=(0, -0.05, 0),
        size=(20, 0.1, 20),
        material=Material(color="#2f3642", roughness=1.0),
        physics=Physics(body="fixed", collider="cuboid"),
        tags=["ground"],
    )
    scene.create_primitive(
        "platform",
        "box",
        position=(0, 0.2, 0),
        size=(3, 0.25, 1.5),
        material=Material(color="#4a6fa5", roughness=0.6),
        physics=Physics(body="kinematic", collider="cuboid"),
        tags=["mover"],
    )
    scene.create_primitive(
        "spinner",
        "box",
        position=(0, 1.2, 0),
        size=(0.4, 0.4, 0.4),
        material=Material(color="#e8c547"),
        tags=["mover"],
    )
    scene.add_annotation(
        "hint",
        position=(0, 2.2, 0),
        label="Driven by @scene.on_tick",
        color="#56ccf2",
    )

    elapsed = {"seconds": 0.0}

    @scene.on_tick
    def animate(current: sf.Scene, dt: float) -> None:
        elapsed["seconds"] += dt
        x = math.sin(elapsed["seconds"] * 1.2) * 3.0
        current.update_node("platform", position=(x, 0.2, 0))
        yaw = elapsed["seconds"] * 90.0
        current.update_node("spinner", position=(x, 1.2, 0), rotation=(0, yaw, 0))

    return scene


if __name__ == "__main__":
    print("Leave this process running and look at the browser (not this terminal).")
    print("Blue platform slides on X; yellow cube spins above it. Enter here only to stop.")
    build_scene().play(project_root=ROOT)
