"""Revisioned server-side scene command stack."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sceneify.game import GameManifest
from sceneify.scene import Scene


class RevisionConflict(ValueError):
    """Raised when a client edits from a stale revision."""


@dataclass
class _HistoryEntry:
    before: dict[str, Any]
    after: dict[str, Any]
    command: dict[str, Any]


class CommandStack:
    """Apply editor commands with snapshot-backed undo and redo."""

    def __init__(self, scene: Scene) -> None:
        self.scene = scene
        self.revision = 0
        self._undo: list[_HistoryEntry] = []
        self._redo: list[_HistoryEntry] = []

    def execute(
        self, command: Mapping[str, Any], *, expected_revision: int | None = None
    ) -> dict[str, Any]:
        self._check_revision(expected_revision)
        normalized = copy.deepcopy(dict(command))
        action = normalized.get("action", normalized.get("command", normalized.get("type")))
        if not isinstance(action, str):
            raise ValueError("Command action must be a string")
        before = self.scene.to_dict()
        try:
            result = self._apply(_normalize_action(action), normalized)
        except Exception:
            self._restore(before)
            raise
        after = self.scene.to_dict()
        self._undo.append(_HistoryEntry(before, after, normalized))
        self._redo.clear()
        return self._ack(action, result)

    def undo(self, *, expected_revision: int | None = None) -> dict[str, Any]:
        self._check_revision(expected_revision)
        if not self._undo:
            raise ValueError("Nothing to undo")
        entry = self._undo.pop()
        self._restore(entry.before)
        self._redo.append(entry)
        return self._ack("undo", None)

    def redo(self, *, expected_revision: int | None = None) -> dict[str, Any]:
        self._check_revision(expected_revision)
        if not self._redo:
            raise ValueError("Nothing to redo")
        entry = self._redo.pop()
        self._restore(entry.after)
        self._undo.append(entry)
        return self._ack("redo", None)

    def snapshot(self) -> dict[str, Any]:
        return {
            "type": "snapshot",
            "revision": self.revision,
            "scene": {**self.scene.to_dict(), "revision": self.revision},
        }

    def check_revision(self, expected_revision: int | None) -> None:
        """Validate a revision for non-command operations."""
        self._check_revision(expected_revision)

    def _apply(self, action: str, command: dict[str, Any]) -> Any:
        if action == "create_primitive":
            primitive = str(command.get("primitive", "box"))
            node_id = _optional_id(command) or self.scene._available_id(primitive)
            options = _snake_options(_without_transport(command))
            options.pop("primitive", None)
            return self.scene.create_primitive(node_id, primitive, **options).to_dict()
        if action == "create_asset":
            asset_id = command.get("assetId", command.get("asset_id"))
            source = command.get("source") or asset_id
            if not isinstance(source, str) or not source:
                raise ValueError("create_asset requires assetId or source")
            base = asset_id if isinstance(asset_id, str) and asset_id else Path(source).stem
            node_id = _optional_id(command) or self.scene._available_id(base)
            options = _snake_options(_without_transport(command))
            for key in ("assetId", "asset_id", "source"):
                options.pop(key, None)
            return self.scene.add_mesh(node_id, source, **options).to_dict()
        if action == "set_gameplay_role":
            node_id = _required(command, "id")
            if node_id not in self.scene._graph_nodes():
                raise KeyError(f"Unknown graph node id {node_id!r}")
            role = command.get("role", command.get("gameplayRole"))
            if not isinstance(role, str):
                raise ValueError("set_gameplay_role requires a role")
            manifest = GameManifest.from_dict(self.scene._game_manifest)
            manifest.set_gameplay_role(node_id, role)
            self.scene.set_game(manifest)
            return {"id": node_id, "role": role, "game": manifest.to_dict()}
        if action == "add_annotation":
            target_id = command.get("targetId", command.get("target_id"))
            return self.scene.add_annotation(
                _required(command, "id"),
                None if target_id else command.get("position", (0.0, 0.0, 0.0)),
                target_id=target_id if isinstance(target_id, str) else None,
                offset=command.get("offset"),
                label=command.get("label"),
                description=command.get("description"),
                visible=bool(command.get("visible", True)),
            ).to_dict()
        if action == "set_world":
            source = command.get("source")
            if not isinstance(source, str) or not source:
                raise ValueError("set_world requires a source")
            environment = self.scene.environment or self.scene.set_environment()
            return environment.set_world_mesh(
                source,
                format=command.get("format"),
                position=command.get("position"),
                rotation=command.get("rotation"),
                scale=command.get("scale"),
                visible=bool(command.get("visible", True)),
                catalog_asset=command.get("assetId"),
            ).to_dict()
        if action == "create":
            payload = dict(command.get("node") or command)
            node_id = _required(payload, "id")
            kind = payload.pop("kind", "primitive")
            for key in (
                "action",
                "command",
                "type",
                "id",
                "kind",
                "revision",
                "expectedRevision",
            ):
                payload.pop(key, None)
            options = _snake_options(payload)
            if kind == "mesh":
                source = options.pop("source", None)
                if not isinstance(source, str) or not source:
                    raise ValueError("Mesh creation requires a source")
                return self.scene.add_mesh(node_id, source, **options).to_dict()
            if kind == "object":
                return self.scene.add_object(node_id, **options).to_dict()
            if kind != "primitive":
                raise ValueError(f"Unsupported node kind: {kind!r}")
            primitive = options.pop("primitive", options.pop("primitiveType", "box"))
            node = self.scene.create_primitive(node_id, primitive, **options)
            return node.to_dict()
        if action == "duplicate":
            return self.scene.duplicate_subtree(
                _required(command, "id"),
                new_id=command.get("newId"),
                parent_id=command.get("parentId"),
            )
        if action == "delete":
            return {"deleted": self.scene.delete_recursive(_required(command, "id"))}
        if action == "reparent":
            return self.scene.reparent(_required(command, "id"), command.get("parentId"))
        if action == "patch":
            patch = command.get("patch")
            if not isinstance(patch, dict):
                raise ValueError("Patch command requires an object patch")
            node_id = _required(command, "id")
            values = dict(patch)
            role = values.pop("gameplayRole", None)
            result = self.scene.patch_node(node_id, values) if values else None
            if role is not None:
                self._apply(
                    "set_gameplay_role",
                    {"id": node_id, "role": role},
                )
            return result or self.scene._graph_nodes()[node_id].to_dict()
        if action == "define_prefab":
            prefab_id = _required(command, "id")
            from_node = command.get("fromNode", command.get("from_node"))
            if not isinstance(from_node, str) or not from_node:
                raise ValueError("define_prefab requires fromNode")
            game_roles = command.get("gameRoles", command.get("game_roles"))
            return self.scene.define_prefab(
                prefab_id,
                from_node=from_node,
                label=command.get("label"),
                root_id=command.get("rootId", command.get("root_id")),
                game_roles=game_roles if isinstance(game_roles, dict) else None,
            ).to_dict()
        if action == "instantiate_prefab":
            prefab_id = command.get("prefabId", command.get("prefab_id"))
            if not isinstance(prefab_id, str) or not prefab_id:
                raise ValueError("instantiate_prefab requires prefabId")
            instance_id = _optional_id(command)
            options = _snake_options(_without_transport(command))
            options.pop("prefabId", None)
            options.pop("prefab_id", None)
            return self.scene.instantiate(prefab_id, id=instance_id, **options)
        raise ValueError(f"Unsupported command action: {action!r}")

    def _ack(self, action: str, result: Any) -> dict[str, Any]:
        self.revision += 1
        return {
            "type": "command_ack",
            "action": action,
            "commandId": f"command-{self.revision}",
            "revision": self.revision,
            "result": result,
            "scene": {**self.scene.to_dict(), "revision": self.revision},
        }

    def _check_revision(self, expected: int | None) -> None:
        if expected is not None and expected != self.revision:
            raise RevisionConflict(
                f"Expected revision {expected}, current revision is {self.revision}"
            )

    def _restore(self, snapshot: dict[str, Any]) -> None:
        restored = Scene.from_dict(snapshot)
        self.scene.name = restored.name
        self.scene.background = restored.background
        self.scene._meshes = restored._meshes
        self.scene._objects = restored._objects
        self.scene._primitives = restored._primitives
        self.scene._annotations = restored._annotations
        self.scene._trajectories = restored._trajectories
        self.scene._environment = restored._environment
        self.scene._game_manifest = restored._game_manifest
        self.scene._prefabs = restored._prefabs


def _required(command: Mapping[str, Any], key: str) -> str:
    value = command.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a nonempty string")
    return value


def _optional_id(command: Mapping[str, Any]) -> str | None:
    value = command.get("id")
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("id must be a nonempty string")
    return value


def _without_transport(command: Mapping[str, Any]) -> dict[str, Any]:
    ignored = {
        "action",
        "command",
        "type",
        "id",
        "revision",
        "expectedRevision",
    }
    return {key: copy.deepcopy(value) for key, value in command.items() if key not in ignored}


def _snake_options(options: dict[str, Any]) -> dict[str, Any]:
    aliases = {
        "parentId": "parent_id",
    }
    return {aliases.get(key, key): value for key, value in options.items()}


def _normalize_action(action: str) -> str:
    aliases = {
        "create_primitive": "create_primitive",
        "create_asset": "create_asset",
        "set_gameplay_role": "set_gameplay_role",
        "define_prefab": "define_prefab",
        "instantiate_prefab": "instantiate_prefab",
        "createPrimitive": "create_primitive",
        "createAsset": "create_asset",
        "setGameplayRole": "set_gameplay_role",
        "definePrefab": "define_prefab",
        "instantiatePrefab": "instantiate_prefab",
        "duplicateNode": "duplicate",
        "deleteNode": "delete",
        "reparentNode": "reparent",
        "patchNode": "patch",
    }
    return aliases.get(action, action)
