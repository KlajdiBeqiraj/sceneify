"""Present a room or object for the web: orbit, HDRI, embed.

Run from the repository root:
  uv run python examples/mcp/hall.py

Drag to orbit, scroll to zoom. After decorating, export and paste
``<sceneify-viewer>`` from dist-web/EMBED.txt. In-repo primitives; no remote cache.
"""

from pathlib import Path

from sceneify import ExperienceManifest, Material, Physics, Scene

# sceneify:scene-begin
def build_scene() -> Scene:
    scene = Scene("Hall", background="#10131a")
    scene.set_experience(ExperienceManifest.present(title="Hall"))
    scene.set_presentation(
        shadows=True,
        environmentPreset="apartment",
        grid=False,
        helpers=False,
        camera={"position": [6, 4, 8], "target": [0, 1, 0], "fov": 42},
        title="Hall",
        subtitle="Drag to orbit · scroll to zoom",
    )
    scene.create_primitive(
        "floor",
        "box",
        size=(10.0, 0.16, 10.0),
        position=(0.0, -0.08, 0.0),
        material=Material("#2b3344"),
        physics=Physics(body="fixed", collider="cuboid"),
    )
    scene.create_primitive(
        "plinth",
        "box",
        size=(1.6, 0.7, 1.6),
        position=(0.0, 0.35, 0.0),
        material=Material("#8a7a66"),
    )
    return scene
# sceneify:scene-end


if __name__ == "__main__":
    scene = build_scene()
    # After decorating, embed on a site:
    #   scene.export_web("dist-web", api_base="http://127.0.0.1:8765")
    # Then paste dist-web/EMBED.txt (<sceneify-viewer> or iframe).
    scene.run(project_root=Path(__file__).parents[2])
