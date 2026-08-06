"""Example: world GLB environment, place-on-world, edit/save loop."""

from pathlib import Path

import sceneify as sf
from sceneify.demo_assets import download_public_asset


def main() -> None:
    # Use a public GLB as the world environment, then place another asset on it.
    world = download_public_asset("damaged_helmet")
    prop = download_public_asset("avocado")

    scene = sf.Scene("demo-world-edit")
    env = scene.set_environment(
        bounds_min=(-4, -1, -4),
        bounds_max=(4, 4, 4),
        ground_y=0.0,
        snap=0.1,
    )
    env.set_world_glb(str(world), position=(0, 0, 0), scale=(1, 1, 1))
    # Hide flat ground visual when a world mesh is present (optional).
    if env.ground:
        env.ground.visible = False

    # Place prop on world surface at xz. Without trimesh, height falls back to ground_y.
    scene.place_on_world("avocado", prop, x=1.2, z=0.4, offset_y=0.05, scale=(10, 10, 10))
    scene.add_annotation("anchor", position=(1.2, 1.0, 0.4), label="Placed on world")

    out = Path("examples/out_world.sceneify.json")
    scene.save(out)
    print("Saved", out.resolve())
    print("Reload check:", sf.Scene.load(out).to_dict()["meshes"][0]["id"])
    print("Open the viewer, toggle Edit on, move objects, Save scene JSON from the sidebar.")
    scene.run()


if __name__ == "__main__":
    main()
