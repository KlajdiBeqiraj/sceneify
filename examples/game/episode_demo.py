"""Demo: episode recording and replay.

Modes:
  uv run python examples/game/episode_demo.py              # replay a synthetic episode
  uv run python examples/game/episode_demo.py --record     # play, record inputs, save JSON
  uv run python examples/game/episode_demo.py --replay path.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

import sceneify as sf
from sceneify.objects import Material, Physics

KAYKIT = "examples/assets/kaykit"


def build_scene() -> sf.Scene:
    scene = sf.Scene("episode-demo", background="#161b24")
    scene.set_presentation(
        grid=True,
        helpers=False,
        shadows=True,
        title="Episode record / replay",
        subtitle="Inputs are captured as a timed episode JSON",
        camera={"position": [0, 5, 10], "target": [0, 1, 0], "fov": 50},
    )
    scene.create_primitive(
        "ground",
        "box",
        position=(0, -0.05, 0),
        size=(24, 0.1, 24),
        material=Material(color="#2f3642", roughness=1.0),
        physics=Physics(body="fixed", collider="cuboid"),
        tags=["ground"],
    )
    scene.create_primitive(
        "marker",
        "box",
        position=(0, 0.25, -4),
        size=(1.5, 0.5, 0.3),
        material=Material(color="#e8c547"),
        physics=Physics(body="fixed", collider="cuboid"),
        tags=["landmark"],
    )
    scene.create_primitive(
        "player",
        "capsule",
        position=(0, 1.1, 4),
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
    game = sf.Game()
    game.add_controller("player", preset="simple", move_speed=4.5)
    game.follow_camera("player")
    game.set_hud(
        title="Episode demo",
        show_score=False,
        show_health=False,
        description=(
            "Replay injects the recorded keyboard events into this same scene. "
            "Use --record to capture your own short run."
        ),
        controls_hint="Move: WASD or arrows · Jump: Space",
    )
    scene.set_game(game)
    return scene


def write_synthetic_episode(path: Path) -> Path:
    episode = sf.Episode(id="synthetic", scene_name="episode-demo", tick_rate=60.0)
    # Walk forward, then jump — enough to see replay inject key events.
    episode.add_input(0.0, "keydown", value="w", metadata={"code": "KeyW"})
    episode.add_input(1.4, "keyup", value="w", metadata={"code": "KeyW"})
    episode.add_input(1.5, "keydown", value=" ", metadata={"code": "Space"})
    episode.add_input(1.7, "keyup", value=" ", metadata={"code": "Space"})
    episode.add_marker(2.0, "end")
    episode.save(path)
    return path


def run_replay(scene: sf.Scene, path: Path) -> None:
    handle = scene.play(block=False, open_browser=True)
    try:
        print(f"Replaying {path} …")
        handle.replay(path)
        input("Press Enter to stop.\n")
    finally:
        handle.stop_replay()
        handle.stop()


def run_record(scene: sf.Scene, out: Path) -> None:
    handle = scene.play(block=False, open_browser=True)
    try:
        print("Recording… move with WASD / Space, then press Enter to stop and save.")
        handle.start_recording(episode_id="live-capture")
        input()
        episode = handle.stop_recording()
        episode.save(out)
        print(f"Saved {out} ({len(episode.events)} events, {episode.duration:.2f}s)")
    finally:
        handle.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="sceneify episode record/replay demo")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--record",
        action="store_true",
        help="Open the viewer and record live inputs to episode_live.json",
    )
    group.add_argument(
        "--replay",
        type=Path,
        metavar="PATH",
        help="Replay an existing episode JSON",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).with_name("episode_live.json"),
        help="Output path when using --record (default: examples/game/episode_live.json)",
    )
    args = parser.parse_args()
    scene = build_scene()

    if args.record:
        run_record(scene, args.out)
        return
    if args.replay is not None:
        run_replay(scene, args.replay)
        return

    path = write_synthetic_episode(Path(__file__).with_name("episode_synthetic.json"))
    print(f"Wrote synthetic episode {path}")
    run_replay(scene, path)


if __name__ == "__main__":
    main()
