"""Explicit scene graph node models."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from sceneify.types import Vec3, as_vec3

BodyType = Literal["fixed", "kinematic", "dynamic"]
ColliderType = Literal["cuboid", "ball", "capsule", "hull"]
PrimitiveType = Literal["box", "sphere", "capsule", "plane"]


@dataclass
class Material:
    """Browser-consumable material properties."""

    color: str = "#ffffff"
    opacity: float = 1.0
    wireframe: bool = False
    roughness: float = 1.0
    metalness: float = 0.0
    base_color_texture: str | None = None
    normal_texture: str | None = None
    metallic_roughness_texture: str | None = None
    texture_repeat: tuple[float, float] = (1.0, 1.0)

    def __post_init__(self) -> None:
        if not 0.0 <= self.opacity <= 1.0:
            raise ValueError("Material opacity must be between 0 and 1")
        if not 0.0 <= self.roughness <= 1.0:
            raise ValueError("Material roughness must be between 0 and 1")
        if not 0.0 <= self.metalness <= 1.0:
            raise ValueError("Material metalness must be between 0 and 1")
        if len(self.texture_repeat) != 2 or any(value <= 0 for value in self.texture_repeat):
            raise ValueError("Material texture repeat must contain two positive values")

    def to_dict(self) -> dict[str, Any]:
        return {
            "color": self.color,
            "opacity": self.opacity,
            "wireframe": self.wireframe,
            "roughness": self.roughness,
            "metalness": self.metalness,
            "baseColorTexture": self.base_color_texture,
            "normalTexture": self.normal_texture,
            "metallicRoughnessTexture": self.metallic_roughness_texture,
            "textureRepeat": list(self.texture_repeat),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Material:
        values = data or {}
        return cls(
            color=str(values.get("color", "#ffffff")),
            opacity=float(values.get("opacity", 1.0)),
            wireframe=bool(values.get("wireframe", False)),
            roughness=float(values.get("roughness", 1.0)),
            metalness=float(values.get("metalness", 0.0)),
            base_color_texture=values.get("baseColorTexture"),
            normal_texture=values.get("normalTexture"),
            metallic_roughness_texture=values.get("metallicRoughnessTexture"),
            texture_repeat=tuple(float(value) for value in values.get("textureRepeat", [1, 1])),
        )


@dataclass
class Physics:
    """Physics body and collider configuration."""

    body: BodyType = "fixed"
    collider: ColliderType = "cuboid"
    sensor: bool = False
    mass: float = 1.0

    def __post_init__(self) -> None:
        if self.body not in {"fixed", "kinematic", "dynamic"}:
            raise ValueError(f"Unsupported physics body: {self.body!r}")
        if self.collider not in {"cuboid", "ball", "capsule", "hull"}:
            raise ValueError(f"Unsupported collider: {self.collider!r}")
        if self.mass <= 0:
            raise ValueError("Physics mass must be greater than zero")

    def to_dict(self) -> dict[str, Any]:
        return {
            "body": self.body,
            "collider": self.collider,
            "sensor": self.sensor,
            "mass": self.mass,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Physics | None:
        if data is None:
            return None
        return cls(
            body=data.get("body", "fixed"),
            collider=data.get("collider", "cuboid"),
            sensor=bool(data.get("sensor", False)),
            mass=float(data.get("mass", 1.0)),
        )


@dataclass
class GraphNode:
    """Fields shared by editable graph nodes."""

    id: str
    parent_id: str | None = None
    tags: list[str] = field(default_factory=list)
    position: Vec3 = (0.0, 0.0, 0.0)
    rotation: Vec3 = (0.0, 0.0, 0.0)
    scale: Vec3 = (1.0, 1.0, 1.0)
    visible: bool = True
    material: Material | None = None
    physics: Physics | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def _base_dict(self, kind: str) -> dict[str, Any]:
        return {
            "kind": kind,
            "id": self.id,
            "parentId": self.parent_id,
            "tags": list(self.tags),
            "position": list(self.position),
            "rotation": list(self.rotation),
            "scale": list(self.scale),
            "visible": self.visible,
            "material": self.material.to_dict() if self.material else None,
            "physics": self.physics.to_dict() if self.physics else None,
            "meta": self.meta,
        }


@dataclass
class MeshAsset(GraphNode):
    """A 3D asset referenced by path or URL (GLB, glTF, PLY, …)."""

    source: str = ""
    format: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = self._base_dict("mesh")
        result.update({"source": self.source, "format": self.format})
        return result


@dataclass
class SceneObject(GraphNode):
    """A logical object that can group meshes or carry custom payload."""

    label: str | None = None
    children: list[str] = field(default_factory=list, repr=False)

    def to_dict(self) -> dict[str, Any]:
        result = self._base_dict("object")
        result["label"] = self.label
        return result


@dataclass
class PrimitiveNode(GraphNode):
    """An editable built-in geometry primitive."""

    primitive: PrimitiveType = "box"
    size: Vec3 = (1.0, 1.0, 1.0)
    radius: float = 0.5
    height: float = 1.0

    def __post_init__(self) -> None:
        if self.primitive not in {"box", "sphere", "capsule", "plane"}:
            raise ValueError(f"Unsupported primitive: {self.primitive!r}")
        if self.radius <= 0 or self.height <= 0:
            raise ValueError("Primitive radius and height must be greater than zero")

    def to_dict(self) -> dict[str, Any]:
        result = self._base_dict("primitive")
        result.update(
            {
                "primitive": self.primitive,
                "size": list(self.size),
                "radius": self.radius,
                "height": self.height,
            }
        )
        return result


def build_mesh(
    asset_id: str,
    source: str,
    *,
    format: str | None = None,
    position: Sequence[float] | None = None,
    rotation: Sequence[float] | None = None,
    scale: Sequence[float] | None = None,
    visible: bool = True,
    parent_id: str | None = None,
    tags: Sequence[str] | None = None,
    material: Material | None = None,
    physics: Physics | None = None,
    **meta: Any,
) -> MeshAsset:
    return MeshAsset(
        id=asset_id,
        parent_id=parent_id,
        tags=list(tags or []),
        source=source,
        format=format,
        position=as_vec3(position),
        rotation=as_vec3(rotation),
        scale=as_vec3(scale, (1.0, 1.0, 1.0)),
        visible=visible,
        material=material,
        physics=physics,
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
    parent_id: str | None = None,
    tags: Sequence[str] | None = None,
    material: Material | None = None,
    physics: Physics | None = None,
    **meta: Any,
) -> SceneObject:
    return SceneObject(
        id=object_id,
        parent_id=parent_id,
        tags=list(tags or []),
        label=label,
        children=list(children or []),
        position=as_vec3(position),
        rotation=as_vec3(rotation),
        scale=as_vec3(scale, (1.0, 1.0, 1.0)),
        visible=visible,
        material=material,
        physics=physics,
        meta=meta,
    )
