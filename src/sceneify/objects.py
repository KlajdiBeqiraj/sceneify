"""Scene graph objects and mesh assets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from sceneify.types import Vec3, as_vec3


@dataclass
class MeshAsset:
    """A 3D asset referenced by path or URL (GLB, glTF, PLY, …)."""

    id: str
    source: str
    format: str | None = None
    position: Vec3 = (0.0, 0.0, 0.0)
    rotation: Vec3 = (0.0, 0.0, 0.0)
    scale: Vec3 = (1.0, 1.0, 1.0)
    visible: bool = True
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "mesh",
            "id": self.id,
            "source": self.source,
            "format": self.format,
            "position": list(self.position),
            "rotation": list(self.rotation),
            "scale": list(self.scale),
            "visible": self.visible,
            "meta": self.meta,
        }


@dataclass
class SceneObject:
    """A logical object that can group meshes or carry custom payload."""

    id: str
    label: str | None = None
    children: list[str] = field(default_factory=list)
    position: Vec3 = (0.0, 0.0, 0.0)
    rotation: Vec3 = (0.0, 0.0, 0.0)
    scale: Vec3 = (1.0, 1.0, 1.0)
    visible: bool = True
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "object",
            "id": self.id,
            "label": self.label,
            "children": list(self.children),
            "position": list(self.position),
            "rotation": list(self.rotation),
            "scale": list(self.scale),
            "visible": self.visible,
            "meta": self.meta,
        }


def build_mesh(
    asset_id: str,
    source: str,
    *,
    format: str | None = None,
    position: Sequence[float] | None = None,
    rotation: Sequence[float] | None = None,
    scale: Sequence[float] | None = None,
    visible: bool = True,
    **meta: Any,
) -> MeshAsset:
    return MeshAsset(
        id=asset_id,
        source=source,
        format=format,
        position=as_vec3(position),
        rotation=as_vec3(rotation),
        scale=as_vec3(scale, (1.0, 1.0, 1.0)),
        visible=visible,
        meta=meta,
    )


def build_object(
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
    return SceneObject(
        id=object_id,
        label=label,
        children=list(children or []),
        position=as_vec3(position),
        rotation=as_vec3(rotation),
        scale=as_vec3(scale, (1.0, 1.0, 1.0)),
        visible=visible,
        meta=meta,
    )
