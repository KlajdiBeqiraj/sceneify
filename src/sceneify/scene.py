"""High-level Scene API (Streamlit-like entry point)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from sceneify.annotations import Annotation, build_annotation
from sceneify.objects import MeshAsset, SceneObject, build_mesh, build_object
from sceneify.trajectories import Trajectory, build_trajectory


class Scene:
    """Composable 3D scene: multiple assets, objects, annotations, trajectories."""

    def __init__(self, name: str = "scene", *, background: str = "#0f1115") -> None:
        self.name = name
        self.background = background
        self._meshes: dict[str, MeshAsset] = {}
        self._objects: dict[str, SceneObject] = {}
        self._annotations: dict[str, Annotation] = {}
        self._trajectories: dict[str, Trajectory] = {}

    def add_glb(
        self,
        asset_id: str,
        source: str | Path,
        *,
        position: Sequence[float] | None = None,
        rotation: Sequence[float] | None = None,
        scale: Sequence[float] | None = None,
        visible: bool = True,
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
        **meta: Any,
    ) -> MeshAsset:
        """Add any supported mesh asset (GLB, glTF, PLY, …)."""
        self._ensure_unique(asset_id)
        path = str(source)
        inferred = format or _infer_format(path)
        mesh = build_mesh(
            asset_id,
            path,
            format=inferred,
            position=position,
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
        **meta: Any,
    ) -> SceneObject:
        """Add a logical container object that can group child asset ids."""
        self._ensure_unique(object_id)
        obj = build_object(
            object_id,
            label=label,
            children=children,
            position=position,
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
        **meta: Any,
    ) -> Annotation:
        self._ensure_unique(annotation_id)
        ann = build_annotation(
            annotation_id,
            position,
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
        **meta: Any,
    ) -> Trajectory:
        self._ensure_unique(trajectory_id)
        traj = build_trajectory(
            trajectory_id,
            points,
            color=color,
            line_width=line_width,
            closed=closed,
            visible=visible,
            **meta,
        )
        self._trajectories[trajectory_id] = traj
        return traj

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "background": self.background,
            "meshes": [m.to_dict() for m in self._meshes.values()],
            "objects": [o.to_dict() for o in self._objects.values()],
            "annotations": [a.to_dict() for a in self._annotations.values()],
            "trajectories": [t.to_dict() for t in self._trajectories.values()],
        }

    def run(self, *, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
        """Serve the scene in a local web viewer and block until interrupted."""
        from sceneify.server import serve_scene

        serve_scene(self, host=host, port=port, open_browser=open_browser)

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
