"""Stress scene: dozens of repeated GLBs + mixed unique props for browser perf tests.

Used by Playwright (`--stress`) and as a manual demo:
  uv run python examples/realtime/stress_many_assets.py
"""

from __future__ import annotations

from sceneify import Material, Physics, Scene

KAYKIT = "examples/assets/kaykit"
REPEAT_COUNT = 200
GRID = 15


def build_scene(*, repeat: int | None = None) -> Scene:
    import os

    if repeat is None:
        repeat = int(os.environ.get("SCENEIFY_STRESS_COUNT", REPEAT_COUNT))
    scene = Scene("Stress Many Assets", background="#0b1020")
    scene.set_presentation(
        grid=False,
        helpers=False,
        shadows=False,
        exposure=1.0,
        environmentPreset="night",
        title="Stress many assets",
        subtitle=f"{repeat} repeated barrels + mixed props",
        camera={"position": [18, 14, 22], "target": [0, 0, 0], "fov": 50},
        ambientIntensity=0.55,
        keyLightIntensity=0.9,
    )

    scene.create_primitive(
        "ground",
        "box",
        size=(40.0, 0.2, 40.0),
        position=(0.0, -0.1, 0.0),
        material=Material("#1f2937", roughness=1.0),
        physics=Physics(body="fixed", collider="cuboid"),
        tags=["ground"],
    )

    # Repeated identical GLBs — should hit auto-instancing (>=3 same source).
    for index in range(repeat):
        col = index % GRID
        row = index // GRID
        x = (col - GRID / 2) * 1.4
        z = (row - GRID / 2) * 1.4
        scene.add_glb(
            f"barrel_{index}",
            f"{KAYKIT}/barrel_large.glb",
            position=(x, 0.0, z),
            scale=(0.85, 0.85, 0.85),
            apply_environment=False,
            tags=["stress", "instance"],
        )

    # Unique / low-repeat props — stay on clone path.
    for index, (name, source, position) in enumerate(
        (
            ("chest", f"{KAYKIT}/chest_gold.glb", (8.0, 0.0, 0.0)),
            ("pillar", f"{KAYKIT}/pillar.glb", (-8.0, 0.0, 0.0)),
            ("torch", f"{KAYKIT}/torch_lit.glb", (0.0, 0.0, 8.0)),
            ("coin_a", f"{KAYKIT}/coin.glb", (2.0, 0.3, -8.0)),
            ("coin_b", f"{KAYKIT}/coin.glb", (-2.0, 0.3, -8.0)),
        )
    ):
        scene.add_glb(
            name,
            source,
            position=position,
            scale=(1.0, 1.0, 1.0) if "coin" not in name else (2.0, 2.0, 2.0),
            apply_environment=False,
            tags=["stress", "unique", f"i{index}"],
        )

    scene.add_annotation(
        "stress_label",
        position=(0.0, 2.5, 0.0),
        label=f"{repeat} instanced barrels",
    )
    return scene


def main() -> None:
    scene = build_scene()
    payload = scene.to_dict()
    print(f"meshes={len(payload['meshes'])} primitives={len(payload['primitives'])}")
    print("Open with ?perf=1 to see FPS / draw calls.")
    scene.run()


if __name__ == "__main__":
    main()
