"""Build the smallest useful 3D scene: two GLBs, a hierarchy, a label, and a path.

Run from the repository root:
  uv run python examples/basics/basic_scene.py

Orbit the scene and inspect the outliner: ``props`` groups the helmet and avocado,
the annotation labels the helmet, and the cyan trajectory is independent geometry.
Assets: Khronos glTF Sample Models (cached under .sceneify_cache).
"""

from pathlib import Path

import sceneify as sf
from sceneify.demo_assets import download_public_asset

ROOT = Path(__file__).resolve().parents[2]


def build_scene() -> sf.Scene:
    cache = ROOT / ".sceneify_cache"
    helmet = download_public_asset("damaged_helmet", cache_dir=cache)
    avocado = download_public_asset("avocado", cache_dir=cache)

    scene = sf.Scene("demo-multi-asset")
    scene.add_glb("helmet", helmet, position=(0, 0, 0))
    scene.add_glb("avocado", avocado, position=(1.5, 0, 0), scale=(8, 8, 8))
    scene.add_object("props", label="Demo props", children=["helmet", "avocado"])
    scene.add_annotation(
        "note-helmet",
        position=(0, 1.1, 0),
        label="Helmet",
        description="Khronos DamagedHelmet sample GLB",
    )
    scene.add_trajectory(
        "orbit-hint",
        points=[(-1, 0.2, 1), (0, 0.8, 1.2), (1.5, 0.2, 1)],
        color="#56ccf2",
    )
    return scene


if __name__ == "__main__":
    scene = build_scene()
    print("Scene nodes:", scene.to_dict()["name"])
    print("Cached assets under:", (ROOT / ".sceneify_cache").resolve())
    print("Inspect the Props group, Helmet annotation, and cyan trajectory in the viewer.")
    scene.run(project_root=ROOT)
