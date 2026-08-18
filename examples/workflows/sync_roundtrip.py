"""Demonstrate editor <-> Python source sync through a marked scene region.

Run from the repository root:
  uv run python examples/workflows/sync_roundtrip.py

Move the crate in the viewer, then use Save JSON for the scene document or Save
Py to rewrite only the code between the two sceneify markers below.
"""

from __future__ import annotations

from pathlib import Path

from sceneify import Material, Physics, Scene
from sceneify.source_sync import BEGIN_MARKER, END_MARKER, save_python

OUT_JSON = Path(__file__).with_name("out_sync.sceneify.json")
OUT_PY = Path(__file__).with_name("out_sync_world.py")


# sceneify:scene-begin
def build_scene() -> Scene:
    scene = Scene("Sync Roundtrip", background="#10131a")
    scene.set_presentation(grid=True, helpers=True, shadows=False, title="Source sync demo")
    scene.create_primitive(
        "floor",
        "box",
        size=(6.0, 0.2, 6.0),
        position=(0.0, -0.1, 0.0),
        material=Material("#2b3344", roughness=1.0),
        physics=Physics(body="fixed", collider="cuboid"),
        tags=["ground"],
    )
    scene.create_primitive(
        "crate",
        "box",
        size=(0.8, 0.8, 0.8),
        position=(1.0, 0.4, 0.0),
        material=Material("#d97706", roughness=0.55),
        physics=Physics(body="dynamic", collider="cuboid", mass=2.0),
        tags=["prop"],
    )
    scene.add_annotation("note", position=(1.0, 1.2, 0.0), label="Move me, then Save Py")
    return scene


# sceneify:scene-end


def main() -> None:
    scene = build_scene()
    scene.save(OUT_JSON)
    path, report = save_python(scene, OUT_PY, mode="markers")
    print("JSON", OUT_JSON.resolve())
    print("Python", path.resolve(), "mode=", report.mode)
    source = path.read_text(encoding="utf-8")
    print("Markers present:", BEGIN_MARKER in source and END_MARKER in source)
    print("Open the viewer, edit transforms, use Save JSON / Save Py.")
    scene.run(project_root=Path(__file__).resolve().parents[2])


if __name__ == "__main__":
    main()
