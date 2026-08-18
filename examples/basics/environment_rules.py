"""Show environment bounds, allowed zones, snapping, and placement rules.

Run from the repository root:
  uv run python examples/basics/environment_rules.py

The helmet is deliberately placed off-grid and below ground. Inspect its final
position to see the environment clamp and snap the placement.
Assets: Khronos DamagedHelmet (cached under .sceneify_cache).
"""

from pathlib import Path

import sceneify as sf
from sceneify.demo_assets import download_public_asset
from sceneify.environment import RuleKind

ROOT = Path(__file__).resolve().parents[2]


def build_scene() -> sf.Scene:
    helmet = download_public_asset("damaged_helmet", cache_dir=ROOT / ".sceneify_cache")

    scene = sf.Scene("demo-environment")
    env = scene.set_environment(
        bounds_min=(-3, 0, -3),
        bounds_max=(3, 3, 3),
        ground_y=0.0,
        snap=0.25,
    )
    env.add_zone(
        "work_cell",
        role="allowed",
        min_point=(-2, 0, -2),
        max_point=(2, 2.5, 2),
        label="Work cell",
    )
    env.add_zone(
        "no_go",
        role="forbidden",
        min_point=(1.2, 0, -0.6),
        max_point=(2.2, 1.2, 0.6),
        label="No-go",
    )
    env.add_rule(RuleKind.INSIDE_ALLOWED, mode="warn")

    # Intentionally slightly off-grid / near bounds: rules clamp/snap on add.
    scene.add_glb("helmet", helmet, position=(0.12, -0.4, 0.08))
    scene.add_annotation(
        "cell-center",
        position=(0, 1.0, 0),
        label="Work cell",
        description="Allowed volume",
    )
    scene.add_trajectory(
        "patrol",
        points=[(-1.5, 0.5, -1), (0, 0.75, 0), (1, 0.5, 1)],
        color="#56ccf2",
    )
    return scene


if __name__ == "__main__":
    scene = build_scene()
    print("Environment:", scene.to_dict()["environment"]["bounds"])
    print("Helmet position after rules:", scene.to_dict()["meshes"][0]["position"])
    print("Cached assets under:", (ROOT / ".sceneify_cache").resolve())
    print("Toggle Edit to inspect the allowed work cell and forbidden no-go volume.")
    scene.run(project_root=ROOT)
