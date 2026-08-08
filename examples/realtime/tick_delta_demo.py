"""Demo: Python on_tick motion with dirty pose deltas over the wire.

A platform and a spinning marker move every tick. Quiet frames (no transform
changes) skip the network; dirty poses are sent as compact frame deltas.

Run from the repository root:
  uv run python examples/realtime/tick_delta_demo.py

Watch the platform: its transform is authored in Python every frame, while the
viewer receives only changed poses instead of a complete scene document.
"""

from __future__ import annotations

import math

import sceneify as sf
from sceneify.objects import Material, Physics


def main() -> None:
    scene = sf.Scene("tick-delta-demo", background="#10141c")
    scene.set_presentation(
        grid=True,
        helpers=False,
        shadows=True,
        title="Tick + pose deltas",
        subtitle="Python drives transforms; only dirty poses leave the wire",
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

    t = {"elapsed": 0.0}

    @scene.on_tick
    def animate(current: sf.Scene, dt: float) -> None:
        t["elapsed"] += dt
        x = math.sin(t["elapsed"] * 1.2) * 3.0
        current.update_node("platform", position=(x, 0.2, 0))
        yaw = t["elapsed"] * 90.0  # degrees / second-ish for demo readability
        current.update_node("spinner", position=(x, 1.2, 0), rotation=(0, yaw, 0))

    print("Watch the platform oscillate — transforms stream as dirty pose deltas.")
    scene.run()


if __name__ == "__main__":
    main()
