"""Create a GLB-backed world, place an object on it, then save and edit the result.

Run from the repository root:
  uv run python examples/workflows/world_edit_save.py

The avocado is placed at an X/Z coordinate on the helmet world surface. Toggle
Edit in the viewer, move it, and save the resulting scene JSON.
Assets: Khronos helmet + avocado (cached under .sceneify_cache).
"""

from pathlib import Path

import sceneify as sf
from sceneify.demo_assets import download_public_asset

ROOT = Path(__file__).resolve().parents[2]


def build_scene() -> sf.Scene:
    cache = ROOT / ".sceneify_cache"
    world = download_public_asset("damaged_helmet", cache_dir=cache)
    prop = download_public_asset("avocado", cache_dir=cache)

    scene = sf.Scene("demo-world-edit")
    env = scene.set_environment(
        bounds_min=(-4, -1, -4),
        bounds_max=(4, 4, 4),
        ground_y=0.0,
        snap=0.1,
    )
    env.set_world_glb(str(world), position=(0, 0, 0), scale=(1, 1, 1))
    if env.ground:
        env.ground.visible = False

    # Without trimesh, height falls back to ground_y.
    scene.place_on_world("avocado", prop, x=1.2, z=0.4, offset_y=0.05, scale=(10, 10, 10))
    scene.add_annotation("anchor", position=(1.2, 1.0, 0.4), label="Placed on world")
    return scene


if __name__ == "__main__":
    scene = build_scene()
    out = Path(__file__).with_name("out_world.sceneify.json")
    scene.save(out)
    print("Saved", out.resolve())
    print("Reload check:", sf.Scene.load(out).to_dict()["meshes"][0]["id"])
    print("Open the viewer, toggle Edit on, move objects, Save scene JSON from the sidebar.")
    scene.run(project_root=ROOT)
