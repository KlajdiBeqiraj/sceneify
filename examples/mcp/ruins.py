"""Explore a space with a character controller and optional objectives.

Run from the repository root:
  uv run python examples/mcp/ruins.py

Controls: WASD / arrows to move, Space to jump. Collect the relic, reach the exit.
Assets: in-repo primitives (no remote cache). Game() sugar is the collect recipe;
this shell uses scene.character() instead.
"""

from pathlib import Path

from sceneify import Material, Physics, Scene

# sceneify:scene-begin
def build_scene() -> Scene:
    scene = Scene("Ruins", background="#10131a")
    scene.set_presentation(
        shadows=True,
        environmentPreset="night",
        camera={"position": [10, 8, 12], "target": [0, 1, 0], "fov": 50},
        title="Ruins",
    )
    scene.create_primitive(
        "ground",
        "box",
        size=(24.0, 0.2, 24.0),
        position=(0.0, -0.1, 0.0),
        material=Material("#2d3b32"),
        physics=Physics(body="fixed", collider="cuboid"),
        tags=["ground"],
    )
    scene.create_primitive(
        "relic_1",
        "sphere",
        position=(3.0, 0.6, -2.0),
        radius=0.28,
        material=Material("#d4af37"),
        physics=Physics(body="kinematic", collider="ball", sensor=True),
        tags=["pickup"],
    )
    scene.create_primitive(
        "exit",
        "box",
        size=(2.0, 2.0, 1.0),
        position=(0.0, 1.0, -8.0),
        material=Material("#4aa36b"),
        physics=Physics(body="kinematic", collider="cuboid", sensor=True),
        tags=["goal"],
    )
    play = scene.character(preset="third_person")
    play.hud(title="Ruins", hint="Move: WASD · Jump: Space")
    play.objective("collect", need=1)
    play.objective("reach", node_id="exit", need=1)
    return scene
# sceneify:scene-end


if __name__ == "__main__":
    build_scene().play(project_root=Path(__file__).parents[2])
