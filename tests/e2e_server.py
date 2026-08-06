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

from examples.collect_escape import build_scene  # noqa: E402
from examples.roman_environment import build_scene as build_roman_scene  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--play", action="store_true")
parser.add_argument("--roman", action="store_true")
parser.add_argument("--edit", action="store_true")
parser.add_argument("--port", type=int, default=4173)
args = parser.parse_args()

scene: Scene = build_roman_scene() if args.roman else build_scene()

with tempfile.TemporaryDirectory(prefix="sceneify-e2e-") as project_root:
    root = Path(project_root)
    (root / "examples").mkdir()
    shutil.copytree(ROOT / "examples" / "assets", root / "examples" / "assets")
    shutil.copy2(ROOT / "assets.catalog.json", root / "assets.catalog.json")
    serve = scene.run if args.edit else scene.play if args.play or args.roman else scene.run
    serve(
        host="127.0.0.1",
        port=args.port,
        open_browser=False,
        stop_on="interrupt",
        project_root=project_root,
    )
