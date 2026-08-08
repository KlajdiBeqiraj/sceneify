"""Reusable scene prefabs: schema subtrees with per-instance overrides."""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from sceneify.objects import Material, MeshAsset, Physics, PrimitiveNode, SceneObject
from sceneify.types import as_vec3

GameplayRole = Literal["none", "player-spawn", "pickup", "hazard", "checkpoint", "goal"]
GraphNode = MeshAsset | SceneObject | PrimitiveNode

_VALID_ROLES = {"none", "player-spawn", "pickup", "hazard", "checkpoint", "goal"}
_NODE_OVERRIDE_KEYS = {
    "position",
    "rotation",
    "scale",
    "visible",
    "material",
    "physics",
    "tags",
    "meta",
    "label",
    "source",
    "format",
    "primitive",
    "size",
    "radius",
    "height",
}


@dataclass
class Prefab:
    """A reusable scene subtree stored with relative node identifiers."""

    id: str
    root_id: str
    label: str | None = None
    meshes: list[dict[str, Any]] = field(default_factory=list)
    objects: list[dict[str, Any]] = field(default_factory=list)
    primitives: list[dict[str, Any]] = field(default_factory=list)
    game_roles: dict[str, GameplayRole] = field(default_factory=dict)

    def nodes(self) -> dict[str, dict[str, Any]]:
        """Return template nodes keyed by relative id."""
        result: dict[str, dict[str, Any]] = {}
        for collection in (self.meshes, self.objects, self.primitives):
            for node in collection:
                node_id = str(node["id"])
                if node_id in result:
                    raise ValueError(f"Duplicate prefab node id {node_id!r} in {self.id!r}")
                result[node_id] = node
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "rootId": self.root_id,
            "meshes": copy.deepcopy(self.meshes),
            "objects": copy.deepcopy(self.objects),
            "primitives": copy.deepcopy(self.primitives),
            "gameRoles": dict(self.game_roles),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Prefab:
        prefab_id = data.get("id")
        root_id = data.get("rootId", data.get("root_id"))
        if not isinstance(prefab_id, str) or not prefab_id:
            raise ValueError("Prefab requires a nonempty id")
        if not isinstance(root_id, str) or not root_id:
            raise ValueError(f"Prefab {prefab_id!r} requires a nonempty rootId")
        game_roles_raw = data.get("gameRoles", data.get("game_roles")) or {}
        if not isinstance(game_roles_raw, Mapping):
            raise ValueError("Prefab gameRoles must be an object")
        game_roles: dict[str, GameplayRole] = {}
        for node_id, role in game_roles_raw.items():
            if role not in _VALID_ROLES:
                raise ValueError(f"Unsupported gameplay role: {role!r}")
            game_roles[str(node_id)] = role  # type: ignore[assignment]
        prefab = cls(
            id=prefab_id,
            root_id=root_id,
            label=data.get("label"),
            meshes=copy.deepcopy(list(data.get("meshes") or [])),
            objects=copy.deepcopy(list(data.get("objects") or [])),
            primitives=copy.deepcopy(list(data.get("primitives") or [])),
            game_roles=game_roles,
        )
        nodes = prefab.nodes()
        if root_id not in nodes:
            raise ValueError(f"Prefab {prefab_id!r} rootId {root_id!r} is missing from nodes")
        for node in nodes.values():
            parent_id = node.get("parentId")
            if parent_id is not None and parent_id not in nodes:
                raise ValueError(
                    f"Prefab {prefab_id!r} parent {parent_id!r} for {node.get('id')!r} "
                    "does not exist"
                )
        for node_id in game_roles:
            if node_id not in nodes:
                raise ValueError(
                    f"Prefab {prefab_id!r} gameRoles references unknown node {node_id!r}"
                )
        return prefab


def capture_prefab(
    *,
    prefab_id: str,
    root: GraphNode,
    descendants: Sequence[GraphNode],
    label: str | None = None,
    root_id: str | None = None,
    game_roles: Mapping[str, str] | None = None,
) -> Prefab:
    """Build a prefab from a live scene subtree (source ids remapped to relative ids)."""
    if not prefab_id:
        raise ValueError("Prefab id must be nonempty")
    relative_root = root_id or prefab_id
    source_nodes = [root, *descendants]
    mapping: dict[str, str] = {root.id: relative_root}
    reserved = {relative_root}
    for node in descendants:
        candidate = node.id if node.id not in reserved else f"{relative_root}_{node.id}"
        relative = _available_relative_id(candidate, reserved)
        reserved.add(relative)
        mapping[node.id] = relative

    meshes: list[dict[str, Any]] = []
    objects: list[dict[str, Any]] = []
    primitives: list[dict[str, Any]] = []
    for node in source_nodes:
        payload = copy.deepcopy(node.to_dict())
        payload["id"] = mapping[node.id]
        if node.id == root.id:
            payload["parentId"] = None
        elif payload.get("parentId") is not None:
            payload["parentId"] = mapping[str(payload["parentId"])]
        if isinstance(node, MeshAsset):
            meshes.append(payload)
        elif isinstance(node, SceneObject):
            objects.append(payload)
        else:
            primitives.append(payload)

    relative_roles: dict[str, GameplayRole] = {}
    for source_id, role in (game_roles or {}).items():
        if role not in _VALID_ROLES:
            raise ValueError(f"Unsupported gameplay role: {role!r}")
        if source_id not in mapping:
            raise KeyError(f"game_roles references unknown source node {source_id!r}")
        relative_roles[mapping[source_id]] = role  # type: ignore[assignment]

    return Prefab(
        id=prefab_id,
        root_id=relative_root,
        label=label,
        meshes=meshes,
        objects=objects,
        primitives=primitives,
        game_roles=relative_roles,
    )


