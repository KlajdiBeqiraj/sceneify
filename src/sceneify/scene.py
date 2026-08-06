"""High-level Scene API (Streamlit-like entry point)."""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from sceneify.annotations import Annotation, build_annotation
from sceneify.environment import Environment, RuleViolation, build_default_environment
from sceneify.objects import (
    Material,
    MeshAsset,
    Physics,
    PrimitiveNode,
    PrimitiveType,
    SceneObject,
    build_mesh,
    build_object,
)
from sceneify.realtime import EventCallback, InputCallback, TickCallback
from sceneify.trajectories import Trajectory, build_trajectory
from sceneify.types import Vec3, as_vec3


class Scene:
    """Composable 3D scene: multiple assets, objects, annotations, trajectories."""

    def __init__(self, name: str = "scene", *, background: str = "#0f1115") -> None:
        self.name = name
        self.background = background
        self._meshes: dict[str, MeshAsset] = {}
        self._objects: dict[str, SceneObject] = {}
        self._primitives: dict[str, PrimitiveNode] = {}
        self._annotations: dict[str, Annotation] = {}
        self._trajectories: dict[str, Trajectory] = {}
        self._environment: Environment | None = None
        self._tick_callbacks: list[TickCallback] = []
        self._input_callbacks: list[InputCallback] = []
        self._event_callbacks: list[EventCallback] = []
        self._game_manifest: dict[str, Any] | None = None
        self._presentation: dict[str, Any] = {}

    def on_tick(self, callback: TickCallback | None = None) -> TickCallback | Callable:
        """Register ``callback(scene, delta_seconds)`` for realtime ticks."""

        def register(candidate: TickCallback) -> TickCallback:
            if not callable(candidate):
                raise TypeError("Tick callback must be callable")
            self._tick_callbacks.append(candidate)
            return candidate

        return register(callback) if callback is not None else register

    def on_input(self, callback: InputCallback | None = None) -> InputCallback | Callable:
        """Register ``callback(scene, event)`` for viewer input."""

        def register(candidate: InputCallback) -> InputCallback:
            if not callable(candidate):
                raise TypeError("Input callback must be callable")
            self._input_callbacks.append(candidate)
            return candidate

        return register(callback) if callback is not None else register

    def on_event(self, callback: EventCallback | None = None) -> EventCallback | Callable:
        """Register ``callback(scene, event)`` for semantic browser events."""

        def register(candidate: EventCallback) -> EventCallback:
            if not callable(candidate):
                raise TypeError("Event callback must be callable")
            self._event_callbacks.append(candidate)
            return candidate

        return register(callback) if callback is not None else register

    def set_game(self, manifest: Any) -> None:
        """Attach a declarative game manifest."""
        value = manifest.to_dict() if hasattr(manifest, "to_dict") else manifest
        if not isinstance(value, dict):
            raise TypeError("Game manifest must be a mapping or expose to_dict()")
        self._game_manifest = copy.deepcopy(value)

    def set_presentation(self, **options: Any) -> None:
        """Configure browser lighting, camera, helpers, and environment presentation."""
        self._presentation = copy.deepcopy(options)

    def set_environment(
        self, environment: Environment | None = None, **defaults: Any
    ) -> Environment:
        """Attach a geometric environment. Pass nothing (or kwargs) for defaults."""
        if environment is not None and defaults:
            raise ValueError("Pass either an Environment instance or default kwargs, not both")
        if environment is not None:
            self._environment = environment
        else:
            self._environment = build_default_environment(**defaults)
        return self._environment

    @property
    def environment(self) -> Environment | None:
        return self._environment

    def add_glb(
        self,
        asset_id: str,
        source: str | Path,
        *,
        position: Sequence[float] | None = None,
        rotation: Sequence[float] | None = None,
        scale: Sequence[float] | None = None,
        visible: bool = True,
        apply_environment: bool = True,
        **meta: Any,
    ) -> MeshAsset:
        """Add a GLB/glTF asset. Prefer this helper for glTF binary files."""
        return self.add_mesh(
            asset_id,
            source,
            format="glb",
            position=position,
            rotation=rotation,
            scale=scale,
            visible=visible,
            apply_environment=apply_environment,
            **meta,
        )

    def add_mesh(
        self,
        asset_id: str,
        source: str | Path,
        *,
        format: str | None = None,
        position: Sequence[float] | None = None,
        rotation: Sequence[float] | None = None,
        scale: Sequence[float] | None = None,
        visible: bool = True,
        parent_id: str | None = None,
        tags: Sequence[str] | None = None,
        material: Material | Mapping[str, Any] | None = None,
        physics: Physics | Mapping[str, Any] | None = None,
        apply_environment: bool = True,
        **meta: Any,
    ) -> MeshAsset:
        """Add any supported mesh asset (GLB, glTF, PLY, …)."""
        self._ensure_unique(asset_id)
        path = str(source)
        inferred = format or _infer_format(path)
        pos = self._resolve_position(asset_id, position, apply_environment=apply_environment)
        mesh = build_mesh(
            asset_id,
            path,
            format=inferred,
            position=pos,
            rotation=rotation,
            scale=scale,
            visible=visible,
            parent_id=parent_id,
            tags=tags,
            material=_material(material),
            physics=_physics(physics),
            **meta,
        )
        self._meshes[asset_id] = mesh
        try:
            self.validate_graph()
        except Exception:
            del self._meshes[asset_id]
            raise
        return mesh

    def add_object(
        self,
        object_id: str,
        *,
        label: str | None = None,
        children: list[str] | None = None,
        position: Sequence[float] | None = None,
        rotation: Sequence[float] | None = None,
        scale: Sequence[float] | None = None,
        visible: bool = True,
        parent_id: str | None = None,
        tags: Sequence[str] | None = None,
        material: Material | Mapping[str, Any] | None = None,
        physics: Physics | Mapping[str, Any] | None = None,
        apply_environment: bool = True,
        **meta: Any,
    ) -> SceneObject:
        """Add a logical container object that can group child asset ids."""
        self._ensure_unique(object_id)
        pos = self._resolve_position(object_id, position, apply_environment=apply_environment)
        obj = build_object(
            object_id,
            label=label,
            children=children,
            position=pos,
            rotation=rotation,
            scale=scale,
            visible=visible,
            parent_id=parent_id,
            tags=tags,
            material=_material(material),
            physics=_physics(physics),
            **meta,
        )
        self._objects[object_id] = obj
        before_parents = {
            child_id: self._graph_nodes()[child_id].parent_id
            for child_id in (children or [])
            if child_id in self._graph_nodes()
        }
        try:
            if children:
                for child_id in children:
                    self.reparent(child_id, object_id)
            self.validate_graph()
        except Exception:
            del self._objects[object_id]
            for child_id, old_parent in before_parents.items():
                self._graph_nodes()[child_id].parent_id = old_parent
            raise
        return obj

    def create_primitive(
        self,
        node_id: str,
        primitive: PrimitiveType,
        *,
        parent_id: str | None = None,
        tags: Sequence[str] | None = None,
        position: Sequence[float] | None = None,
        rotation: Sequence[float] | None = None,
        scale: Sequence[float] | None = None,
        size: Sequence[float] | None = None,
        radius: float = 0.5,
        height: float = 1.0,
        visible: bool = True,
        material: Material | Mapping[str, Any] | None = None,
        physics: Physics | Mapping[str, Any] | None = None,
        **meta: Any,
    ) -> PrimitiveNode:
        """Create a built-in primitive in the validated scene graph."""
        self._ensure_unique(node_id)
        node = PrimitiveNode(
            id=node_id,
            parent_id=parent_id,
            tags=list(tags or []),
            position=as_vec3(position),
            rotation=as_vec3(rotation),
            scale=as_vec3(scale, (1.0, 1.0, 1.0)),
            visible=visible,
            material=_material(material) or Material(),
            physics=_physics(physics),
            meta=meta,
            primitive=primitive,
            size=as_vec3(size, (1.0, 1.0, 1.0)),
            radius=float(radius),
            height=float(height),
        )
        self._primitives[node_id] = node
        try:
            self.validate_graph()
        except Exception:
            del self._primitives[node_id]
            raise
        return node

    add_primitive = create_primitive

    def add_annotation(
        self,
        annotation_id: str,
        position: Sequence[float] | None = None,
        *,
        target_id: str | None = None,
        offset: Sequence[float] | None = None,
        label: str | None = None,
        description: str | None = None,
        color: str = "#ffcc00",
        visible: bool = True,
        apply_environment: bool = True,
        **meta: Any,
    ) -> Annotation:
        self._ensure_unique(annotation_id)
        relative_offset = as_vec3(offset)
        if target_id is not None:
            if position is not None:
                raise ValueError("Pass either position or target_id with offset, not both")
            if target_id not in self._graph_nodes():
                raise KeyError(f"Unknown annotation target id {target_id!r}")
            target_position = self._world_transform(target_id)[0]
            position = tuple(target_position[index] + relative_offset[index] for index in range(3))
        elif position is None:
            raise ValueError("Annotation requires position or target_id")
        pos = self._resolve_position(annotation_id, position, apply_environment=apply_environment)
        ann = build_annotation(
            annotation_id,
            pos,
            target_id=target_id,
            offset=relative_offset,
            label=label,
            description=description,
            color=color,
            visible=visible,
            **meta,
        )
        self._annotations[annotation_id] = ann
        return ann

    def add_trajectory(
        self,
        trajectory_id: str,
        points: Sequence[Sequence[float]],
        *,
        color: str = "#2f80ed",
        line_width: float = 2.0,
        closed: bool = False,
        visible: bool = True,
        apply_environment: bool = True,
        **meta: Any,
    ) -> Trajectory:
        self._ensure_unique(trajectory_id)
        resolved: list[Vec3] = []
        for index, point in enumerate(points):
            resolved.append(
                self._resolve_position(
                    f"{trajectory_id}[{index}]",
                    point,
                    apply_environment=apply_environment,
                )
            )
        traj = build_trajectory(
            trajectory_id,
            resolved,
            color=color,
            line_width=line_width,
            closed=closed,
            visible=visible,
            **meta,
        )
        self._trajectories[trajectory_id] = traj
        return traj

    def place_on_world(
        self,
        asset_id: str,
        source: str | Path,
        *,
        x: float,
        z: float,
        offset_y: float = 0.0,
        format: str | None = "glb",
        rotation: Sequence[float] | None = None,
        scale: Sequence[float] | None = None,
        visible: bool = True,
        apply_environment: bool = True,
        **meta: Any,
    ) -> MeshAsset:
        """Place a mesh on top of the world environment at (x, z).

        Height comes from world-mesh raycast when ``trimesh`` is installed,
        otherwise from the ground plane / zero.
        """
        if self._environment is None:
            raise ValueError("Call set_environment() before place_on_world()")
        y = self._environment.height_at(x, z) + offset_y
        return self.add_mesh(
            asset_id,
            source,
            format=format,
            position=(x, y, z),
            rotation=rotation,
            scale=scale,
            visible=visible,
            apply_environment=apply_environment,
            **meta,
        )

    def update_node(
        self,
        node_id: str,
        *,
        position: Sequence[float] | None = None,
        rotation: Sequence[float] | None = None,
        scale: Sequence[float] | None = None,
        visible: bool | None = None,
        apply_environment: bool = False,
    ) -> dict[str, Any]:
        """Update transform fields for a graph node or annotation."""
        node: Any
        if node_id in self._meshes:
            node = self._meshes[node_id]
        elif node_id in self._objects:
            node = self._objects[node_id]
        elif node_id in self._primitives:
            node = self._primitives[node_id]
        elif node_id in self._annotations:
            node = self._annotations[node_id]
        else:
            raise KeyError(f"Unknown node id {node_id!r}")

        if position is not None:
            resolved = self._resolve_position(
                node_id,
                position,
                apply_environment=apply_environment,
            )
            node.position = resolved
        if rotation is not None and hasattr(node, "rotation"):
            node.rotation = as_vec3(rotation)
        if scale is not None and hasattr(node, "scale"):
            node.scale = as_vec3(scale, (1.0, 1.0, 1.0))
        if visible is not None:
            node.visible = bool(visible)
        return node.to_dict()

    def patch_node(self, node_id: str, patch: Mapping[str, Any]) -> dict[str, Any]:
        """Patch explicit editable properties and validate the resulting graph."""
        node = self._graph_nodes().get(node_id)
        if node is None:
            raise KeyError(f"Unknown graph node id {node_id!r}")
        before = copy.deepcopy(node)
        aliases = {"parentId": "parent_id"}
        allowed = {
            "parent_id",
            "tags",
            "position",
            "rotation",
            "scale",
            "visible",
            "material",
            "physics",
            "label",
            "source",
            "format",
            "primitive",
            "size",
            "radius",
            "height",
            "meta",
        }
        try:
            for raw_key, value in patch.items():
                key = aliases.get(raw_key, raw_key)
                if key not in allowed or not hasattr(node, key):
                    raise ValueError(f"Property {raw_key!r} cannot be patched")
                if key in {"position", "rotation", "scale", "size"}:
                    value = as_vec3(value, (1.0, 1.0, 1.0) if key in {"scale", "size"} else None)
                elif key == "tags":
                    if not isinstance(value, list) or not all(
                        isinstance(item, str) for item in value
                    ):
                        raise ValueError("tags must be a list of strings")
                    value = list(value)
                elif key == "material":
                    value = _material(value)
                elif key == "physics":
                    value = _physics(value)
                elif key == "meta":
                    if not isinstance(value, dict):
                        raise ValueError("meta must be an object")
                    value = copy.deepcopy(value)
                setattr(node, key, value)
            self.validate_graph()
        except Exception:
            self._replace_graph_node(node_id, before)
            raise
        return node.to_dict()

    def reparent(self, node_id: str, parent_id: str | None) -> dict[str, Any]:
        """Move one node while preserving its approximate world transform."""
        world_position, world_rotation, world_scale = self._world_transform(node_id)
        if parent_id is None:
            parent_position = (0.0, 0.0, 0.0)
            parent_rotation = (0.0, 0.0, 0.0)
            parent_scale = (1.0, 1.0, 1.0)
        else:
            parent_position, parent_rotation, parent_scale = self._world_transform(parent_id)
        if any(value == 0.0 for value in parent_scale):
            raise ValueError("Cannot preserve world transform under a zero-scale parent")
        self.patch_node(node_id, {"parentId": parent_id})
        local_position = tuple(
            (world_position[index] - parent_position[index]) / parent_scale[index]
            for index in range(3)
        )
        local_rotation = tuple(world_rotation[index] - parent_rotation[index] for index in range(3))
        local_scale = tuple(world_scale[index] / parent_scale[index] for index in range(3))
        return self.patch_node(
            node_id,
            {
                "position": local_position,
                "rotation": local_rotation,
                "scale": local_scale,
            },
        )

    def _world_transform(self, node_id: str) -> tuple[Vec3, Vec3, Vec3]:
        nodes = self._graph_nodes()
        node = nodes.get(node_id)
        if node is None:
            raise KeyError(f"Unknown graph node id {node_id!r}")
        position = node.position
        rotation = node.rotation
        scale = node.scale
        parent_id = node.parent_id
        while parent_id is not None:
            parent = nodes[parent_id]
            position = tuple(
                parent.position[index] + position[index] * parent.scale[index] for index in range(3)
            )
            rotation = tuple(parent.rotation[index] + rotation[index] for index in range(3))
            scale = tuple(parent.scale[index] * scale[index] for index in range(3))
            parent_id = parent.parent_id
        return position, rotation, scale

    def delete_recursive(self, node_id: str) -> list[dict[str, Any]]:
        """Delete a node and all descendants, returning deleted node payloads."""
        if node_id not in self._graph_nodes():
            raise KeyError(f"Unknown graph node id {node_id!r}")
        ids = [node_id, *self.descendants(node_id)]
        deleted = [copy.deepcopy(self._graph_nodes()[item]).to_dict() for item in ids]
        anchored_annotations = [
            annotation for annotation in self._annotations.values() if annotation.target_id in ids
        ]
        deleted.extend(copy.deepcopy(annotation).to_dict() for annotation in anchored_annotations)
        for annotation in anchored_annotations:
            self._annotations.pop(annotation.id, None)
        for item in reversed(ids):
            self._meshes.pop(item, None)
            self._objects.pop(item, None)
            self._primitives.pop(item, None)
        return deleted

    def duplicate_subtree(
        self,
        node_id: str,
        *,
        new_id: str | None = None,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        """Duplicate a subtree with stable, collision-free generated identifiers."""
        nodes = self._graph_nodes()
        if node_id not in nodes:
            raise KeyError(f"Unknown graph node id {node_id!r}")
        source_ids = [node_id, *self.descendants(node_id)]
        root_copy_id = new_id or self._available_id(f"{node_id}_copy")
        self._ensure_unique(root_copy_id)
        mapping = {node_id: root_copy_id}
        for source_id in source_ids[1:]:
            mapping[source_id] = self._available_id(
                f"{root_copy_id}_{source_id}", reserved=set(mapping.values())
            )
        for source_id in source_ids:
            duplicate = copy.deepcopy(nodes[source_id])
            duplicate.id = mapping[source_id]
            if source_id == node_id:
                duplicate.parent_id = parent_id if parent_id is not None else duplicate.parent_id
            elif duplicate.parent_id is not None:
                duplicate.parent_id = mapping[duplicate.parent_id]
            self._store_graph_node(duplicate)
        self.validate_graph()
        return self._graph_nodes()[root_copy_id].to_dict()

    def descendants(self, node_id: str) -> list[str]:
        """Return descendants in deterministic pre-order."""
        nodes = self._graph_nodes()
        result: list[str] = []

        def visit(parent: str) -> None:
            for child_id, child in nodes.items():
                if child.parent_id == parent:
                    result.append(child_id)
                    visit(child_id)

        visit(node_id)
        return result

    def validate_graph(self) -> None:
        """Validate globally unique ids, existing parents, and acyclicity."""
        groups = [
            self._meshes,
            self._objects,
            self._primitives,
            self._annotations,
            self._trajectories,
        ]
        all_ids = [node_id for group in groups for node_id in group]
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("Scene node ids must be globally unique")
        nodes = self._graph_nodes()
        for annotation in self._annotations.values():
            if annotation.target_id is not None and annotation.target_id not in nodes:
                raise ValueError(
                    f"Annotation target {annotation.target_id!r} for {annotation.id!r} "
                    "does not exist"
                )
        for node in nodes.values():
            if isinstance(node, PrimitiveNode):
                if node.primitive not in {"box", "sphere", "capsule", "plane"}:
                    raise ValueError(f"Unsupported primitive: {node.primitive!r}")
                if node.radius <= 0 or node.height <= 0:
                    raise ValueError("Primitive radius and height must be greater than zero")
            if node.parent_id is not None and node.parent_id not in nodes:
                raise ValueError(f"Parent {node.parent_id!r} for {node.id!r} does not exist")
            seen: set[str] = set()
            current = node
            while current.parent_id is not None:
                if current.id in seen:
                    raise ValueError(f"Scene graph contains a cycle at {current.id!r}")
                seen.add(current.id)
                current = nodes[current.parent_id]

    def save(self, path: str | Path) -> Path:
        """Save the scene as a sceneify JSON document."""
        from sceneify.io import save_scene

        return save_scene(self, path)

    @classmethod
    def load(cls, path: str | Path) -> Scene:
        """Load a sceneify JSON document (or raw scene payload)."""
        from sceneify.io import load_scene_dict

        return cls.from_dict(load_scene_dict(path))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Scene:
        from sceneify.io import migrate_scene_payload

        data = migrate_scene_payload(data)
        scene = cls(
            name=str(data.get("name", "scene")), background=str(data.get("background", "#0f1115"))
        )
        env_data = data.get("environment")
        if env_data:
            scene._environment = Environment.from_dict(env_data)
        for mesh in data.get("meshes") or []:
            scene._meshes[mesh["id"]] = MeshAsset(
                id=mesh["id"],
                parent_id=mesh.get("parentId"),
                tags=list(mesh.get("tags") or []),
                source=mesh["source"],
                format=mesh.get("format"),
                position=as_vec3(mesh.get("position")),
                rotation=as_vec3(mesh.get("rotation")),
                scale=as_vec3(mesh.get("scale"), (1.0, 1.0, 1.0)),
                visible=bool(mesh.get("visible", True)),
                material=Material.from_dict(mesh["material"]) if mesh.get("material") else None,
                physics=Physics.from_dict(mesh.get("physics")),
                meta=dict(mesh.get("meta") or {}),
            )
        for obj in data.get("objects") or []:
            scene._objects[obj["id"]] = SceneObject(
                id=obj["id"],
                parent_id=obj.get("parentId"),
                tags=list(obj.get("tags") or []),
                label=obj.get("label"),
                position=as_vec3(obj.get("position")),
                rotation=as_vec3(obj.get("rotation")),
                scale=as_vec3(obj.get("scale"), (1.0, 1.0, 1.0)),
                visible=bool(obj.get("visible", True)),
                material=Material.from_dict(obj["material"]) if obj.get("material") else None,
                physics=Physics.from_dict(obj.get("physics")),
                meta=dict(obj.get("meta") or {}),
            )
        for primitive in data.get("primitives") or []:
            scene._primitives[primitive["id"]] = PrimitiveNode(
                id=primitive["id"],
                parent_id=primitive.get("parentId"),
                tags=list(primitive.get("tags") or []),
                position=as_vec3(primitive.get("position")),
                rotation=as_vec3(primitive.get("rotation")),
                scale=as_vec3(primitive.get("scale"), (1.0, 1.0, 1.0)),
                visible=bool(primitive.get("visible", True)),
                material=Material.from_dict(primitive.get("material")),
                physics=Physics.from_dict(primitive.get("physics")),
                meta=dict(primitive.get("meta") or {}),
                primitive=primitive.get("primitive", "box"),
                size=as_vec3(primitive.get("size"), (1.0, 1.0, 1.0)),
                radius=float(primitive.get("radius", 0.5)),
                height=float(primitive.get("height", 1.0)),
            )
        for ann in data.get("annotations") or []:
            scene._annotations[ann["id"]] = Annotation(
                id=ann["id"],
                position=as_vec3(ann["position"]),
                target_id=ann.get("targetId"),
                offset=as_vec3(ann.get("offset")),
                label=ann.get("label"),
                description=ann.get("description"),
                color=str(ann.get("color", "#ffcc00")),
                visible=bool(ann.get("visible", True)),
                meta=dict(ann.get("meta") or {}),
            )
        for traj in data.get("trajectories") or []:
            scene._trajectories[traj["id"]] = Trajectory(
                id=traj["id"],
                points=[as_vec3(p) for p in traj["points"]],
                color=str(traj.get("color", "#2f80ed")),
                line_width=float(traj.get("lineWidth", traj.get("line_width", 2.0))),
                closed=bool(traj.get("closed", False)),
                visible=bool(traj.get("visible", True)),
                meta=dict(traj.get("meta") or {}),
            )
        game = data.get("game")
        if game is not None:
            if not isinstance(game, dict):
                raise ValueError("game must be an object")
            scene._game_manifest = copy.deepcopy(game)
        presentation = data.get("presentation")
        if presentation is not None:
            if not isinstance(presentation, dict):
                raise ValueError("presentation must be an object")
            scene._presentation = copy.deepcopy(presentation)
        scene.validate_graph()
        return scene

    def validate_environment(self, *, raise_on_reject: bool = False) -> list[RuleViolation]:
        """Re-check mesh/object/annotation positions against the environment rules."""
        if self._environment is None:
            return []
        violations: list[RuleViolation] = []
        for mesh in self._meshes.values():
            _, found = self._environment.apply_point(
                mesh.position,
                node_id=mesh.id,
                raise_on_reject=raise_on_reject,
            )
            violations.extend(found)
        for obj in self._objects.values():
            _, found = self._environment.apply_point(
                obj.position,
                node_id=obj.id,
                raise_on_reject=raise_on_reject,
            )
            violations.extend(found)
        for ann in self._annotations.values():
            _, found = self._environment.apply_point(
                ann.position,
                node_id=ann.id,
                raise_on_reject=raise_on_reject,
            )
            violations.extend(found)
        return violations

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": 2,
            "name": self.name,
            "background": self.background,
            "environment": self._environment.to_dict() if self._environment else None,
            "meshes": [m.to_dict() for m in self._meshes.values()],
            "objects": [o.to_dict() for o in self._objects.values()],
            "primitives": [p.to_dict() for p in self._primitives.values()],
            "annotations": [a.to_dict() for a in self._annotations.values()],
            "trajectories": [t.to_dict() for t in self._trajectories.values()],
            "game": copy.deepcopy(self._game_manifest),
            "presentation": copy.deepcopy(self._presentation),
        }

    def run(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        open_browser: bool = True,
        block: bool = True,
        stop_on: str = "enter",
        project_root: str | Path | None = None,
    ):
        """Serve the scene in a local web viewer.

        By default the call stays occupied until you press Enter (or Ctrl+C).
        Use ``block=False`` to get a ServerHandle and keep the shell free.
        """
        from sceneify.server import serve_scene

        return serve_scene(
            self,
            host=host,
            port=port,
            open_browser=open_browser,
            block=block,
            stop_on=stop_on,  # type: ignore[arg-type]
            realtime=False,
            project_root=project_root,
        )

    def play(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        open_browser: bool = True,
        block: bool = True,
        stop_on: str = "enter",
        tick_rate: float = 60.0,
        project_root: str | Path | None = None,
    ):
        """Serve the scene with shared realtime ticks and viewer input."""
        from sceneify.server import serve_scene

        return serve_scene(
            self,
            host=host,
            port=port,
            open_browser=open_browser,
            block=block,
            stop_on=stop_on,  # type: ignore[arg-type]
            realtime=True,
            tick_rate=tick_rate,
            project_root=project_root,
        )

    def _resolve_position(
        self,
        node_id: str,
        position: Sequence[float] | None,
        *,
        apply_environment: bool,
    ) -> Vec3:
        point = as_vec3(position)
        if not apply_environment or self._environment is None:
            return point
        resolved, _ = self._environment.apply_point(point, node_id=node_id, raise_on_reject=True)
        return resolved

    def _ensure_unique(self, node_id: str) -> None:
        taken = (
            set(self._meshes)
            | set(self._objects)
            | set(self._primitives)
            | set(self._annotations)
            | set(self._trajectories)
        )
        if node_id in taken:
            raise ValueError(f"Scene already has a node with id {node_id!r}")

    def _graph_nodes(self) -> dict[str, MeshAsset | SceneObject | PrimitiveNode]:
        return {**self._meshes, **self._objects, **self._primitives}

    def _store_graph_node(self, node: MeshAsset | SceneObject | PrimitiveNode) -> None:
        if isinstance(node, PrimitiveNode):
            self._primitives[node.id] = node
        elif isinstance(node, MeshAsset):
            self._meshes[node.id] = node
        else:
            self._objects[node.id] = node

    def _replace_graph_node(
        self, node_id: str, node: MeshAsset | SceneObject | PrimitiveNode
    ) -> None:
        self._meshes.pop(node_id, None)
        self._objects.pop(node_id, None)
        self._primitives.pop(node_id, None)
        self._store_graph_node(node)

    def _available_id(self, base: str, *, reserved: set[str] | None = None) -> str:
        taken = set(self._graph_nodes()) | (reserved or set())
        if base not in taken:
            return base
        index = 2
        while f"{base}_{index}" in taken:
            index += 1
        return f"{base}_{index}"


def _infer_format(source: str) -> str | None:
    lower = source.lower().split("?", 1)[0]
    for ext in (".glb", ".gltf", ".ply", ".obj", ".stl"):
        if lower.endswith(ext):
            return ext.lstrip(".")
    return None


def _material(value: Material | Mapping[str, Any] | None) -> Material | None:
    if value is None or isinstance(value, Material):
        return value
    return Material.from_dict(dict(value))


def _physics(value: Physics | Mapping[str, Any] | None) -> Physics | None:
    if value is None or isinstance(value, Physics):
        return value
    return Physics.from_dict(dict(value))
