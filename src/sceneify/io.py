"""Scene serialization (sceneify JSON format)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

SCENE_FORMAT = "sceneify-scene"
SCENE_VERSION = 1

if TYPE_CHECKING:
    from sceneify.scene import Scene


def scene_document(scene: Scene) -> dict[str, Any]:
    payload = scene.to_dict()
    return {
        "format": SCENE_FORMAT,
        "version": SCENE_VERSION,
        "scene": payload,
    }


def save_scene(scene: Scene, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    document = scene_document(scene)
    target.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return target


def load_scene_dict(path: str | Path) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Scene file must contain a JSON object")
    if "scene" in raw:
        if raw.get("format") not in {None, SCENE_FORMAT}:
            raise ValueError(f"Unsupported scene format: {raw.get('format')!r}")
        return raw["scene"]
    # Allow raw scene payloads without wrapper for convenience.
    return raw
