"""A source-sync-ready example for MCP conversational sessions."""

from pathlib import Path

from sceneify import Material, Physics, Scene


# sceneify:scene-begin
def build_scene() -> Scene:
    scene = Scene("Conversational Room", background="#10131a")
    scene.create_primitive(
        "floor",
        "box",
        size=(8.0, 0.2, 8.0),
        position=(0.0, -0.1, 0.0),
        material=Material("#2b3344"),
        physics=Physics(body="fixed", collider="cuboid"),
    )
    scene.create_primitive(
        "welcome_cube",
        "box",
        position=(0.0, 0.5, 0.0),
        material=Material("#d97706"),
        physics=Physics(body="dynamic", collider="cuboid"),
    )
    return scene


# sceneify:scene-end

if __name__ == "__main__":
    build_scene().run(project_root=Path(__file__).parents[2])
