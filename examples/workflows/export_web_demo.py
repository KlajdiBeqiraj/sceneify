"""Demo: export a static viewer that talks to a live Python backend.

  uv run python examples/workflows/export_web_demo.py
  uv run python examples/workflows/export_web_demo.py --serve
  uv run python examples/workflows/export_web_demo.py --out dist-web --api-base http://127.0.0.1:8765

With --serve: exports, starts scene.play() (backend), and prints how to host dist-web/.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import sceneify as sf
from sceneify.objects import Material, Physics

KAYKIT = "examples/assets/kaykit"


def build_scene() -> sf.Scene:
    scene = sf.Scene("export-web-demo", background="#12161e")
    scene.set_presentation(
        grid=True,
        helpers=False,
        shadows=True,
        title="Static web export",
        subtitle="Viewer files are static; play/API stay on Python",
        camera={"position": [0, 5, 10], "target": [0, 1, 0], "fov": 50},
    )
    scene.create_primitive(
        "ground",
        "box",
        position=(0, -0.05, 0),
        size=(20, 0.1, 20),
        material=Material(color="#2f3642", roughness=1.0),
        physics=Physics(body="fixed", collider="cuboid"),
        tags=["ground"],
    )
    scene.create_primitive(
        "player",
        "capsule",
        position=(0, 1.1, 0),
        radius=0.3,
        height=0.8,
        material=Material(color="#53b1fd"),
        physics=Physics(body="dynamic", collider="capsule", mass=1.0),
        tags=["player"],
        renderPrimitive=False,
    )
    scene.add_glb(
        "player_visual",
        f"{KAYKIT}/knight.glb",
        parent_id="player",
        position=(0, -0.7, 0),
        scale=(0.78, 0.78, 0.78),
        apply_environment=False,
        visualFor="player",
        animation={
            "autoplay": "Idle",
            "states": {
                "idle": "Idle",
                "move": "Walking_A",
                "run": "Running_A",
                "jump": "Jump_Full_Short",
            },
            "fadeSeconds": 0.12,
        },
    )
    scene.create_primitive(
        "beacon",
        "box",
        position=(3, 0.75, -2),
        size=(0.6, 1.5, 0.6),
        material=Material(color="#e8c547"),
        physics=Physics(body="fixed", collider="cuboid"),
    )
    game = sf.Game()
    game.add_controller("player", preset="simple")
    game.follow_camera("player")
    game.set_hud(
        title="Export demo",
        show_score=False,
        show_health=False,
        show_timer=False,
        description=(
            "This small world proves that a static viewer can keep talking to the "
            "live Python play backend."
        ),
        controls_hint="Move: WASD or arrows · Jump: Space",
    )
    scene.set_game(game)
    return scene


def main() -> None:
    parser = argparse.ArgumentParser(description="sceneify static web export demo")
    parser.add_argument("--out", type=Path, default=Path("dist-web"))
    parser.add_argument(
        "--api-base",
        default="http://127.0.0.1:8765",
        help="Backend origin written into sceneify.config.json",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="After export, start the Python backend with scene.play()",
    )
    parser.add_argument(
        "--no-copy-assets",
        action="store_true",
        help="Skip packing assets into the export (load via /api/asset)",
    )
    args = parser.parse_args()

    scene = build_scene()
    out = scene.export_web(
        args.out,
        api_base=args.api_base,
        copy_assets=not args.no_copy_assets,
    )
    print(f"Exported viewer → {out.resolve()}")
    print(f"  apiBase = {args.api_base!r}")
    print("Host the folder statically, e.g.:")
    print(f"  uv run python -m http.server 8080 --directory {out}")
    print("Keep the Python backend running (scene.play / --serve).")

    if args.serve:
        print(f"\nStarting backend at {args.api_base} …")
        scene.play()


if __name__ == "__main__":
    main()
