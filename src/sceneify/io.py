"""Scene serialization (sceneify JSON format)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

SCENE_FORMAT = "sceneify-scene"
SCENE_VERSION = 2

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
        if raw.get("format") != SCENE_FORMAT:
            raise ValueError(f"Unsupported scene format: {raw.get('format')!r}")
        version = raw.get("version")
        if isinstance(version, bool) or version not in {1, SCENE_VERSION}:
            raise ValueError(f"Unsupported scene version: {version!r}")
        payload = raw["scene"]
        if not isinstance(payload, dict):
            raise ValueError("Scene document payload must be a JSON object")
        return migrate_scene_payload(payload, source_version=version)
    # Keep compatibility with unwrapped scene payloads.
    return migrate_scene_payload(raw)


def migrate_scene_payload(
    payload: dict[str, Any], *, source_version: int | None = None
) -> dict[str, Any]:
    """Normalize a v1 or raw scene payload to the explicit v2 contract."""
    data = copy.deepcopy(payload)
    inferred = source_version or int(data.get("schemaVersion", 1))
    if inferred not in {1, 2}:
        raise ValueError(f"Unsupported scene payload version: {inferred!r}")
    data["schemaVersion"] = 2
    data.setdefault("meshes", [])
    data.setdefault("objects", [])
    data.setdefault("primitives", [])
    data.setdefault("annotations", [])
    data.setdefault("trajectories", [])
    data.setdefault("game", None)
    data.setdefault("prefabs", [])

    ids = [
        str(node["id"])
        for collection in ("meshes", "objects", "primitives", "annotations", "trajectories")
        for node in data[collection]
    ]
    if len(ids) != len(set(ids)):
        raise ValueError("Scene node ids must be globally unique")

    child_parents: dict[str, str] = {}
    for obj in data["objects"]:
        for child_id in obj.pop("children", []) or []:
            previous = child_parents.setdefault(str(child_id), str(obj["id"]))
            if previous != obj["id"]:
                raise ValueError(f"Node {child_id!r} has multiple parents")
    for collection in ("meshes", "objects", "primitives"):
        for node in data[collection]:
            node.setdefault("parentId", child_parents.get(str(node["id"])))
            node.setdefault("tags", [])
            node.setdefault("material", None)
            node.setdefault("physics", None)
    missing = set(child_parents) - {
        str(node["id"])
        for collection in ("meshes", "objects", "primitives")
        for node in data[collection]
    }
    if missing:
        raise ValueError(f"Legacy children reference missing nodes: {', '.join(sorted(missing))}")
    return data
