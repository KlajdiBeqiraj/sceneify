"""High-level Scene API (Streamlit-like entry point)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sceneify.annotations import Annotation, build_annotation
from sceneify.environment import Environment, RuleViolation, build_default_environment
from sceneify.objects import MeshAsset, SceneObject, build_mesh, build_object
from sceneify.trajectories import Trajectory, build_trajectory
from sceneify.types import Vec3, as_vec3


class Scene:
    """Composable 3D scene: multiple assets, objects, annotations, trajectories."""

    def __init__(self, name: str = "scene", *, background: str = "#0f1115") -> None:
        self.name = name
        self.background = background
        self._meshes: dict[str, MeshAsset] = {}
        self._objects: dict[str, SceneObject] = {}
        self._annotations: dict[str, Annotation] = {}
        self._trajectories: dict[str, Trajectory] = {}
        self._environment: Environment | None = None

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
            **meta,
        )
        self._meshes[asset_id] = mesh
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
            **meta,
        )
        self._objects[object_id] = obj
        return obj

    def add_annotation(
        self,
        annotation_id: str,
        position: Sequence[float],
        *,
        label: str | None = None,
        description: str | None = None,
        color: str = "#ffcc00",
        visible: bool = True,
        apply_environment: bool = True,
        **meta: Any,
    ) -> Annotation:
        self._ensure_unique(annotation_id)
        pos = self._resolve_position(annotation_id, position, apply_environment=apply_environment)
        ann = build_annotation(
            annotation_id,
            pos,
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
        """Update transform fields for a mesh, object, or annotation."""
        node: Any
        if node_id in self._meshes:
            node = self._meshes[node_id]
        elif node_id in self._objects:
            node = self._objects[node_id]
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
        scene = cls(
            name=str(data.get("name", "scene")), background=str(data.get("background", "#0f1115"))
        )
        env_data = data.get("environment")
        if env_data:
            scene._environment = Environment.from_dict(env_data)
        for mesh in data.get("meshes") or []:
            scene._meshes[mesh["id"]] = MeshAsset(
                id=mesh["id"],
                source=mesh["source"],
                format=mesh.get("format"),
                position=as_vec3(mesh.get("position")),
                rotation=as_vec3(mesh.get("rotation")),
                scale=as_vec3(mesh.get("scale"), (1.0, 1.0, 1.0)),
                visible=bool(mesh.get("visible", True)),
                meta=dict(mesh.get("meta") or {}),
            )
        for obj in data.get("objects") or []:
            scene._objects[obj["id"]] = SceneObject(
                id=obj["id"],
                label=obj.get("label"),
                children=list(obj.get("children") or []),
                position=as_vec3(obj.get("position")),
                rotation=as_vec3(obj.get("rotation")),
                scale=as_vec3(obj.get("scale"), (1.0, 1.0, 1.0)),
                visible=bool(obj.get("visible", True)),
                meta=dict(obj.get("meta") or {}),
            )
        for ann in data.get("annotations") or []:
            scene._annotations[ann["id"]] = Annotation(
                id=ann["id"],
                position=as_vec3(ann["position"]),
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
            "name": self.name,
            "background": self.background,
            "environment": self._environment.to_dict() if self._environment else None,
            "meshes": [m.to_dict() for m in self._meshes.values()],
            "objects": [o.to_dict() for o in self._objects.values()],
            "annotations": [a.to_dict() for a in self._annotations.values()],
            "trajectories": [t.to_dict() for t in self._trajectories.values()],
        }

    def run(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        open_browser: bool = True,
        block: bool = True,
        stop_on: str = "enter",
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
            | set(self._annotations)
            | set(self._trajectories)
        )
        if node_id in taken:
            raise ValueError(f"Scene already has a node with id {node_id!r}")


def _infer_format(source: str) -> str | None:
    lower = source.lower().split("?", 1)[0]
    for ext in (".glb", ".gltf", ".ply", ".obj", ".stl"):
        if lower.endswith(ext):
            return ext.lstrip(".")
    return None
