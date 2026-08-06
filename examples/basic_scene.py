"""Example: multi-asset scene with annotation and trajectory."""

from pathlib import Path

import sceneify as sf
from sceneify.demo_assets import download_public_asset


def main() -> None:
    helmet = download_public_asset("damaged_helmet")
    avocado = download_public_asset("avocado")

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
    print("Scene nodes:", scene.to_dict()["name"])
    print("Cached assets under:", Path(".sceneify_cache").resolve())
    scene.run()


if __name__ == "__main__":
    main()