def graph_node_from_dict(data: Mapping[str, Any]) -> GraphNode:
    """Rehydrate a graph node payload into a typed model."""
    kind = data.get("kind")
    node_id = str(data["id"])
    common = {
        "id": node_id,
        "parent_id": data.get("parentId"),
        "tags": list(data.get("tags") or []),
        "position": as_vec3(data.get("position")),
        "rotation": as_vec3(data.get("rotation")),
        "scale": as_vec3(data.get("scale"), (1.0, 1.0, 1.0)),
        "visible": bool(data.get("visible", True)),
        "material": Material.from_dict(data["material"]) if data.get("material") else None,
        "physics": Physics.from_dict(data.get("physics")),
        "meta": dict(data.get("meta") or {}),
    }
    if kind == "mesh":
        return MeshAsset(
            source=str(data.get("source", "")),
            format=data.get("format"),
            **common,
        )
    if kind == "object":
        return SceneObject(label=data.get("label"), **common)
    if kind == "primitive":
        return PrimitiveNode(
            primitive=data.get("primitive", "box"),
            size=as_vec3(data.get("size"), (1.0, 1.0, 1.0)),
            radius=float(data.get("radius", 0.5)),
            height=float(data.get("height", 1.0)),
            **common,
        )
    raise ValueError(f"Unsupported prefab node kind: {kind!r}")


def apply_node_overrides(node: GraphNode, overrides: Mapping[str, Any] | None) -> GraphNode:
    """Apply shallow property overrides onto a graph node (mutates and returns it)."""
    if not overrides:
        return node
    aliases = {"parentId": "parent_id", "gameRole": "game_role", "game_role": "game_role"}
    for raw_key, value in overrides.items():
        key = aliases.get(raw_key, raw_key)
        if key in {"game_role", "nodes", "parent_id"}:
            continue
        if key not in _NODE_OVERRIDE_KEYS or not hasattr(node, key):
            raise ValueError(f"Unsupported prefab override property: {raw_key!r}")
        if key in {"position", "rotation", "scale", "size"}:
            setattr(
                node,
                key,
                as_vec3(value, (1.0, 1.0, 1.0) if key in {"scale", "size"} else None),
            )
        elif key == "tags":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError("tags override must be a list of strings")
            node.tags = list(value)
        elif key == "material":
            node.material = _merge_material(node.material, value)
        elif key == "physics":
            node.physics = _merge_physics(node.physics, value)
        elif key == "meta":
            if not isinstance(value, Mapping):
                raise ValueError("meta override must be an object")
            merged = dict(node.meta)
            merged.update(copy.deepcopy(dict(value)))
            node.meta = merged
        elif key == "visible":
            node.visible = bool(value)
        else:
            setattr(node, key, value)
    return node


def split_instance_overrides(
    overrides: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], GameplayRole | None]:
    """Split root overrides, per-node overrides, and optional root game role."""
    values = dict(overrides or {})
    child_overrides_raw = values.pop("nodes", None)
    game_role = values.pop("game_role", values.pop("gameRole", None))
    if game_role is not None and game_role not in _VALID_ROLES:
        raise ValueError(f"Unsupported gameplay role: {game_role!r}")
    child_overrides: dict[str, dict[str, Any]] = {}
    if child_overrides_raw is not None:
        if not isinstance(child_overrides_raw, Mapping):
            raise ValueError("overrides.nodes must be an object")
        for relative_id, patch in child_overrides_raw.items():
            if not isinstance(patch, Mapping):
                raise ValueError(f"Override for node {relative_id!r} must be an object")
            child_overrides[str(relative_id)] = dict(patch)
    return values, child_overrides, game_role  # type: ignore[return-value]


def build_instance_id_map(
    prefab: Prefab,
    *,
    instance_root_id: str,
    reserved: set[str],
) -> dict[str, str]:
    """Map prefab-relative ids to unique scene instance ids."""
    nodes = prefab.nodes()
    if prefab.root_id not in nodes:
        raise ValueError(f"Prefab {prefab.id!r} is missing root node {prefab.root_id!r}")
    mapping = {prefab.root_id: instance_root_id}
    taken = set(reserved) | {instance_root_id}
    for relative_id in nodes:
        if relative_id == prefab.root_id:
            continue
        candidate = f"{instance_root_id}_{relative_id}"
        mapped = candidate if candidate not in taken else _available_relative_id(candidate, taken)
        taken.add(mapped)
        mapping[relative_id] = mapped
    return mapping


def _merge_material(
    current: Material | None, value: Material | Mapping[str, Any] | None
) -> Material | None:
    if value is None:
        return None
    if isinstance(value, Material):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("material override must be an object")
    base = current.to_dict() if current is not None else {}
    patch = dict(value)
    # Accept snake_case keys from the Python API.
    aliases = {
        "base_color_texture": "baseColorTexture",
        "normal_texture": "normalTexture",
        "metallic_roughness_texture": "metallicRoughnessTexture",
        "texture_repeat": "textureRepeat",
    }
    normalized = {aliases.get(key, key): item for key, item in patch.items()}
    base.update(normalized)
    return Material.from_dict(base)


def _merge_physics(
    current: Physics | None, value: Physics | Mapping[str, Any] | None
) -> Physics | None:
    if value is None:
        return None
    if isinstance(value, Physics):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("physics override must be an object")
    base = current.to_dict() if current is not None else {}
    base.update(dict(value))
    return Physics.from_dict(base)


def _available_relative_id(base: str, reserved: set[str]) -> str:
    if base not in reserved:
        return base
    index = 2
    while f"{base}_{index}" in reserved:
        index += 1
    return f"{base}_{index}"
