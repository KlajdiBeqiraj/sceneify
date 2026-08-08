"""Serve the bundled vertical slice for Playwright tests."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from sceneify import Scene

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from examples.game.collect_escape import build_scene  # noqa: E402
from examples.realtime.stress_many_assets import build_scene as build_stress_scene  # noqa: E402
from examples.showcase.roman_environment import build_scene as build_roman_scene  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--play", action="store_true")
parser.add_argument("--roman", action="store_true")
parser.add_argument("--stress", action="store_true")
parser.add_argument("--edit", action="store_true")
parser.add_argument("--port", type=int, default=4173)
args = parser.parse_args()

if args.stress:
    scene: Scene = build_stress_scene()
elif args.roman:
    scene = build_roman_scene()
else:
    scene = build_scene()

with tempfile.TemporaryDirectory(prefix="sceneify-e2e-") as project_root:
    root = Path(project_root)
    (root / "examples").mkdir()
    shutil.copytree(ROOT / "examples" / "assets", root / "examples" / "assets")
    shutil.copy2(ROOT / "assets.catalog.json", root / "assets.catalog.json")
    if args.edit or args.stress:
        serve = scene.run
    elif args.play or args.roman:
        serve = scene.play
    else:
        serve = scene.run
    serve(
        host="127.0.0.1",
        port=args.port,
        open_browser=False,
        stop_on="interrupt",
        project_root=project_root,
    )
