"""Provider independent actions for coding agents that author scenes."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sceneify.catalog import AssetCatalog
from sceneify.scene import Scene

ACTION_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "sceneify world action",
    "type": "object",
    "required": ["action"],
    "properties": {
        "action": {
            "enum": [
                "set_world",
                "add_asset",
                "add_object",
                "add_annotation",
                "update_node",
                "save",
            ]
        },
        "asset": {"type": "string", "minLength": 1},
        "id": {"type": "string", "minLength": 1},
        "path": {"type": "string", "minLength": 1},
        "label": {"type": "string"},
        "description": {"type": "string"},
        "targetId": {"type": "string", "minLength": 1},
        "children": {"type": "array", "items": {"type": "string"}},
        "position": {"$ref": "#/$defs/vec3"},
        "offset": {"$ref": "#/$defs/vec3"},
        "rotation": {"$ref": "#/$defs/vec3"},
        "scale": {"$ref": "#/$defs/vec3"},
        "visible": {"type": "boolean"},
    },
    "$defs": {
        "vec3": {
            "type": "array",
            "prefixItems": [{"type": "number"}, {"type": "number"}, {"type": "number"}],
            "items": False,
        }
    },
}


def tool_definition() -> dict[str, Any]:
    """Return a neutral tool descriptor suitable for a coding agent adapter."""
    return {
        "name": "sceneify_apply",
        "description": "Apply one validated action to a sceneify world.",
        "inputSchema": ACTION_SCHEMA,
    }


class WorldTools:
    """Apply small deterministic actions over a scene and an asset catalog."""

    def __init__(self, scene: Scene, catalog: AssetCatalog) -> None:
        self.scene = scene
        self.catalog = catalog

    def apply(self, command: Mapping[str, Any]) -> dict[str, Any]:
        """Apply one action and return its result plus the current scene."""
        action = _required_string(command, "action")
        handlers = {
            "set_world": self._set_world,
            "add_asset": self._add_asset,
            "add_object": self._add_object,
            "add_annotation": self._add_annotation,
            "update_node": self._update_node,
            "save": self._save,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ValueError(f"Unsupported world action: {action!r}")
        result = handler(command)
        return {"action": action, "result": result, "scene": self.scene.to_dict()}

    def _set_world(self, command: Mapping[str, Any]) -> dict[str, Any]:
        asset = self.catalog.get(_required_string(command, "asset"))
        environment = self.scene.environment or self.scene.set_environment()
        world = environment.set_world_mesh(
            asset.path,
            position=command.get("position"),
            rotation=command.get("rotation"),
            scale=command.get("scale"),
            visible=bool(command.get("visible", True)),
            catalog_asset=asset.id,
        )
        return world.to_dict()

    def _add_asset(self, command: Mapping[str, Any]) -> dict[str, Any]:
        asset = self.catalog.get(_required_string(command, "asset"))
        node_id = str(command.get("id") or asset.id)
        mesh = self.scene.add_mesh(
            node_id,
            asset.path,
            position=command.get("position"),
            rotation=command.get("rotation"),
            scale=command.get("scale"),
            visible=bool(command.get("visible", True)),
            catalog_asset=asset.id,
        )
        return mesh.to_dict()

    def _add_object(self, command: Mapping[str, Any]) -> dict[str, Any]:
        children = command.get("children")
        if children is not None and (
            not isinstance(children, list) or not all(isinstance(item, str) for item in children)
        ):
            raise ValueError("children must be a list of node ids")
        node = self.scene.add_object(
            _required_string(command, "id"),
            label=_optional_string(command, "label"),
            children=children,
            position=command.get("position"),
            rotation=command.get("rotation"),
            scale=command.get("scale"),
            visible=bool(command.get("visible", True)),
        )
        return node.to_dict()

    def _add_annotation(self, command: Mapping[str, Any]) -> dict[str, Any]:
        target_id = _optional_string(command, "targetId")
        node = self.scene.add_annotation(
            _required_string(command, "id"),
            None if target_id else command.get("position", (0.0, 0.0, 0.0)),
            target_id=target_id,
            offset=command.get("offset"),
            label=_optional_string(command, "label"),
            description=_optional_string(command, "description"),
            visible=bool(command.get("visible", True)),
        )
        return node.to_dict()

    def _update_node(self, command: Mapping[str, Any]) -> dict[str, Any]:
        return self.scene.update_node(
            _required_string(command, "id"),
            position=command.get("position"),
            rotation=command.get("rotation"),
            scale=command.get("scale"),
            visible=command.get("visible"),
        )

    def _save(self, command: Mapping[str, Any]) -> dict[str, str]:
        path = Path(_required_string(command, "path"))
        return {"path": str(self.scene.save(path))}


def _required_string(command: Mapping[str, Any], key: str) -> str:
    value = command.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a nonempty string")
    return value


def _optional_string(command: Mapping[str, Any], key: str) -> str | None:
    value = command.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value
